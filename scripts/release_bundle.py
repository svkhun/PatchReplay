"""Build a reviewable offline release ZIP; never uploads or publishes artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(wheel, demo, output):
    subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "src", "pyproject.toml"], cwd=ROOT, check=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files = {}
    for name in ("README.md", "LICENSE", "requirements.lock", "requirements-provenance.lock", "containers/Dockerfile", ".dockerignore", "docs/container-executor.md", "docs/function-workflow.md", "docs/provenance.md", "docs/verification/docker-recovery.md", "docs/reviewer-guide.md", "docs/reviewer-trial-template.json", "docs/trust-operations.md", "docs/real-cases.md", "docs/function-claims.md", "docs/demo-v02.md"):
        files[name] = (ROOT / name).read_bytes()
    files["README.md"] = ("# PatchReplay 0.2 offline review bundle\n\nOpen demo/index.html for two pinned upstream fixes, four synthetic controls, claims and replay records.\n\nInstall the wheel using docs/reviewer-guide.md. See docs/real-cases.md for source/license scope and docs/trust-operations.md for external-trust signing.\n\nSource commit: " + commit + "\nSource repository: https://github.com/svkhun/PatchReplay\n\nAutomated simulated trials are distinct from human usability acceptance. No arbitrary-code or production-readiness claim is made.\n").encode()
    wheel = Path(wheel)
    files["wheel/" + wheel.name] = wheel.read_bytes()
    for p in Path(demo).rglob("*"):
        if p.is_symlink():
            raise ValueError("Release does not accept linked artifacts")
        if p.is_file():
            files["demo/" + p.relative_to(demo).as_posix()] = p.read_bytes()
    for data in files.values():
        if re.search(rb"-----BEGIN (?:ENCRYPTED |RSA |EC |OPENSSH )?PRIVATE KEY-----", data):
            raise ValueError("Private key material cannot enter a release")
    manifest = {"schema_version": 1, "version": "0.2.0", "source_commit": commit, "files": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())},
                "scope": "Reviewed upstream function extracts and synthetic controls. Human usability acceptance is recorded separately."}
    files["release-manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    return verify(output)


def verify(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(n.startswith(("/", "\\")) or ".." in n.split("/") or ":" in n or "\\" in n for n in names):
            raise ValueError("Invalid ZIP paths or duplicate entries")
        manifest = json.loads(archive.read("release-manifest.json"))
        actual = {n: hashlib.sha256(archive.read(n)).hexdigest() for n in names if n != "release-manifest.json"}
        if actual != manifest["files"]:
            raise ValueError("Release manifest does not match its file set")
    return {"release": str(Path(path).resolve()), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(), "file_count": len(actual)}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--wheel", type=Path)
    p.add_argument("--demo", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--verify", type=Path)
    a = p.parse_args()
    if not a.verify and not all((a.wheel, a.demo, a.output)):
        p.error("Provide --verify or all of --wheel, --demo, --output")
    print(json.dumps(verify(a.verify) if a.verify else build(a.wheel, a.demo, a.output), indent=2))
