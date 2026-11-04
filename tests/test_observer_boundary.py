"""Host-side protocol/transport checks; no candidate code runs on the host."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.observer_boundary.host import MAX_RESPONSE, capture, judge, observe
from patchreplay.executors import DockerExecutor

IMAGE = "sha256:" + "a" * 64


def answer(**changes):
    return json.dumps({"protocol": 1, "request_id": "this-round", "value": 0, **changes}).encode()


def test_host_owns_answer_comparison():
    assert judge(answer(), "this-round", 0)["outcome"] == "MATCH"
    assert judge(answer(value=999), "this-round", 0)["outcome"] == "MISMATCH"


@pytest.mark.parametrize("raw", [
    b"", b"null", b"[]", b"\xff", b"x" * (MAX_RESPONSE + 1),
    answer(status="PASS"), answer(request_id="previous-round"),
    answer(protocol=True), answer(protocol=2), answer(value=True), answer(value=0.0),
    answer(value=2**60), answer(value=float("nan")), answer(value=float("inf")),
    answer() + b"\n" + answer(), b'{"protocol":1,"request_id":"this-round","value":999,"value":0}',
    b'{"protocol":1,"request_id":"this-round"}', b"[" * 2000 + b"]" * 2000,
])
def test_untrusted_responses_never_match(raw):
    assert judge(raw, "this-round", 0)["outcome"] == "INVALID_RESPONSE"


def test_response_does_not_authorize_a_different_request():
    assert judge(answer(), "next-round", 0)["outcome"] == "INVALID_RESPONSE"


def test_capture_bounds_live_output():
    result = capture([sys.executable, "-c", "import os; os.write(1, b'x' * 100000)"], 5)
    assert result["overflow"] and len(result["raw"]) == MAX_RESPONSE + 1


def test_capture_times_out_disconnected_producer():
    result = capture([sys.executable, "-c", "import time; time.sleep(30)"], .2)
    assert result["timeout"]


def test_capture_preserves_exit_code():
    result = capture([sys.executable, "-c", "print('response'); raise SystemExit(3)"], 5)
    assert result["exit_code"] == 3 and result["raw"].strip() == b"response"


def test_external_source_never_reaches_docker(monkeypatch):
    calls = []
    monkeypatch.setattr(DockerExecutor, "preflight", lambda self: calls.append("docker"))
    with pytest.raises(ValueError, match="registered"):
        observe(IMAGE, "C:/unreviewed/source.py", 0)
    assert not calls


def test_guest_mount_has_no_oracle_and_host_checks_exit_status(monkeypatch, tmp_path):
    monkeypatch.setattr(DockerExecutor, "preflight", lambda self: None)
    monkeypatch.setattr(DockerExecutor, "validate_config", lambda *args: None)
    request = {}
    def control(self, args):
        if args[0] == "create":
            mount = args[args.index("--mount") + 1]
            folder = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
            assert {p.name for p in folder.iterdir()} == {"candidate.py", "guest.py"}
            request.update(json.loads(args[-1]))
            assert set(request) == {"protocol", "request_id", "args"}
        return "[{}]" if args[0] == "inspect" else ""
    monkeypatch.setattr(DockerExecutor, "control", control)
    monkeypatch.setattr("experiments.observer_boundary.host.capture", lambda *args: {
        "raw": answer(request_id=request["request_id"]), "exit_code": 1, "timeout": False, "overflow": False})
    result = observe(IMAGE, "correct", 0, workspace=tmp_path)
    assert result["outcome"] == "EXECUTION_ERROR" and result["container_removed"]


@pytest.mark.parametrize("failure", ["create", "cleanup"])
def test_lifecycle_failure_cannot_match(monkeypatch, failure):
    calls = []
    monkeypatch.setattr(DockerExecutor, "preflight", lambda self: None)
    monkeypatch.setattr(DockerExecutor, "validate_config", lambda *args: None)
    def control(self, args):
        calls.append(args)
        if (failure == "create" and args[0] == "create") or (failure == "cleanup" and args[0] == "rm"):
            raise subprocess.TimeoutExpired("docker", 15)
        return "[{}]" if args[0] == "inspect" else ""
    monkeypatch.setattr(DockerExecutor, "control", control)
    def fake_capture(command, timeout):
        request_id = command[-1].removeprefix("patchreplay-oracle-")
        return {"raw": answer(request_id=request_id), "exit_code": 0, "timeout": False, "overflow": False}
    monkeypatch.setattr("experiments.observer_boundary.host.capture", fake_capture)
    result = observe(IMAGE, "correct", 0)
    assert result["outcome"] == "INFRA_ERROR"
    assert calls[-1][:2] == ["rm", "--force"]
