from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from patchreplay.claims import check_claim
from patchreplay.integrity import digest, read_json, seal_package, write_json


def claim_copy(demo_run, tmp_path, name="regression-supported"):
    root, _ = demo_run
    data = read_json(root / f"claim-{name}.json")
    path = tmp_path / "claim.json"
    write_json(path, data)
    return root, data, path


@pytest.mark.parametrize("mutation", ["numerator", "denominator", "missing", "duplicate", "policy", "bool_count", "extra_scope", "traversal"])
def test_claim_fail_closed(demo_run, tmp_path, mutation):
    root, data, path = claim_copy(demo_run, tmp_path, "suite-supported")
    expected = "INSUFFICIENT_EVIDENCE"
    if mutation in ("numerator", "denominator"):
        data["assertion"][mutation] += 1
        expected = "CONTRADICTED"
    elif mutation == "missing":
        data["evidence"].pop()
    elif mutation == "duplicate":
        data["evidence"][-1] = deepcopy(data["evidence"][0])
    elif mutation == "policy":
        data["assertion"]["denominator_policy"] = "exclude_errors"
    elif mutation == "bool_count":
        data["assertion"]["numerator"] = True
    elif mutation == "extra_scope":
        data["scope"]["case_ids"].append("undeclared")
    elif mutation == "traversal":
        data["evidence"][0]["package"] = "../escape"
    write_json(path, data)
    assert check_claim(path, root)["status"] == expected


@pytest.mark.parametrize("key", ["source_revision", "patch_sha256", "evaluator_sha256", "suite_sha256", "environment_sha256", "engine_sha256", "case_sha256", "inputs_sha256"])
def test_changed_expected_inputs_are_stale(demo_run, tmp_path, key):
    root, data, path = claim_copy(demo_run, tmp_path)
    data["evidence"][0]["expected"][key] = ("sha256:" if key == "source_revision" else "") + "0" * 64
    write_json(path, data)
    assert check_claim(path, root)["status"] == "STALE"


@pytest.mark.parametrize("mutation", ["changed_log", "missing_log", "added_file", "changed_report", "rehashed_forgery"])
def test_artifact_tampering_is_detected(demo_run, tmp_path, mutation):
    root, data, path = claim_copy(demo_run, tmp_path)
    ref = data["evidence"][0]
    folder = tmp_path / ref["package"]
    shutil.copytree(root / ref["package"], folder)
    report = read_json(folder / "report.json")
    log = folder / report["checks"][0]["log"]
    if mutation == "changed_log":
        log.write_text("silently replaced")
    elif mutation == "missing_log":
        log.unlink()
    elif mutation == "added_file":
        (folder / "extra.txt").write_text("not in manifest")
    elif mutation == "changed_report":
        report["status"] = "FIX_FAILED"
        write_json(folder / "report.json", report)
    else:
        report["checks"][0]["outcome"] = "PASS"
        write_json(folder / "report.json", report)
        # Even a newly anchored manifest cannot make a verdict consistent with conflicting raw records.
        ref["manifest_sha256"] = seal_package(folder)
    write_json(path, data)
    assert check_claim(path, tmp_path)["status"] == "INSUFFICIENT_EVIDENCE"


def test_full_suite_denominator_includes_errors_and_inconclusive(demo_run):
    root, _ = demo_run
    result = check_claim(root / "claim-suite-supported.json")
    assert result["observed"] == {"numerator": 1, "denominator": 10, "denominator_policy": "all_declared_cases"}
    assert result["excluded_from_numerator"]["INFRA_ERROR"] == 1
    assert result["excluded_from_numerator"]["INCONCLUSIVE"] == 2


def test_suite_claim_cannot_cherry_pick_success(demo_run, tmp_path):
    root, data, path = claim_copy(demo_run, tmp_path, "suite-supported")
    data["scope"]["case_ids"] = ["good"]
    data["evidence"] = data["evidence"][:1]
    data["assertion"]["denominator"] = 1
    write_json(path, data)
    assert check_claim(path, root)["status"] == "INSUFFICIENT_EVIDENCE"
