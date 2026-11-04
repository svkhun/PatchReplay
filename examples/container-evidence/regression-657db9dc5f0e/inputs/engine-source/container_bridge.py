"""Container-only transport for reviewed fixtures. Not hostile-code attestation."""
import base64
import json
from pathlib import Path
import subprocess
import sys


def main():
    import pytest
    if pytest.__version__ != "8.3.5":
        raise RuntimeError("Container pytest version must be 8.3.5")
    selection, attempt = sys.argv[1:]
    if selection not in {"bug", "regression"} or attempt not in {"1", "2", "3", "4", "5"}:
        raise ValueError("Invalid check selection")
    with Path("/work/check.log").open("wb") as stream:
        result = subprocess.run([sys.executable, "-I", "-B", "/input/worker.py", "/input/source",
                                 "/input/evaluator", selection, "/work/records.json", attempt],
                                stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    payload = {"exit_code": result.returncode}
    for key, file in (("records", "records.json"), ("junit", "records.xml"), ("log", "check.log")):
        path = Path("/work") / file
        if path.exists() and path.stat().st_size > 200_000:
            raise ValueError("Container artifact exceeded transport limit")
        payload[key] = base64.b64encode(path.read_bytes()).decode("ascii") if path.exists() else None
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
