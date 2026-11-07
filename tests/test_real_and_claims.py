"""Pinned upstream admission and explicit function claim schema boundaries."""
import ast
import copy
from pathlib import Path
import shutil

import pytest

from patchreplay.claims import check_claim
from patchreplay.function import workflow as w
from patchreplay.function.contract import parse_case
from patchreplay.function.evidence import verify
from patchreplay.function_claims import draft, parse
from patchreplay.integrity import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "examples/function-evidence"


@pytest.mark.parametrize("name", ["boltons-fix", "boltons-noop", "boltons-regression", "lcm-fix", "lcm-noop", "lcm-regression"])
def test_reviewed_upstream_admission(name):
    case, oracle, suite, source, patch, patched = w.load_registered(name)
    assert case["schema_version"] == 2 and case["provenance_sha256"]
    ast.parse(source.decode())
    ast.parse(patched.decode())
    record = read_json(w.REAL_DATA / name / "provenance/record.json")
    assert len(record["before_commit"]) == len(record["fix_commit"]) == 40
    assert record["variant_origin"] == ("upstream-fix" if name.endswith("-fix") else "synthetic-control")


@pytest.mark.parametrize("file", ["source.py", "provenance/LICENSE", "provenance/adapter.py.txt", "oracle.json"])
def test_upstream_drift_rejected_before_execution(tmp_path, monkeypatch, file):
    data = tmp_path / "real"
    shutil.copytree(w.REAL_DATA, data)
    path = data / "lcm-fix" / file
    path.write_bytes(path.read_bytes() + b" \n")
    if file == "oracle.json":
        value = read_json(path)
        value["probes"][0]["baseline"] = -2
        write_json(path, value)
    monkeypatch.setattr(w, "REAL_DATA", data)
    with pytest.raises(ValueError):
        w.load_registered("lcm-fix")


def make_claim(tmp_path, cases, kind="regression_all"):
    packages=[]
    for name in cases:
        original = next(ARCHIVE.glob(name + "-*/manifest.json")).parent
        package = tmp_path / original.name
        shutil.copytree(original, package)
        packages.append(package)
    path = tmp_path / "claim.json"
    data = draft(packages, path, kind)
    return path, data


def approve(path, data):
    data["approval"] = "APPROVED_FOR_DECLARED_RULE"
    write_json(path, data)


def test_drafts_require_explicit_review(tmp_path):
    path, data = make_claim(tmp_path, ["good"])
    assert check_claim(path)["status"] == "INSUFFICIENT_EVIDENCE"
    approve(path, data)
    result = check_claim(path)
    assert result["status"] == "SUPPORTED_FOR_SCOPE" and result["observed"]["numerator"] == 1


@pytest.mark.parametrize("cases,status", [(["regression"], "CONTRADICTED"), (["good", "regression"], "CONTRADICTED"), (["timeout"], "INSUFFICIENT_EVIDENCE")])
def test_regression_claims_from_real_raw_packages(tmp_path, cases, status):
    path, data = make_claim(tmp_path, cases)
    approve(path, data)
    assert check_claim(path)["status"] == status


def test_success_scope_cannot_omit_unsuccessful_roster_members(tmp_path):
    path, data = make_claim(tmp_path, ["good"], "success_count")
    approve(path, data)
    assert "complete pinned suite" in check_claim(path)["reason"]


@pytest.mark.parametrize("change,status", [("missing", "INSUFFICIENT_EVIDENCE"), ("duplicate", "INSUFFICIENT_EVIDENCE"),
    ("identity", "STALE"), ("anchor", "INSUFFICIENT_EVIDENCE"), ("count", "CONTRADICTED"),
    ("bool", "INSUFFICIENT_EVIDENCE"), ("kind", "INSUFFICIENT_EVIDENCE"), ("path", "INSUFFICIENT_EVIDENCE")])
def test_function_claim_rejections(tmp_path, change, status):
    path, data = make_claim(tmp_path, ["good"])
    approve(path, data)
    if change == "missing": data["evidence"] = []
    elif change == "duplicate": data["evidence"] *= 2
    elif change == "identity": data["evidence"][0]["expected"]["engine_sha256"] = "0"*64
    elif change == "anchor": data["evidence"][0]["manifest_sha256"] = "0"*64
    elif change == "count": data["assertion"]["numerator"] = 0
    elif change == "bool": data["assertion"]["numerator"] = True
    elif change == "kind": data["evaluation_kind"] = "pytest"
    else: data["evidence"][0]["package"] = "../outside"
    write_json(path, data)
    assert check_claim(path)["status"] == status


def test_real_case_version_does_not_change_legacy_contract():
    case = read_json(w.DATA / "good/case.json")
    assert parse_case(case) == case
    case["provenance_sha256"] = "0"*64
    with pytest.raises(ValueError): parse_case(case)
