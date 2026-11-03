from pathlib import Path
import shutil

import pytest

from patchreplay.claims import validate_report
from patchreplay.cli import main
from patchreplay.demo import EXPECTED, EXPECTED_CLAIMS
from patchreplay.engine import DATA, replay
from patchreplay.integrity import IntegrityError, read_json, tree_hash, verify_package


@pytest.mark.parametrize("name,expected", EXPECTED.items())
def test_demo_case_decisions(demo_run, name, expected):
    root, summary = demo_run
    row = next(c for c in summary["cases"] if c["case_id"] == name)
    assert row["actual"] == expected
    report = verify_package(root / row["package"])
    validate_report(root / row["package"], report)
    assert (root / row["package"] / "report.html").is_file()


@pytest.mark.parametrize("name,expected", EXPECTED_CLAIMS.items())
def test_demo_claim_decisions(demo_run, name, expected):
    _, summary = demo_run
    row = next(c for c in summary["claim_results"] if c["claim_id"] == name)
    assert row["status"] == expected


def test_success_has_exact_reproduced_failures_and_clean_regressions(good_package):
    report = read_json(good_package / "report.json")
    assert len(report["checks"]) == 8
    for row in report["checks"]:
        raw = read_json(good_package / row["records"])
        calls = [r for r in raw["records"] if r["when"] == "call"]
        if row["phase"] == "before_bug":
            assert len(calls) == 2
            assert all(c["exception"] == "AssertionError" and c["outcome"] == "failed" for c in calls)
        else:
            assert all(c["outcome"] == "passed" for c in calls)
        assert (good_package / row["junit"]).is_file()


def test_replay_preserves_original_and_input_identity(good_package, tmp_path):
    original = tree_hash(good_package)
    new = replay(good_package, tmp_path)
    before = read_json(good_package / "report.json")
    after = read_json(new / "report.json")
    assert before["run_id"] != after["run_id"]
    assert before["identities"] == after["identities"]
    assert before["status"] == after["status"]
    assert tree_hash(good_package) == original


def test_replay_rejects_engine_drift(good_package, tmp_path, monkeypatch):
    monkeypatch.setattr("patchreplay.engine.engine_files", lambda: {"changed.py": "0" * 64})
    with pytest.raises(IntegrityError, match="engine changed"):
        replay(good_package, tmp_path)


def test_replay_rejects_environment_drift(good_package, tmp_path, monkeypatch):
    monkeypatch.setattr("patchreplay.engine.environment", lambda: {"changed": True})
    with pytest.raises(IntegrityError, match="Environment changed"):
        replay(good_package, tmp_path)


def test_cli_integrity_and_no_overwrite(good_package, tmp_path):
    assert main(["verify", str(good_package)]) == 0
    assert main(["run", "not-a-case"]) == 2
    assert main(["examples", str(tmp_path)]) == 2
    assert main(["demo", "--output", str(good_package)]) == 2
    assert main(["run", "good", "--output", str(good_package / "nested")]) == 2


def test_render_escapes_untrusted_text(good_package, tmp_path):
    from patchreplay.reporting import render_report
    folder = tmp_path / "report"
    shutil.copytree(good_package, folder)
    report = read_json(folder / "report.json")
    report["title"] = '<script>alert("x")</script>'
    report["reason"] = '<img src=x onerror="alert(1)">'
    render_report(folder, report)
    html = (folder / "report.html").read_text()
    assert '<script>' not in html and '<img src=x' not in html
    assert '&lt;script&gt;' in html
    assert "Content-Security-Policy" in html
