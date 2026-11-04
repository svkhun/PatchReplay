import json
from pathlib import Path
import subprocess

import pytest

from patchreplay.engine import DATA, evaluate, load_case
from patchreplay.executors import DockerExecutor
from patchreplay.integrity import digest, read_json, verify_package, write_json

IMAGE = "sha256:" + "a" * 64


@pytest.mark.parametrize("image", ["python:3.12", "latest", "--privileged", "sha256:abc", "registry/image@" + IMAGE])
def test_mutable_or_invalid_image_rejected(image):
    with pytest.raises(ValueError):
        DockerExecutor(image)


def test_policy_has_no_credential_or_output_mount(tmp_path):
    args = DockerExecutor(IMAGE).create_args("test", tmp_path, "bug", 1)
    for required in ("--read-only", "--network=none", "--cap-drop=ALL", "--pull=never", "--memory=256m",
                     "--memory-swap=256m", "--pids-limit=64", "--user=65534:65534"):
        assert required in args
    assert args.count("--mount") == 1
    assert "readonly" in args[args.index("--mount") + 1]
    assert not any("docker.sock" in arg or "--env-file" in arg for arg in args)


def test_unavailable_daemon_produces_sealed_infra_report(tmp_path, monkeypatch):
    executor = DockerExecutor(IMAGE)
    def unavailable(*args):
        raise OSError("simulated daemon unavailable")
    monkeypatch.setattr(executor, "control", unavailable)
    package = evaluate(DATA / "cases" / "good.json", tmp_path, executor)
    report = verify_package(package)
    assert report["status"] == "INFRA_ERROR" and report["checks"] == []
    assert "simulated daemon unavailable" in report["reason"]
    assert read_json(package / "inputs/environment.json")["container"]["image"] == IMAGE


def test_docker_does_not_admit_rehashed_unregistered_patch(tmp_path, monkeypatch):
    case, patch = load_case(DATA / "cases" / "good.json")
    changed = patch.replace(b"max(lower, min(value, upper))", b"value")
    assert changed != patch
    (tmp_path / "patch.diff").write_bytes(changed)
    write_json(tmp_path / "case.json", {**case.as_dict(), "patch": "patch.diff", "patch_sha256": digest(changed)})
    executor = DockerExecutor(IMAGE)
    calls = []
    monkeypatch.setattr(executor, "control", lambda args: calls.append(args))
    report = verify_package(evaluate(tmp_path / "case.json", tmp_path / "runs", executor))
    assert report["status"] == "EVALUATION_INTEGRITY_FAILED"
    assert "Unregistered patch" in report["reason"]
    assert not report["checks"] and not calls


def test_policy_mismatch_never_starts_container(tmp_path, monkeypatch):
    executor = DockerExecutor(IMAGE)
    calls = []
    def control(args):
        calls.append(args)
        if args[0] == "inspect":
            return '[{"Image":"wrong","HostConfig":{},"Config":{}}]'
        return ""
    monkeypatch.setattr(executor, "control", control)
    command = ["python", "-I", "-B", "worker", "source", "eval", "bug", str(tmp_path / "result.json"), "1"]
    result = executor.check(command, tmp_path, {}, 1, tmp_path / "run.log")
    assert result["error"]
    assert all(args[0] != "start" for args in calls)
    assert calls[-1][0:2] == ["rm", "--force"]


def test_create_timeout_attempts_cleanup(tmp_path, monkeypatch):
    executor = DockerExecutor(IMAGE)
    calls = []
    def control(args):
        calls.append(args)
        if args[0] == "create":
            raise subprocess.TimeoutExpired("docker", 15)
        return ""
    monkeypatch.setattr(executor, "control", control)
    result = executor.check(["p", "-I", "-B", "w", "s", "e", "bug", "r", "1"], tmp_path, {}, 1, tmp_path / "run.log")
    assert result["error"] and calls[-1][0:2] == ["rm", "--force"]


def config(folder):
    return {"Image": IMAGE, "Config": {"User": "65534:65534"}, "HostConfig": {
        "NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False, "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges:true"], "Memory": 268435456, "MemorySwap": 268435456,
        "NanoCpus": 1000000000, "PidsLimit": 64, "IpcMode": "private",
        "Tmpfs": {"/work": "rw,noexec,nosuid,nodev,size=67108864,mode=1777"},
        "Mounts": [{"Type": "bind", "ReadOnly": True, "Target": "/input", "Source": str(folder.resolve())}]}}


@pytest.mark.parametrize("key,value", [("NetworkMode", "host"), ("ReadonlyRootfs", False),
    ("Privileged", True), ("CapDrop", []), ("SecurityOpt", []), ("Memory", 0), ("MemorySwap", -1),
    ("NanoCpus", 0), ("PidsLimit", -1), ("PidMode", "host"), ("Devices", ["device"]),
    ("Binds", ["/home:/home"]), ("IpcMode", "host"), ("Tmpfs", {})])
def test_weakened_policy_is_rejected(tmp_path, key, value):
    spec = config(tmp_path)
    DockerExecutor.validate_config(spec, IMAGE, tmp_path)
    spec["HostConfig"][key] = value
    with pytest.raises(OSError, match="isolation policy"):
        DockerExecutor.validate_config(spec, IMAGE, tmp_path)


def test_transport_forgery_cannot_select_host_artifact_path(tmp_path, monkeypatch):
    executor = DockerExecutor(IMAGE)
    def control(args):
        return json.dumps([config(tmp_path)]) if args[0] == "inspect" else ""
    def fake_execute(command, folder, env, timeout, log):
        log.write_text(json.dumps({"exit_code": 0, "records": None, "junit": None, "log": "", "path": "../outside"}))
        return {"command": command, "exit_code": 0, "timeout": False, "duration_seconds": 0, "error": None}
    monkeypatch.setattr(executor, "control", control)
    monkeypatch.setattr("patchreplay.executors.execute", fake_execute)
    target = tmp_path / "result.json"
    result = executor.check(["p", "-I", "-B", "w", "s", "e", "bug", str(target), "1"], tmp_path, {}, 1, tmp_path / "run.log")
    assert result["error"] and not target.exists()
