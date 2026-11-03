from copy import deepcopy

import pytest

from patchreplay.contracts import CaseSpec, PHASES, Status, decide
from patchreplay.engine import DATA, interpret
from patchreplay.integrity import read_json


def observations():
    return [{"phase": p, "attempt": i, "outcome": "EXPECTED_FAILURE" if p == "before_bug" else "PASS", "signature": p}
            for i in (1, 2) for p in PHASES]


@pytest.mark.parametrize("phase,outcome,expected", [
    ("before_bug", "PASS", Status.NOT_REPRODUCED),
    ("before_bug", "FAIL", Status.INCONCLUSIVE),
    ("before_regression", "FAIL", Status.INCONCLUSIVE),
    ("after_bug", "FAIL", Status.FIX_FAILED),
    ("after_bug", "CHECK_ERROR", Status.FIX_FAILED),
    ("after_regression", "FAIL", Status.REGRESSION),
    ("after_regression", "TIMEOUT", Status.INCONCLUSIVE),
    ("after_bug", "INFRA_ERROR", Status.INFRA),
    ("before_bug", "INTEGRITY_ERROR", Status.INTEGRITY),
])
def test_decision_boundaries(phase, outcome, expected):
    rows = observations()
    for row in rows:
        if row["phase"] == phase:
            row["outcome"] = outcome
    assert decide(rows, 2)[0] == expected


def test_stable_success_and_disagreement():
    rows = observations()
    assert decide(rows, 2)[0] == Status.VERIFIED
    rows[-1]["signature"] = "different-records"
    assert decide(rows, 2)[0] == Status.INCONCLUSIVE


def test_missing_duplicate_and_integrity_precedence():
    rows = observations()
    assert decide(rows[:-1], 2)[0] == Status.INFRA
    rows[-1] = deepcopy(rows[3])
    assert decide(rows, 2)[0] == Status.INFRA
    rows[0]["outcome"] = "INTEGRITY_ERROR"
    rows[1]["outcome"] = "TIMEOUT"
    assert decide(rows, 2)[0] == Status.INTEGRITY


def record(outcome="passed", exception=None):
    return [{"node": "test.py::test_case", "when": phase,
             "outcome": outcome if phase == "call" else "passed", "exception": exception if phase == "call" else None}
            for phase in ("setup", "call", "teardown")]


def test_reproduction_requires_exact_assertion_failure():
    nodes = ["test.py::test_case"]
    for exception, expected in [("AssertionError", "EXPECTED_FAILURE"), ("ImportError", "FAIL"), ("TypeError", "FAIL")]:
        result = {"exit_code": 1, "records": record("failed", exception)}
        assert interpret(result, nodes, "before_bug", 1)[0] == expected
    assert interpret({"exit_code": 0, "records": []}, nodes, "after_bug", 0)[0] != "PASS"
    assert interpret({"exit_code": 5, "records": []}, nodes, "before_bug", 5)[0] == "CHECK_ERROR"


@pytest.mark.parametrize("change", ["skip", "duplicate", "unknown_node", "missing_call", "setup_error", "wrong_exit"])
def test_invalid_observations_never_pass(change):
    records = record()
    exit_code = 0
    if change == "skip":
        records[1]["outcome"] = "skipped"
    elif change == "duplicate":
        records.append(deepcopy(records[0]))
    elif change == "unknown_node":
        records[0]["node"] = "injected.py::test_other"
    elif change == "missing_call":
        records.pop(1)
    elif change == "setup_error":
        records[0]["outcome"] = "failed"
    elif change == "wrong_exit":
        exit_code = 3
    assert interpret({"exit_code": exit_code, "records": records}, ["test.py::test_case"], "after_bug", exit_code)[0] != "PASS"


@pytest.mark.parametrize("key,value", [("repeats", True), ("repeats", 0), ("repeats", 6),
                                      ("timeout_seconds", float("nan")), ("timeout_seconds", float("inf")),
                                      ("timeout_seconds", -1), ("schema_version", True),
                                      ("source_id", "../escape"), ("patch_sha256", "abc"), ("required_pytest", ">=8")])
def test_case_contract_rejects_ambiguous_values(key, value):
    data = read_json(DATA / "cases" / "good.json")
    data[key] = value
    with pytest.raises(ValueError):
        CaseSpec.parse(data)
