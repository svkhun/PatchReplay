"""Offline signing examples with ephemeral, encrypted demo keys; no Docker."""
import argparse
import json
from pathlib import Path
import secrets
import shutil
import tempfile

from patchreplay.integrity import write_json
from patchreplay_provenance import core

ROOT = Path(__file__).resolve().parents[1]


def demo(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    trust = output / "trust"
    trust.mkdir()
    subject = ROOT / "examples/observer-evidence"
    expected, public, bundle = trust / "observer.expected.json", trust / "demo-public.pem", output / "bundle"
    core.prepare(subject, "observer-v1", expected)
    # Only the public key leaves this temporary directory; the random password
    # is kept in memory and is never passed to a guest or printed.
    scratch = ROOT / ".patchreplay" / "provenance-demo-work"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="keys-", dir=scratch) as directory:
        work = Path(directory)
        private, local_public = work / "private.pem", work / "public.pem"
        password = secrets.token_bytes(32)
        key_id = core.keygen(private, local_public, password)
        shutil.copyfile(local_public, public)
        core.sign(subject, expected, private, password, bundle)
        results = [{"case": "authentic_expected_subject", **core.verify(bundle, public, expected)}]
        other_private, other_public = work / "other-private.pem", work / "other-public.pem"
        core.keygen(other_private, other_public, password)
        for name in ("tampered_artifact", "missing_artifact", "added_artifact", "invalid_signature", "unknown_key", "wrong_round", "unsigned"):
            candidate = work / name
            shutil.copytree(bundle, candidate)
            pinned, trusted = expected, public
            if name == "tampered_artifact":
                (candidate / "artifacts/README.md").write_text("Changed after signing")
            elif name == "missing_artifact":
                (candidate / "artifacts/README.md").unlink()
            elif name == "added_artifact":
                (candidate / "artifacts/extra.txt").write_text("Added after signing")
            elif name == "invalid_signature":
                data = core.load(candidate / "attestation.json")
                data["signature"] = "A" * 86 + "=="
                write_json(candidate / "attestation.json", data)
            elif name == "unknown_key":
                trusted = other_public
            elif name == "wrong_round":
                data = core.load(expected)
                data["run_id"] = "another-expected-run"
                pinned = work / "other-expected.json"
                write_json(pinned, data)
            else:
                (candidate / "attestation.json").unlink()
            try:
                result = core.verify(candidate, trusted, pinned)
            except (ValueError, OSError, KeyError) as exc:
                result = {"status": "REJECTED", "reason": str(exc)}
            results.append({"case": name, **result})
    passed = results[0]["status"] == "AUTHENTICATED_FOR_EXPECTED_SUBJECT" and all(r["status"] == "REJECTED" for r in results[1:])
    report = {"schema_version": 1, "all_expected_outcomes_matched": passed, "demo_key_id": key_id,
              "private_key_retained": False, "results": results,
              "scope": "Random demo identity only; bundled public key/expectation are illustrative trust inputs, not a production trust root."}
    write_json(output / "results.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = demo(args.output)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["all_expected_outcomes_matched"] else 1)
