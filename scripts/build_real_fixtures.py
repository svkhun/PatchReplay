"""Maintainer authoring for pinned upstream extracts. Never imports candidate code."""
import ast
import difflib
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from patchreplay.function.contract import POLICY
from patchreplay.integrity import digest, identity, tree_hash, write_json

DATA = Path(__file__).resolve().parents[1] / "src/patchreplay/data/real"


def build():
    members = {}
    descriptions = {
        "boltons": ("mahmoud/boltons", "230b856dc31cc0702d77ef978daec9cff45944eb", "4bae3f55894e78ec6326d6dba8ac7e3eb39440aa", "boltons/mathutils.py"),
        "lcm": ("TheAlgorithms/Python", "d9027b034699aa60f3e89e1344211b686274af27", "4aca14b650a238e4906c3d753b075cc324774e67", "maths/least_common_multiple.py"),
    }
    for project, (repository, before_commit, fix_commit, upstream_path) in descriptions.items():
        raw = DATA / "upstream" / project
        before, after = [(raw / name).read_text(encoding="utf-8") for name in ("before.py.txt", "after.py.txt")]
        if project == "boltons":
            adapter = '''\n# Reviewed observation adapter; zero bounds select the upstream default-argument call.\n_upstream_clamp = clamp\ndef clamp(value, lower, upper):\n    try:\n        return _upstream_clamp(value) if lower == upper == 0 else _upstream_clamp(value, lower, upper)\n    except TypeError:\n        return -9007199254740991\n'''
            probes = [("default-positive", "bug", [7, 0, 0], 7, -9007199254740991),
                      ("default-large", "bug", [42, 0, 0], 42, -9007199254740991),
                      ("bounded", "regression", [4, 1, 10], 4, 4),
                      ("upper", "regression", [12, 1, 10], 10, 10)]
            adaptation = "Full upstream module retained; append a fixed wrapper. TypeError is encoded by the reserved integer -9007199254740991. Declared success probes cannot return this sentinel. Zero/zero bounds select the upstream default-argument call."
        else:
            gcd_text = (raw / "gcd.py.txt").read_text(encoding="utf-8")
            # The upstream CLI footer uses Python 3.14 except syntax. Extract only
            # the dependency function before parsing; that function supports 3.11+.
            gcd = "def greatest_common_divisor" + gcd_text.split("def greatest_common_divisor", 1)[1].split("\ndef gcd_by_iterative", 1)[0]
            ast.parse(gcd)
            before, after = [s.replace("from maths.greatest_common_divisor import greatest_common_divisor", gcd) for s in (before, after)]
            adapter = '''\n# Reviewed nonnegative-domain observation adapter.\ndef clamp(first, second, unused):\n    try:\n        return least_common_multiple_fast(first, second)\n    except ZeroDivisionError:\n        return -1\n'''
            probes = [("both-zero", "bug", [0, 0, 0], 0, -1),
                      ("coprime", "regression", [3, 5, 0], 15, 15),
                      ("shared-factor", "regression", [6, 9, 0], 18, 18),
                      ("one-zero", "regression", [0, 5, 0], 0, 0)]
            adaptation = "Full upstream module retained, replacing only the gcd import with the exact pinned gcd function body. Append fixed wrapper for nonnegative integer inputs. ZeroDivisionError is encoded as -1, outside the declared nonnegative result domain."
        source, fixed = (before + adapter).encode(), (after + adapter).encode()
        for variant in ("fix", "noop", "regression"):
            name = project + "-" + variant
            folder = DATA / name
            provenance = folder / "provenance"
            provenance.mkdir(parents=True, exist_ok=True)
            for path in raw.iterdir():
                shutil.copyfile(path, provenance / path.name)
            (provenance / "adapter.py.txt").write_text(adapter, encoding="utf-8", newline="\n")
            write_json(provenance / "record.json", {
                "schema_version": 1, "origin": "upstream-function-extract", "repository": repository,
                "before_commit": before_commit, "fix_commit": fix_commit, "upstream_path": upstream_path,
                "fix_url": f"https://github.com/{repository}/commit/{fix_commit}",
                "variant": variant, "variant_origin": "upstream-fix" if variant == "fix" else "synthetic-control",
                "adaptation": adaptation, "dependency_policy": "Python standard library only; no installation during evaluation",
                "scope": "Declared function probes through a reviewed wrapper; not the complete upstream project/test suite.",
            })
            patched = fixed if variant == "fix" else source + b"# Synthetic ineffective control.\n" if variant == "noop" else fixed + b"\n# Synthetic regressive control; not an upstream patch.\ndef clamp(a, b, c):\n    return 99\n"
            oracle = {"schema_version": 1, "rule": "all-declared-baseline-mismatches-v1", "probes": [
                dict(zip(("id", "group", "args", "expected", "baseline"), p)) for p in probes]}
            patch = ("diff --git a/candidate.py b/candidate.py\n" + "".join(difflib.unified_diff(source.decode().splitlines(True), patched.decode().splitlines(True), "a/candidate.py", "b/candidate.py"))).encode()
            for filename, value in (("source.py", source), ("patched.py", patched), ("patch.diff", patch)):
                (folder / filename).write_bytes(value)
            write_json(folder / "oracle.json", oracle)
            members[name] = {"schema_version": 2, "case_id": name, "source_sha256": digest(source), "patch_sha256": digest(patch),
                             "patched_sha256": digest(patched), "evaluator_sha256": identity(oracle), "suite_id": "reviewed-upstream-functions-v1",
                             "provenance_sha256": tree_hash(provenance), "policy_sha256": identity(POLICY), "interface": POLICY["interface"],
                             "repeats": 2, "timeout_seconds": 10}
    suite = {"suite_id": "reviewed-upstream-functions-v1", "members": members}
    write_json(DATA / "suite.json", suite)
    for name, member in members.items():
        write_json(DATA / name / "case.json", {**member, "suite_sha256": identity(suite)})
    print(identity(suite))


if __name__ == "__main__":
    build()
