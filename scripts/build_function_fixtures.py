"""Maintainer-only synthetic fixture authoring. Review bytes and catalog together."""
from pathlib import Path
import difflib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from experiments.observer_boundary.fixtures import SOURCES
from patchreplay.function.contract import POLICY
from patchreplay.integrity import digest, identity, write_json


def main():
    data = ROOT / "src/patchreplay/data/function"
    oracle = {"schema_version": 1, "rule": "all-declared-baseline-mismatches-v1", "probes": [
        {"id": "negative-lower", "group": "bug", "args": [-2, 0, 10], "expected": 0, "baseline": -2},
        {"id": "nonzero-lower", "group": "bug", "args": [1, 5, 10], "expected": 5, "baseline": 1},
        {"id": "in-range", "group": "regression", "args": [4, 0, 10], "expected": 4, "baseline": 4},
        {"id": "upper", "group": "regression", "args": [12, 0, 10], "expected": 10, "baseline": 10},
    ]}
    write_json(data / "oracle.json", oracle)
    buggy, correct = SOURCES["buggy"], SOURCES["correct"]
    cases = {
        "good": (buggy, correct),
        "incorrect": (buggy, buggy + "# Ineffective reviewed patch.\n"),
        "narrow": (buggy, "def clamp(value, lower, upper):\n    return max(0, min(value, upper))\n"),
        "regression": (buggy, "def clamp(value, lower, upper):\n    return max(lower, value)\n"),
        "already-fixed": (correct, correct + "# Already corrected baseline.\n"),
        "baseline-regression": ("def clamp(value, lower, upper):\n    return min(value, upper - 1)\n", correct),
    }
    cases.update({name.replace("_", "-"): (buggy, source) for name, source in SOURCES.items()
                  if name not in {"buggy", "correct"}})
    members = {}
    for name, (before, after) in cases.items():
        folder = data / name
        folder.mkdir(parents=True, exist_ok=True)
        patch = "diff --git a/candidate.py b/candidate.py\n" + "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True), "a/candidate.py", "b/candidate.py"))
        for filename, value in (("source.py", before), ("patched.py", after), ("patch.diff", patch)):
            (folder / filename).write_text(value, encoding="utf-8", newline="\n")
        members[name] = {"schema_version": 1, "case_id": name, "source_sha256": digest(before.encode()),
                         "patched_sha256": digest(after.encode()), "patch_sha256": digest(patch.encode()),
                         "evaluator_sha256": identity(oracle), "suite_id": "synthetic-function-v1",
                         "policy_sha256": identity(POLICY), "interface": POLICY["interface"],
                         "repeats": 2, "timeout_seconds": 2 if name == "timeout" else 10}
    suite = {"suite_id": "synthetic-function-v1", "members": members}
    write_json(data / "suite.json", suite)
    for name, member in members.items():
        write_json(data / name / "case.json", {**member, "suite_sha256": identity(suite)})
    print("Reviewed suite identity:", identity(suite))


if __name__ == "__main__":
    main()
