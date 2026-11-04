"""Opt-in real Docker acceptance. Skips never count as live passes."""
import os
from pathlib import Path

import pytest

from patchreplay.function.workflow import evaluate, replay
from patchreplay.function.evidence import verify

IMAGE = os.environ.get("PATCHREPLAY_TEST_IMAGE")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Set PATCHREPLAY_TEST_IMAGE for real Docker acceptance")


@pytest.mark.parametrize("case,status", [
    ("good", "VERIFIED_FOR_DECLARED_CHECKS"), ("incorrect", "FIX_FAILED"), ("narrow", "FIX_FAILED"),
    ("regression", "REGRESSION_DETECTED"), ("already-fixed", "BUG_NOT_REPRODUCED"),
    ("baseline-regression", "BASELINE_REGRESSION_FAILED"), ("forge-records", "INVALID_RESPONSE"),
    ("forge-status", "INVALID_RESPONSE"), ("duplicate", "INVALID_RESPONSE"),
    ("wrong-round", "INVALID_RESPONSE"), ("disconnect", "INVALID_RESPONSE"),
    ("flood", "INVALID_RESPONSE"), ("timeout", "TIMEOUT"),
])
def test_real_function_workflow(tmp_path, case, status):
    root = evaluate(case, IMAGE, tmp_path)
    report = verify(root)
    assert report["status"] == status
    assert len(report["observations"]) == 16
    assert all(r["container_removed"] for r in report["observations"])
    if case == "good":
        original = (root / "manifest.json").read_bytes()
        second = verify(replay(root, tmp_path / "replays"))
        assert second["status"] == status and second["run_id"] != report["run_id"]
        assert second["identities"] == report["identities"]
        assert (root / "manifest.json").read_bytes() == original
