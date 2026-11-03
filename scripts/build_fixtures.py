"""Maintainer-only fixture authoring. Review changes to this file and catalog together.

No downloaded code, model output, or real project measurements are used here.
"""

from pathlib import Path
import difflib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from patchreplay.integrity import digest, identity, tree_hash, write_json

DATA = ROOT / "src" / "patchreplay" / "data"


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main():
    base = '''"""Synthetic bounded-value utility; intentionally buggy lower bound."""


def clamp(value, lower, upper):
    if lower > upper:
        raise ValueError("lower must not exceed upper")
    return min(value, upper)
'''
    fixed = base.replace("return min(value, upper)", "return max(lower, min(value, upper))")
    for name, code in (("clamp-buggy-v1", base), ("clamp-fixed-v1", fixed)):
        put(DATA / "sources" / name / "clamp.py", code)
        put(DATA / "sources" / name / "tests" / "test_contract.py", '# Protected repository test placeholder. The actual evaluator lives separately.\n')
    evaluator = DATA / "evaluators" / "clamp-v1"
    put(evaluator / "pytest.ini", "[pytest]\njunit_family = xunit2\n")
    put(evaluator / "test_bug.py", '''from clamp import clamp


def test_negative_lower_bound():
    assert clamp(-2, 0, 10) == 0


def test_nonzero_lower_bound():
    assert clamp(1, 5, 10) == 5
''')
    put(evaluator / "test_regression.py", '''import pytest
from clamp import clamp


def test_upper_bound():
    assert clamp(20, 0, 10) == 10


def test_in_range():
    assert clamp(7, 0, 10) == 7


def test_invalid_bounds():
    with pytest.raises(ValueError):
        clamp(4, 10, 0)
''')
    write_json(evaluator / "contract.json", {
        "schema_version": 1, "approval": "Human-authored synthetic evaluator, reviewed as project source",
        "bug": ["test_bug.py::test_negative_lower_bound", "test_bug.py::test_nonzero_lower_bound"],
        "regression": ["test_regression.py::test_upper_bound", "test_regression.py::test_in_range", "test_regression.py::test_invalid_bounds"],
        "baseline_failure": "Every bug node must fail in call phase with AssertionError",
        "protected_source_paths": ["tests/test_contract.py"], "patchable_paths": ["clamp.py"],
    })
    variants = {
        "good": fixed,
        "ineffective": base.replace("return min(value, upper)", "return min(value, upper)  # Lower bound is still missing."),
        "narrow": base.replace("return min(value, upper)", "return lower if value == -2 else min(value, upper)"),
        "regression": base.replace("return min(value, upper)", "return max(lower, value)"),
        "timeout": base.replace("return min(value, upper)", "import time\n    time.sleep(10)\n    return max(lower, min(value, upper))"),
        "unstable": base.replace("return min(value, upper)", 'import os\n    if int(os.environ["PATCHREPLAY_ATTEMPT"]) % 2:\n        return max(lower, min(value, upper))\n    return min(value, upper)'),
        "syntax-error": base.replace("return min(value, upper)", "return ("),
    }
    patches = {}
    for name, code in variants.items():
        patches[name] = "diff --git a/clamp.py b/clamp.py\n" + "".join(difflib.unified_diff(base.splitlines(True), code.splitlines(True), fromfile="a/clamp.py", tofile="b/clamp.py"))
    patches["already-fixed"] = "diff --git a/clamp.py b/clamp.py\n" + "".join(difflib.unified_diff(fixed.splitlines(True), fixed.replace("intentionally buggy lower bound", "already corrected lower bound").splitlines(True), fromfile="a/clamp.py", tofile="b/clamp.py"))
    old = '# Protected repository test placeholder. The actual evaluator lives separately.\n'
    patches["protected"] = "diff --git a/tests/test_contract.py b/tests/test_contract.py\n" + "".join(difflib.unified_diff(old.splitlines(True), ['# Silently remove protected checks.\n'], fromfile="a/tests/test_contract.py", tofile="b/tests/test_contract.py"))
    for name, patch in patches.items():
        put(DATA / "patches" / f"{name}.diff", patch)
    source_hashes = {p.name: tree_hash(p) for p in (DATA / "sources").iterdir()}
    evaluator_hash = tree_hash(evaluator)
    cases = []
    names = ["good", "ineffective", "narrow", "regression", "protected", "environment-error", "timeout", "unstable", "already-fixed", "syntax-error"]
    for name in names:
        patch_name = "good" if name == "environment-error" else name
        source = "clamp-fixed-v1" if name == "already-fixed" else "clamp-buggy-v1"
        cases.append({"schema_version": 1, "case_id": name, "title": f"Synthetic clamp / {name.replace('-', ' ')}",
                      "source_id": source, "source_revision": "sha256:" + source_hashes[source],
                      "patch": f"../patches/{patch_name}.diff", "patch_sha256": digest(patches[patch_name].encode()),
                      "evaluator_id": "clamp-v1", "evaluator_sha256": evaluator_hash,
                      "suite_id": "synthetic-clamp-v1", "repeats": 2, "timeout_seconds": 2.0 if name == "timeout" else 10.0,
                      "required_pytest": "0.0.0" if name == "environment-error" else "8.3.5"})
    # Relative parent paths are never accepted by the reader: cases include a copy of each patch.
    for case in cases:
        patch_name = "good" if case["case_id"] == "environment-error" else case["case_id"]
        case["patch"] = f"{patch_name}.diff"
    members = {c["case_id"]: {k: v for k, v in c.items() if k not in {"patch", "title"}} for c in cases}
    suite_hash = identity(members)
    suite = {"suite_id": "synthetic-clamp-v1", "suite_sha256": suite_hash, "members": members,
             "provenance": "Entirely synthetic, authored for workflow demonstration; not an agent benchmark."}
    write_json(DATA / "suite.json", suite)
    for case in cases:
        case["suite_sha256"] = suite_hash
        write_json(DATA / "cases" / f'{case["case_id"]}.json', case)
        patch_name = case["patch"][:-5]
        put(DATA / "cases" / case["patch"], patches[patch_name])
    write_json(DATA / "catalog.json", {"sources": source_hashes, "evaluators": {"clamp-v1": evaluator_hash},
                                       "patches": {name: digest(value.encode()) for name, value in patches.items()},
                                       "suite_sha256": suite_hash})


if __name__ == "__main__":
    main()
