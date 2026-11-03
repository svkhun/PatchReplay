import json
import os
from pathlib import Path
import shutil
import sys
import time

import pytest

from patchreplay.engine import DATA, approved_inputs, load_case
from patchreplay.integrity import IntegrityError, identity, patch_paths, read_json, safe_path, tree_hash, verify_package, write_json
from patchreplay.process import clean_environment, execute


@pytest.mark.parametrize("path", ["../outside", "/absolute", "C:/outside", "a\\b", "a/../b", "a//b", "./a", "file:stream", "NUL.txt", "a/CON", "a.", "a ", "a\nfile"])
def test_cross_platform_path_rejection(tmp_path, path):
    with pytest.raises(IntegrityError):
        safe_path(tmp_path, path)


@pytest.mark.parametrize("patch", [
    b"diff --git a/../escape b/../escape\n",
    b"diff --git a/clamp.py b/clamp.py\nnew mode 120000\n",
    b"diff --git a/clamp.py b/clamp.py\n--- a/other.py\n+++ b/clamp.py\n",
    b"diff --git a/clamp.py b/renamed.py\n",
    b'diff --git "a/clamp.py" "b/clamp.py"\n',
    b"diff --git a/clamp.py b/clamp.py\nGIT binary patch\n",
    b"diff --git a/clamp.py b/clamp.py\nnew file mode 100644\n",
    b"not a diff", b"\xff\x00",
])
def test_patch_formats_fail_closed(patch):
    with pytest.raises(IntegrityError):
        patch_paths(patch)


def test_known_patch_and_protected_evaluator():
    case, patch = load_case(DATA / "cases" / "good.json")
    assert patch_paths(patch) == {"clamp.py"}
    approved_inputs(case, patch)
    case, patch = load_case(DATA / "cases" / "protected.json")
    with pytest.raises(IntegrityError, match="protected"):
        approved_inputs(case, patch)


def test_changed_patch_and_evaluator_are_rejected():
    from dataclasses import replace
    from patchreplay.integrity import digest
    case, patch = load_case(DATA / "cases" / "good.json")
    with pytest.raises(IntegrityError, match="hash"):
        approved_inputs(case, patch + b"\n")
    with pytest.raises(IntegrityError, match="evaluator"):
        approved_inputs(replace(case, evaluator_sha256="0" * 64), patch)
    changed = patch.replace(b"max(lower, min(value, upper))", b"__import__('os').getcwd()")
    with pytest.raises(IntegrityError, match="Unregistered"):
        approved_inputs(replace(case, patch_sha256=digest(changed)), changed)


def test_install_time_bytecode_does_not_change_fixture_identity(tmp_path, monkeypatch):
    import compileall
    from patchreplay.integrity import fixture_hash
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    source = data / "sources" / "clamp-buggy-v1"
    before = fixture_hash(source)
    assert compileall.compile_dir(str(data), quiet=1)
    assert list(source.rglob("*.pyc"))
    assert fixture_hash(source) == before
    monkeypatch.setattr("patchreplay.engine.DATA", data)
    case, patch = load_case(data / "cases" / "good.json")
    approved_inputs(case, patch)


def test_link_rejected(tmp_path):
    target = tmp_path / "target"
    target.write_text("data")
    link = tmp_path / "link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Creating symlinks requires privileges on this host")
    with pytest.raises(IntegrityError):
        safe_path(tmp_path, "link")


def test_duplicate_json_keys_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"status":"PASS","status":"FAIL"}')
    with pytest.raises(ValueError, match="Duplicate"):
        read_json(path)


def test_canonical_artifacts_and_fixture_metadata_use_lf(tmp_path):
    path = tmp_path / "portable.json"
    write_json(path, {"source": "fixture", "nested": {"version": 1}})
    assert b"\r" not in path.read_bytes()
    for path in DATA.rglob("*.json"):
        assert b"\r" not in path.read_bytes(), str(path)


def test_clean_environment_does_not_inherit_secrets_or_plugins(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-sentinel-not-a-real-secret")
    monkeypatch.setenv("PYTHONPATH", "untrusted")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--force-injected-config")
    env = clean_environment(tmp_path / "home")
    assert not {"OPENAI_API_KEY", "PYTHONPATH", "PYTEST_ADDOPTS", "PATH", "SSH_AUTH_SOCK"}.intersection(env)
    log = tmp_path / "env.log"
    result = execute([sys.executable, "-I", "-c", "import os,json;print(json.dumps(dict(os.environ)))"], tmp_path, env, 5, log)
    assert result["exit_code"] == 0
    assert "unit-test-sentinel" not in log.read_text()
    assert "force-injected" not in log.read_text()


def test_timeout_terminates_descendant(tmp_path):
    marker = tmp_path / "child-survived.txt"
    child = f"import time; from pathlib import Path; time.sleep(1.5); Path({str(marker)!r}).write_text('survived')"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-I','-c',{child!r}]); time.sleep(20)"
    result = execute([sys.executable, "-I", "-c", parent], tmp_path, clean_environment(tmp_path / "home"), 0.5, tmp_path / "timeout.log")
    assert result["timeout"]
    time.sleep(1.6)
    assert not marker.exists()


def test_spawn_failure_is_an_infrastructure_observation(tmp_path):
    result = execute([str(tmp_path / "missing-executable")], tmp_path, clean_environment(tmp_path / "home"), 1, tmp_path / "failure.log")
    assert result["error"] and result["exit_code"] is None and not result["timeout"]


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object lifecycle")
def test_job_assignment_failure_never_resumes_code(tmp_path, monkeypatch):
    from patchreplay.windows_job import WindowsJob
    def fail_assignment(self, pid):
        raise OSError("simulated assignment failure")
    monkeypatch.setattr(WindowsJob, "assign_and_resume", fail_assignment)
    marker = tmp_path / "must-not-execute.txt"
    command = [sys.executable, "-I", "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"]
    result = execute(command, tmp_path, clean_environment(tmp_path / "home"), 2, tmp_path / "job.log")
    assert "simulated assignment failure" in result["error"]
    assert not marker.exists()
