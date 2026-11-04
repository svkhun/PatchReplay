"""Verify Git's clean filters preserve all identity-bearing fixture/evidence bytes.

Uses hash-object without -w: no staging, commits, or Git object writes.
"""

import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = sorted(p.relative_to(ROOT).as_posix() for folder in
                   (ROOT / "src" / "patchreplay" / "data", ROOT / "examples" / "evidence",
                    ROOT / "examples" / "container-evidence")
                   for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    names = "\n".join(files) + "\n"
    base = ["git", "-c", "core.autocrlf=true", "hash-object", "--stdin-paths"]
    raw = subprocess.run([*base, "--no-filters"], input=names, cwd=ROOT, text=True, capture_output=True, check=True).stdout.splitlines()
    filtered = subprocess.run(base, input=names, cwd=ROOT, text=True, capture_output=True, check=True).stdout.splitlines()
    assert len(raw) == len(files) == len(filtered)
    changed = [name for name, first, second in zip(files, raw, filtered) if first != second]
    result = {"passed": not changed, "files_checked": len(files), "core.autocrlf": True, "changed_by_clean_filters": changed,
              "limitation": "Read-only Git clean-filter check; this does not execute the project on another OS."}
    (ROOT / "docs" / "verification" / "checkout-bytes.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result))
    return 1 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
