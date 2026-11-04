"""Opt-in Linux container acceptance tests. Skips are not an isolation pass."""
import json
import os
from pathlib import Path

import pytest

from patchreplay.engine import DATA, evaluate, replay
from patchreplay.executors import DockerExecutor
from patchreplay.integrity import read_json, verify_package
from patchreplay.claims import validate_report

pytestmark = pytest.mark.skipif(not os.environ.get("PATCHREPLAY_TEST_IMAGE"), reason="Requires built immutable Docker image and Linux daemon")


def test_live_container_controls(tmp_path, monkeypatch):
    executor = DockerExecutor(os.environ["PATCHREPLAY_TEST_IMAGE"])
    executor.preflight()
    monkeypatch.setenv("PATCHREPLAY_HOST_SECRET", "must-not-enter-container")
    probe = tmp_path / "probe.py"
    probe.write_text('''import os, socket, pathlib, json
assert os.getuid() == 65534
assert 'PATCHREPLAY_HOST_SECRET' not in os.environ
assert not pathlib.Path('/var/run/docker.sock').exists()
assert [name for _, name in socket.if_nameindex()] == ['lo']
for name in ['/root-write', '/input/modified']:
    try:
        pathlib.Path(name).write_text('unexpected')
    except OSError:
        pass
    else:
        raise AssertionError('Unexpected writable path: ' + name)
assert pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip() == '268435456'
assert pathlib.Path('/sys/fs/cgroup/pids.max').read_text().strip() == '64'
quota, period = pathlib.Path('/sys/fs/cgroup/cpu.max').read_text().split()
assert quota == period
status = pathlib.Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\\t1' in status and 'CapEff:\\t0000000000000000' in status
assert 'Seccomp:\\t2' in status
print('controls observed')
''', encoding="utf-8")
    # pytest creates private 0700 directories on Linux; this disposable input
    # mount must be readable by the deliberately unprivileged container user.
    tmp_path.chmod(0o755)
    probe.chmod(0o644)
    name = "patchreplay-probe-" + tmp_path.name.lower().replace("_", "-")
    args = executor.create_args(name, tmp_path, "bug", 1)
    args[-3:] = ["/input/probe.py"]
    try:
        executor.control(args)
        executor.validate_config(json.loads(executor.control(["inspect", name]))[0], executor.image, tmp_path)
        assert "controls observed" in executor.control(["start", "--attach", name])
    finally:
        executor.control(["rm", "--force", name])


@pytest.mark.parametrize("case,status", [("good", "VERIFIED_FOR_DECLARED_CHECKS"), ("regression", "REGRESSION_DETECTED"), ("timeout", "INCONCLUSIVE")])
def test_live_fixture_evaluation(tmp_path, case, status):
    executor = DockerExecutor(os.environ["PATCHREPLAY_TEST_IMAGE"])
    package = evaluate(DATA / "cases" / f"{case}.json", tmp_path, executor)
    report = read_json(package / "report.json")
    validate_report(package, verify_package(package))
    assert report["status"] == status
    assert report["executor"] == "docker-fixtures-v1"
    # Every created container name comes from the recorded create argv.
    for check in report["checks"]:
        command = check["command"]
        name = command[command.index("--name") + 1]
        assert not executor.control(["ps", "-aq", "--filter", "name=^/" + name + "$"]).strip()
    if case == "good":
        rerun = replay(package, tmp_path / "replays")
        repeated = verify_package(rerun)
        validate_report(rerun, repeated)
        assert repeated["status"] == status
        assert repeated["identities"] == report["identities"]
        assert repeated["run_id"] != report["run_id"]
