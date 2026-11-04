"""Host-owned oracle for fixed integer function probes; no external intake."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import uuid

from patchreplay.executors import DockerExecutor
from patchreplay.integrity import identity, write_json
from patchreplay.engine import DATA, PACKAGE, interpret

from .fixtures import PROBES, SOURCES

POLICY = "experimental-host-oracle-v1"
MAX_RESPONSE = 4096


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
        return {"raw": received[0] if received else b"", "exit_code": code,
                "timeout": timed_out, "overflow": overflow}


def observe(image, fixture, probe, timeout=10, workspace=None):
    """Execute one registered fixture/probe pair in a fresh container."""
    if fixture not in SOURCES or type(probe) is not int or probe not in range(len(PROBES)):
        raise ValueError("Only registered experiment fixtures and probes are admitted")
    executor = DockerExecutor(image)
    executor.preflight()
    probe_id, args, expected = PROBES[probe]
    request_id = uuid.uuid4().hex
    request = {"protocol": 1, "request_id": request_id, "args": list(args)}
    result = {"policy": POLICY, "fixture": fixture, "probe": probe_id,
              "request": request, "expected": expected, "image": image,
              "source_sha256": hashlib.sha256(SOURCES[fixture].encode()).hexdigest(),
              "outcome": "INFRA_ERROR", "container_removed": False}
    name = "patchreplay-oracle-" + request_id
    result["container_name"] = name
    scratch = Path(workspace) if workspace else Path.cwd() / ".patchreplay" / "observer-work"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="patchreplay-oracle-", dir=scratch.resolve()) as directory:
        folder = Path(directory)
        folder.chmod(0o755)
        candidate = folder / "candidate.py"
        candidate.write_text(SOURCES[fixture], encoding="utf-8", newline="\n")
        candidate.chmod(0o644)
        guest = folder / "guest.py"
        shutil.copyfile(Path(__file__).with_name("guest.py"), guest)
        guest.chmod(0o644)
        command = executor.create_args(name, folder, "bug", 1)
        command[-3:] = ["/input/guest.py", json.dumps(request, separators=(",", ":"))]
        try:
            executor.control(command)
            executor.validate_config(json.loads(executor.control(["inspect", name]))[0], image, folder)
            transport = capture([executor.binary, "start", "--attach", name], timeout)
            raw = transport.pop("raw")
            result["transport"] = {**transport, "response_bytes": len(raw),
                                   "response_sha256": hashlib.sha256(raw).hexdigest()}
            result["response"] = raw.decode("utf-8", errors="replace")
            if transport["overflow"]:
                result["outcome"] = "INVALID_RESPONSE"
                result["reason"] = "Response limit exceeded"
            elif transport["timeout"]:
                result["outcome"] = "TIMEOUT"
            elif transport["exit_code"] != 0:
                result["outcome"] = "EXECUTION_ERROR"
            else:
                result.update(judge(raw, request_id, expected))
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            result.update(outcome="INFRA_ERROR", reason=str(exc))
        finally:
            try:
                executor.control(["rm", "--force", name])
                result["container_removed"] = True
            except (OSError, subprocess.SubprocessError) as exc:
                result.update(outcome="INFRA_ERROR", reason="Cleanup failed: " + str(exc))
    return result


def demonstrate_legacy_forgery(image, output):
    """Deliberately bypass admission ONLY for this fixed, reviewed attack fixture.

    This invokes the internal adapter to expose its observation trust assumption.
    The public run/evaluate path still rejects these unregistered source bytes.
    """
    executor = DockerExecutor(image)
    executor.preflight()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="patchreplay-forgery-", dir=output.parent) as directory:
        folder = Path(directory)
        folder.chmod(0o755)
        (folder / "source").mkdir()
        (folder / "source" / "clamp.py").write_text(SOURCES["forge_records"], encoding="utf-8")
        shutil.copytree(DATA / "evaluators" / "clamp-v1", folder / "evaluator",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(PACKAGE / "worker.py", folder / "worker.py")
        executor.prepare(folder)
        records = output / "records.json"
        result = executor.check(["python", "-I", "-B", "worker", "source", "evaluator",
                                 "bug", str(records), "1"], folder, {}, 10, output / "legacy.log")
        if result["error"] or result["timeout"] or not records.exists():
            raise RuntimeError(f"Legacy demonstration could not run: {result}")
        contract = json.loads((folder / "evaluator" / "contract.json").read_text())
        outcome, _ = interpret(json.loads(records.read_text()), contract["bug"], "after_bug", result["exit_code"])
        command = result["command"]
        name = command[command.index("--name") + 1]
        removed = not executor.control(["ps", "-aq", "--filter", "name=^/" + name + "$"]).strip()
    summary = {"known_weakness_reproduced": outcome == "PASS", "legacy_interpretation": outcome,
               "actual_behavior": "Candidate wrote fake records and exited without executing declared test bodies.",
               "container_removed": removed,
               "admission": "Internal test harness only; public evaluator catalog was not changed."}
    write_json(output / "demonstration.json", summary)
    return summary


def demo(image, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    legacy = demonstrate_legacy_forgery(image, output / "legacy-demonstration")
    observations = []
    for fixture in SOURCES:
        probes = range(len(PROBES)) if fixture in {"buggy", "correct"} else [0]
        for probe in probes:
            observations.append(observe(image, fixture, probe, timeout=2 if fixture == "timeout" else 10,
                                        workspace=output / ".work"))
    matched = legacy["known_weakness_reproduced"] and legacy["container_removed"] and all(
        item["container_removed"] and item["outcome"] == (
            "MISMATCH" if item["fixture"] == "buggy" and item["probe"] in {"negative-lower", "nonzero-lower"}
            else "MATCH" if item["fixture"] in {"buggy", "correct"}
            else "TIMEOUT" if item["fixture"] == "timeout" else "INVALID_RESPONSE")
        for item in observations)
    code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")}
    report = {"schema_version": 1, "policy": POLICY, "expected_outcomes_matched": matched,
              "experiment_sha256": identity(code), "engine_files": code, "legacy_demonstration": legacy,
              "observations": observations,
              "limitations": ["Registered synthetic experiments only; not a production PatchReplay evidence package.",
                              "MATCH means the observed answer equals one host-owned expected value, not internal execution authenticity.",
                              "Request IDs bind responses to requests; they are visible to the guest and are not authentication.",
                              "The Docker daemon, host oracle, reviewed image and kernel are trusted; no escape resistance is established."]}
    write_json(output / "results.json", report)
    return report
