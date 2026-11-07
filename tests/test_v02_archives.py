"""Offline guards for actual 0.2 observations, claims, source scope and signatures."""
from pathlib import Path
import subprocess

import pytest

from patchreplay.claims import check_claim
from patchreplay.function.evidence import verify
from patchreplay.integrity import read_json

ROOT = Path(__file__).resolve().parents[1] / "examples/v02-evidence"


def deny(*args, **kwargs):
    raise AssertionError("Archived evidence verification must remain offline")


def test_v02_packages_and_claims_without_execution(monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", deny)
    summary = read_json(ROOT / "demo/results.json")
    assert summary["expected_outcomes_matched"]
    reports = [verify(p.parent) for p in (ROOT / "demo").rglob("report.json")]
    assert len(reports) == 8 and len({r["run_id"] for r in reports}) == 8
    assert len([r for r in reports if r["status"] == "VERIFIED_FOR_DECLARED_CHECKS"]) == 4
    for kind in ("success_count", "regression_all"):
        assert check_claim(ROOT / "demo" / (kind + ".json"))["status"] == "SUPPORTED_FOR_SCOPE"


def test_real_provenance_reports_distinguish_controls():
    for p in (ROOT / "demo/runs").glob("*/inputs/provenance/record.json"):
        record = read_json(p)
        expected = "synthetic-control" if record["variant"] != "fix" else "upstream-fix"
        assert record["variant_origin"] == expected
        assert "not the complete upstream" in record["scope"]


def test_v02_signed_real_subject_offline(monkeypatch):
    pytest.importorskip("cryptography")
    from patchreplay_provenance import core
    monkeypatch.setattr(subprocess, "Popen", deny)
    base = ROOT / "provenance"
    result = core.verify(base / "bundle", base / "trust/public.pem", base / "trust/expected.json")
    assert result["status"] == "AUTHENTICATED_FOR_EXPECTED_SUBJECT"
    assert result["run_id"].startswith("boltons-fix-")
