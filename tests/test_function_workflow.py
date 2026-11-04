"""Host-function admission, semantics, hostile transport, evidence and replay."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from patchreplay.cli import main
from patchreplay.executors import DockerExecutor
from patchreplay.function import workflow as w, transport as t
from patchreplay.function.contract import POLICY, decide, schedule
from patchreplay.function.evidence import verify, render
from patchreplay.integrity import digest, read_json, seal_package, write_json

IMAGE = "sha256:" + "a" * 64


@pytest.fixture
def fake_docker(monkeypatch):
    """Mock only Docker I/O. Admission, Git patching, parser and host verdict are real."""
    state = {"calls": [], "mode": None}
    env = {"host": {"test": "controlled mock, not live acceptance"}, "docker": {"ServerVersion": "mock"},
           "image": {"Id": IMAGE, "Os": "linux", "Architecture": "test"}}
    monkeypatch.setattr(w, "runtime_environment", lambda executor: copy.deepcopy(env))
    monkeypatch.setattr(DockerExecutor, "validate_config", lambda *args: None)
    def control(self, args):
        state["calls"].append(args)
        if state["mode"] == args[0]:
            raise OSError("injected " + args[0] + " failure")
        if args[0] == "create":
            mount = args[args.index("--mount") + 1]
            folder = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
            assert {p.name for p in folder.iterdir()} == {"candidate.py", "guest.py"}
            state["source"] = (folder / "candidate.py").read_bytes()
            state["folder"] = folder
            state["request"] = json.loads(args[-1])
            assert set(state["request"]) == {"protocol", "request_id", "args"}
            assert "test-signing-secret" not in str(args)
        return "[{}]" if args[0] == "inspect" else ""
    monkeypatch.setattr(DockerExecutor, "control", control)
    def capture(command, timeout):
        request = state["request"]
        value, lower, upper = request["args"]
        source = state["source"].decode()
        # Fixed test-double arithmetic, not eval/exec/import of candidate bytes.
        if "upper - 1" in source:
            result = min(value, upper - 1)
        elif "max(lower, min" in source:
            result = max(lower, min(value, upper))
        elif "max(0," in source:
            result = max(0, min(value, upper))
        elif "max(lower, value)" in source:
            result = max(lower, value)
        else:
            result = min(value, upper)
        raw = json.dumps({"protocol": 1, "request_id": request["request_id"], "value": result}).encode()
        return {"raw": raw, "exit_code": 0, "timeout": False, "overflow": False}
    state["capture"] = capture
    state["env"] = env
    monkeypatch.setattr(t, "capture", capture)
    monkeypatch.setenv("PATCHREPLAY_SIGNING_PASSWORD", "test-signing-secret")
    return state


@pytest.mark.parametrize("case,status", [
    ("good", "VERIFIED_FOR_DECLARED_CHECKS"), ("incorrect", "FIX_FAILED"), ("narrow", "FIX_FAILED"),
    ("regression", "REGRESSION_DETECTED"), ("already-fixed", "BUG_NOT_REPRODUCED"),
    ("baseline-regression", "BASELINE_REGRESSION_FAILED"),
])
def test_integrated_semantics(tmp_path, fake_docker, case, status):
    root = w.evaluate(case, IMAGE, tmp_path)
    report = verify(root)
    assert report["status"] == status
    assert len(report["observations"]) == 16
    assert len({r["request"]["request_id"] for r in report["observations"]}) == 16
    assert all(r["container_removed"] for r in report["observations"])
    assert "Host-owned function" in (root / "report.html").read_text()


@pytest.fixture
def good(tmp_path, fake_docker):
    return w.evaluate("good", IMAGE, tmp_path / "runs")


def rewrite_report(root, report, html=True):
    write_json(root / "report.json", report)
    if html:
        (root / "report.html").write_text(render(report, read_json(root / "inputs/case.json"),
                                              read_json(root / "inputs/oracle.json")), encoding="utf-8")
    seal_package(root)


@pytest.mark.parametrize("change", ["verdict", "value", "missing", "duplicate", "request", "html", "source", "engine", "oracle", "policy", "command", "image", "repeats"])
def test_resealed_inconsistent_packages_fail(good, change):
    report = read_json(good / "report.json")
    if change == "verdict":
        report["status"] = "FIX_FAILED"
    elif change == "value":
        report["observations"][0]["observation"]["value"] = 99
    elif change == "missing":
        report["observations"].pop()
    elif change == "duplicate":
        report["observations"][1] = report["observations"][0]
    elif change == "request":
        report["observations"][0]["request"]["request_id"] = "b" * 32
    elif change == "command":
        report["observations"][0]["command"][3] = "--network=host"
    elif change == "image":
        report["identities"]["image"] = "sha256:" + "b" * 64
    elif change in {"source", "engine", "oracle", "policy", "repeats"}:
        paths = {"source": "inputs/source.py", "engine": "inputs/engine-source/cli.py",
                 "oracle": "inputs/oracle.json", "policy": "inputs/policy.json", "repeats": "inputs/case.json"}
        path = good / paths[change]
        if change in {"source", "engine"}:
            path.write_bytes(path.read_bytes() + b"# drift\n")
        else:
            data = read_json(path)
            if change == "oracle":
                data["probes"][0]["expected"] = 99
            elif change == "policy":
                data["network"] = "host"
            else:
                data["repeats"] = 3
            write_json(path, data)
    rewrite_report(good, report, html=change != "html")
    if change == "html":
        (good / "report.html").write_text("Forged PASS", encoding="utf-8")
        seal_package(good)
    with pytest.raises((ValueError, KeyError)):
        verify(good)


def test_replay_new_identity_and_unchanged_original(good, tmp_path, fake_docker):
    before = (good / "manifest.json").read_bytes()
    replay = w.replay(good, tmp_path / "replays")
    first, second = verify(good), verify(replay)
    assert first["run_id"] != second["run_id"]
    assert first["identities"] == second["identities"]
    assert before == (good / "manifest.json").read_bytes()


@pytest.mark.parametrize("change", ["engine", "environment", "image", "case", "oracle"])
def test_replay_drift_blocks_execution(good, tmp_path, fake_docker, monkeypatch, change):
    fake_docker["calls"].clear()
    if change == "engine":
        monkeypatch.setattr(w, "engine_files", lambda: {"changed.py": "0" * 64})
    elif change in {"environment", "image"}:
        fake_docker["env"]["docker" if change == "environment" else "image"]["drift"] = True
    else:
        original = w.load_registered
        def changed(name):
            result = list(original(name))
            if change == "case":
                result[0]["repeats"] = 3
            else:
                raise ValueError("Registered evaluator drift")
            return tuple(result)
        monkeypatch.setattr(w, "load_registered", changed)
    with pytest.raises(ValueError):
        w.replay(good, tmp_path / "replay")
    assert not fake_docker["calls"]


@pytest.mark.parametrize("raw", [b"", b"null", b"\xff", b"{}", b"[]", b"x" * 4097,
    b'{"protocol":1,"request_id":"ID","value":0,"status":"PASS"}',
    b'{"records":[{"outcome":"passed"}]}',
    b'{"protocol":1,"request_id":"wrong","value":0}',
    b'{"protocol":1,"request_id":"ID","value":0}\n{"value":0}',
    b'{"protocol":1,"request_id":"ID","value":0,"value":1}',
    b'{"protocol":1,"request_id":"ID","value":true}',
    b'{"protocol":1,"request_id":"ID","value":NaN}',
])
def test_forged_and_invalid_transport(tmp_path, fake_docker, monkeypatch, raw):
    def capture(*args):
        value = raw.replace(b"ID", fake_docker["request"]["request_id"].encode())
        return {"raw": value, "exit_code": 0, "timeout": False, "overflow": len(value) > 4096}
    monkeypatch.setattr(t, "capture", capture)
    report = verify(w.evaluate("good", IMAGE, tmp_path))
    assert report["status"] == "INVALID_RESPONSE"


@pytest.mark.parametrize("failure,status", [("timeout", "TIMEOUT"), ("exit", "EXECUTION_ERROR"),
    ("create", "INFRA_ERROR"), ("rm", "INFRA_ERROR"), ("input", "INTEGRITY_ERROR"), ("repeat", "REPEAT_DISAGREEMENT")])
def test_execution_failures(tmp_path, fake_docker, monkeypatch, failure, status):
    fake_docker["mode"] = failure
    count = 0
    def capture(*args):
        nonlocal count
        count += 1
        result = fake_docker["capture"](*args)
        if failure == "timeout":
            result["timeout"] = True
        elif failure == "exit":
            result["exit_code"] = 1
        elif failure == "input":
            (fake_docker["folder"] / "candidate.py").write_text("changed")
        elif failure == "repeat" and count == 9:
            value = json.loads(result["raw"])
            value["value"] = -3
            result["raw"] = json.dumps(value).encode()
        return result
    monkeypatch.setattr(t, "capture", capture)
    report = verify(w.evaluate("good", IMAGE, tmp_path))
    assert report["status"] == status
    if failure == "rm":
        assert len(report["observations"]) == 1 and report["failure"]["stage"] == "execution"


def test_no_docker_fallback(tmp_path, fake_docker, monkeypatch):
    def unavailable(executor):
        raise OSError("Docker unavailable")
    monkeypatch.setattr(w, "runtime_environment", unavailable)
    root = w.evaluate("good", IMAGE, tmp_path)
    assert verify(root)["status"] == "INFRA_ERROR"
    assert not fake_docker["calls"]


def test_cli_registered_only_and_dispatch(good, tmp_path, fake_docker, capsys):
    assert main(["function-list"]) == 0
    assert "good" in capsys.readouterr().out
    assert main(["function-run", "../../candidate", "--image", IMAGE, "--output", str(tmp_path)]) == 2
    assert main(["function-run", "good", "--image", "latest", "--output", str(tmp_path)]) == 2
    assert main(["verify", str(good)]) == 0
    assert main(["replay", str(good), "--output", str(tmp_path / "cli-replay")]) == 0
    assert main(["function-run", "incorrect", "--image", IMAGE, "--output", str(tmp_path / "bad")]) == 1
    from patchreplay.claims import validate_report
    with pytest.raises(ValueError, match="schema"):
        validate_report(good, read_json(good / "report.json"))


@pytest.mark.parametrize("file", ["oracle.json", "good/source.py", "good/patch.diff", "good/case.json", "suite.json"])
def test_admission_drift_never_executes(tmp_path, fake_docker, monkeypatch, file):
    import shutil
    data = tmp_path / "fixtures"
    shutil.copytree(w.DATA, data)
    path = data / file
    if path.suffix == ".json":
        value = read_json(path)
        value["unreviewed"] = True
        write_json(path, value)
    else:
        path.write_bytes(path.read_bytes() + b"# changed\n")
    monkeypatch.setattr(w, "DATA", data)
    with pytest.raises(ValueError):
        w.evaluate("good", IMAGE, tmp_path / "runs")
    assert not fake_docker["calls"]


def test_bounded_capture_and_timeout():
    result = t.capture([sys.executable, "-c", "import os; os.write(1, b'x' * 100000)"], 5)
    assert result["overflow"] and len(result["raw"]) == 4097
    assert t.capture([sys.executable, "-c", "import time; time.sleep(30)"], .2)["timeout"]


@pytest.mark.parametrize("case", ["good", "regression"])
def test_function_provenance_roundtrip_and_external_expectation(tmp_path, fake_docker, case):
    pytest.importorskip("cryptography")
    good = w.evaluate(case, IMAGE, tmp_path / "subject")
    from patchreplay_provenance import core
    private, public = tmp_path / "private.pem", tmp_path / "public.pem"
    password = b"ephemeral-test-password-only"
    core.keygen(private, public, password)
    expected = tmp_path / "expected.json"
    core.prepare(good, "host-function-v1", expected)
    bundle = tmp_path / "bundle"
    core.sign(good, expected, private, password, bundle)
    assert core.verify(bundle, public, expected)["status"] == "AUTHENTICATED_FOR_EXPECTED_SUBJECT"
    value = core.load(expected)
    value["run_id"] = "another-expected-run"
    write_json(tmp_path / "wrong.json", value)
    with pytest.raises(ValueError, match="externally expected"):
        core.verify(bundle, public, tmp_path / "wrong.json")
    with pytest.raises(ValueError):
        core.prepare(good, "patchreplay-v1", tmp_path / "wrong-kind.json")


def test_function_schema_shapes(good):
    from patchreplay.function.contract import CASE_KEYS
    from patchreplay.function.evidence import REPORT_KEYS, ROW_KEYS
    schemas = Path(__file__).resolve().parents[1] / "schemas"
    case_schema = read_json(schemas / "function-case.schema.json")
    schema = read_json(schemas / "function-report.schema.json")
    assert set(case_schema["required"]) == CASE_KEYS
    assert set(schema["required"]) == REPORT_KEYS
    assert set(schema["properties"]["observations"]["items"]["required"]) == ROW_KEYS
    assert set(read_json(good / "report.json")) == REPORT_KEYS


@pytest.mark.parametrize("change", [{"protocol": True}, {"protocol": 2}, {"value": 0.0},
                                    {"value": 2**53}, {"value": float("inf")}])
def test_protocol_types_and_numeric_bounds(change):
    raw = json.dumps({"protocol": 1, "request_id": "round", "value": 0, **change}).encode()
    assert t.judge(raw, "round", 0)["outcome"] == "INVALID_RESPONSE"


def test_patch_preparation_failure_is_not_a_bug(tmp_path, fake_docker, monkeypatch):
    def failure(*args):
        raise OSError("Git unavailable")
    monkeypatch.setattr(w, "apply_patch", failure)
    report = verify(w.evaluate("good", IMAGE, tmp_path))
    assert report["status"] == "INFRA_ERROR" and report["failure"]["stage"] == "patch"
    assert not fake_docker["calls"]


def test_same_mismatch_does_not_prove_declared_bug(tmp_path, fake_docker, monkeypatch):
    def capture(*args):
        result = fake_docker["capture"](*args)
        value = json.loads(result["raw"])
        if value["value"] == -2:
            value["value"] = -3
        result["raw"] = json.dumps(value).encode()
        return result
    monkeypatch.setattr(t, "capture", capture)
    assert verify(w.evaluate("good", IMAGE, tmp_path))["status"] == "BUG_NOT_REPRODUCED"


def test_replay_rechecks_resolved_identity_before_execution(good, tmp_path, fake_docker, monkeypatch):
    count = 0
    def changed(executor):
        nonlocal count
        count += 1
        result = copy.deepcopy(fake_docker["env"])
        if count > 1:
            result["host"]["drift"] = True
        return result
    monkeypatch.setattr(w, "runtime_environment", changed)
    fake_docker["calls"].clear()
    report = verify(w.replay(good, tmp_path / "replays"))
    assert report["status"] == "INTEGRITY_ERROR"
    assert "between verification and execution" in report["reason"]
    assert not fake_docker["calls"]


def test_environment_drift_after_execution_cannot_pass(tmp_path, fake_docker, monkeypatch):
    count = 0
    def changed(executor):
        nonlocal count
        count += 1
        result = copy.deepcopy(fake_docker["env"])
        if count > 1:
            result["host"]["drift"] = True
        return result
    monkeypatch.setattr(w, "runtime_environment", changed)
    assert verify(w.evaluate("good", IMAGE, tmp_path))["status"] == "INTEGRITY_ERROR"


def test_archived_function_packages_are_offline_and_consistent(monkeypatch):
    root = Path(__file__).resolve().parents[1] / "examples/function-evidence"
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline verification must not start a subprocess")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    packages = sorted(root.glob("*/manifest.json"))
    assert len(packages) == 3
    assert {verify(p.parent)["status"] for p in packages} == {
        "VERIFIED_FOR_DECLARED_CHECKS", "REGRESSION_DETECTED", "TIMEOUT"}


def test_archived_function_provenance_is_offline(monkeypatch):
    pytest.importorskip("cryptography")
    from patchreplay_provenance import core
    root = Path(__file__).resolve().parents[1] / "examples/function-evidence/provenance"
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline provenance must not start a subprocess")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert core.verify(root / "bundle", root / "trust/public.pem", root / "trust/expected.json")["status"] == "AUTHENTICATED_FOR_EXPECTED_SUBJECT"
