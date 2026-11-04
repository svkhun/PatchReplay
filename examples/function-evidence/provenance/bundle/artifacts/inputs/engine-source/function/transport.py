"""Bounded guest transport. Verdict computation stays on the host."""
import base64
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from patchreplay.executors import DockerExecutor
from patchreplay.integrity import digest, tree_files
from .contract import POLICY

MAX_RESPONSE = POLICY["max_response_bytes"]


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate response field")
        result[key] = value
    return result


def judge(raw, request_id, expected):
    """Treat every guest byte as untrusted; only the host computes outcomes."""
    try:
        if len(raw) > MAX_RESPONSE:
            raise ValueError("Response limit exceeded")
        response = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if not isinstance(response, dict) or set(response) != {"protocol", "request_id", "value"}:
            raise ValueError("Unexpected response shape")
        if type(response["protocol"]) is not int or response["protocol"] != 1:
            raise ValueError("Protocol mismatch")
        if response["request_id"] != request_id:
            raise ValueError("Response belongs to another request")
        if type(response["value"]) is not int or abs(response["value"]) > 2**53 - 1:
            raise ValueError("Expected a bounded integer answer")
        return {"outcome": "MATCH" if response["value"] == expected else "MISMATCH", "value": response["value"]}
    except (ValueError, UnicodeError, RecursionError) as exc:
        return {"outcome": "INVALID_RESPONSE", "reason": str(exc)}


def capture(command, timeout):
    """Bound Docker attach output while reading, rather than after disk writes.

    This launches only the trusted Docker CLI. The caller must always remove
    the container: killing an attach client does not stop guest execution.
    """
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT) as proc:
        received, errors = [], []

        def read():
            try:
                received.append(proc.stdout.read(MAX_RESPONSE + 1))
            except OSError as exc:
                errors.append(str(exc))

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        reader.join(timeout)
        timed_out = reader.is_alive()
        overflow = bool(received and len(received[0]) > MAX_RESPONSE)
        if timed_out or overflow:
            proc.kill()
        try:
            code = proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = proc.wait(timeout=2)
            timed_out = True
        reader.join(2)
        if reader.is_alive():
            raise OSError("Docker attach output reader did not stop")
        if errors:
            raise OSError(errors[0])
        overflow = bool(received and len(received[0]) > MAX_RESPONSE)
        return {"raw": received[0] if received else b"", "exit_code": code,
                "timeout": timed_out, "overflow": overflow}


def interpret(row, expected):
    """Recompute the observation from raw bytes and host transport metadata."""
    raw = base64.b64decode(row["raw_base64"], validate=True)
    if len(raw) > MAX_RESPONSE + 1 or digest(raw) != row["response_sha256"]:
        raise ValueError("Invalid bounded raw response/hash")
    if row["input_changed"]:
        return {"outcome": "INTEGRITY_ERROR"}
    if row["error"] or not row["container_removed"]:
        return {"outcome": "INFRA_ERROR"}
    if row["overflow"] or len(raw) > MAX_RESPONSE:
        return {"outcome": "INVALID_RESPONSE", "reason": "Response limit exceeded"}
    if row["timeout"]:
        return {"outcome": "TIMEOUT"}
    if row["exit_code"] != 0:
        return {"outcome": "EXECUTION_ERROR"}
    return judge(raw, row["request"]["request_id"], expected)


def observe(executor, source, probe, timeout, workspace):
    """Internal transport; the workflow admits reviewed source before calling it."""
    request_id = uuid.uuid4().hex
    request = {"protocol": 1, "request_id": request_id, "args": probe["args"]}
    name = "patchreplay-function-" + request_id
    row = {"request": request, "container_name": name, "command": [], "duration_seconds": 0,
           "raw_base64": "", "response_sha256": digest(b""), "exit_code": None,
           "timeout": False, "overflow": False, "error": None, "container_removed": False,
           "input_changed": False, "cleanup_error": None}
    start = time.monotonic()
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="request-", dir=workspace) as temporary:
        folder = Path(temporary)
        folder.chmod(0o755)
        (folder / "candidate.py").write_bytes(source)
        shutil.copyfile(Path(__file__).with_name("guest.py"), folder / "guest.py")
        for path in folder.iterdir():
            path.chmod(0o644)
        before = tree_files(folder)
        try:
            command = executor.create_args(name, folder, "bug", 1)
            command[-3:] = ["/input/guest.py", json.dumps(request, sort_keys=True, separators=(",", ":"))]
            row["command"] = command
            executor.control(command)
            executor.validate_config(json.loads(executor.control(["inspect", name]))[0], executor.image, folder)
            result = capture([executor.binary, "start", "--attach", name], timeout)
            raw = result.pop("raw")
            row.update(result, raw_base64=base64.b64encode(raw).decode("ascii"), response_sha256=digest(raw))
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            row["error"] = str(exc)
        finally:
            try:
                executor.control(["rm", "--force", name])
                remaining = executor.control(["ps", "-aq", "--filter", "name=^/" + name + "$"]).strip()
                if remaining:
                    raise OSError("Container still present after removal")
                row["container_removed"] = True
            except (OSError, subprocess.SubprocessError) as exc:
                row["cleanup_error"] = str(exc)
            try:
                row["input_changed"] = tree_files(folder) != before
            except (OSError, ValueError):
                row["input_changed"] = True
    row["duration_seconds"] = round(time.monotonic() - start, 6)
    row["observation"] = interpret(row, probe["expected"])
    return row


