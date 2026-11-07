"""EvidenceCI schema 2: explicit host-function claims, separate from pytest claims."""
from collections import Counter
from pathlib import Path
import re

from .contracts import require_keys, sha
from .function.contract import equal
from .function.evidence import verify
from .integrity import digest, identity, read_json, safe_path, write_json

KEYS = {"schema_version", "evaluation_kind", "claim_id", "text", "approval", "kind", "scope", "assertion", "evidence"}
IDENTITIES = {"source_revision", "patch_sha256", "evaluator_sha256", "suite_sha256", "case_sha256", "environment_sha256", "engine_sha256", "policy", "image", "inputs_sha256"}


def parse(data):
    require_keys(data, KEYS, "Function claim")
    equal([data["schema_version"], data["evaluation_kind"]], [2, "host-function-v1"], "Unsupported function claim schema/kind")
    if data["kind"] not in {"success_count", "regression_all"}:
        raise ValueError("Unsupported claim rule")
    for k in ("claim_id", "text"):
        if not isinstance(data[k], str) or not data[k].strip():
            raise ValueError("Claim ID/text must be nonempty")
    if data["approval"] != "APPROVED_FOR_DECLARED_RULE":
        raise ValueError("Claim draft requires explicit review of text, scope and rule")
    scope = data["scope"]
    require_keys(scope, {"suite_id", "suite_sha256", "case_ids"}, "Claim scope")
    if not isinstance(scope["suite_id"], str) or not sha(scope["suite_sha256"]):
        raise ValueError("Invalid suite identity")
    cases = scope["case_ids"]
    if not isinstance(cases, list) or not cases or any(not isinstance(v, str) or not v for v in cases) or len(set(cases)) != len(cases):
        raise ValueError("Scope requires unique case IDs")
    require_keys(data["assertion"], {"numerator", "denominator", "denominator_policy"}, "Assertion")
    for k in ("numerator", "denominator"):
        if type(data["assertion"][k]) is not int or data["assertion"][k] < 0:
            raise ValueError("Counts must be nonnegative integers")
    if data["assertion"]["denominator_policy"] != "all_declared_cases":
        raise ValueError("The declared denominator cannot shrink")
    if not isinstance(data["evidence"], list):
        raise ValueError("Invalid evidence references")
    for ref in data["evidence"]:
        require_keys(ref, {"case_id", "package", "manifest_sha256", "expected"}, "Evidence reference")
        if not isinstance(ref["case_id"], str) or not isinstance(ref["package"], str) or not sha(ref["manifest_sha256"]):
            raise ValueError("Invalid evidence reference")
        require_keys(ref["expected"], IDENTITIES, "Expected execution identities")
        for k, v in ref["expected"].items():
            if k.endswith("_sha256") and not sha(v):
                raise ValueError("Invalid expected digest")
        for k in ("source_revision", "image"):
            if not isinstance(ref["expected"][k], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", ref["expected"][k]):
                raise ValueError("Invalid expected source/image identity")
        if ref["expected"]["policy"] != "docker-host-function-v1":
            raise ValueError("Unsupported expected execution policy")
    return data


def check(path, evidence_root=None):
    def result(status, reason, **extra):
        return {"schema_version": 2, "evaluation_kind": "host-function-v1", "claim_id": Path(path).stem,
                "status": status, "reason": reason, **extra}
    try:
        data = parse(read_json(Path(path)))
        refs, scope = data["evidence"], data["scope"]
        if len(refs) != len(scope["case_ids"]) or {r["case_id"] for r in refs} != set(scope["case_ids"]):
            raise ValueError("Missing, duplicate or out-of-scope evidence; denominator cannot shrink")
        root, reports, runs, stale = Path(evidence_root or Path(path).parent).resolve(), [], set(), []
        for ref in refs:
            folder = safe_path(root, ref["package"])
            report = verify(folder, ref["manifest_sha256"])
            if report["case_id"] != ref["case_id"] or report["run_id"] in runs:
                raise ValueError("Duplicate run or case mismatch")
            runs.add(report["run_id"])
            case, suite = read_json(folder / "inputs/case.json"), read_json(folder / "inputs/suite.json")
            if (report["identities"] != ref["expected"] or case["suite_id"] != scope["suite_id"] or
                    report["identities"]["suite_sha256"] != scope["suite_sha256"]):
                stale.append(ref["case_id"])
            if data["kind"] == "success_count" and set(scope["case_ids"]) != set(suite["members"]):
                raise ValueError("Success count requires the complete pinned suite, including controls and unsuccessful runs")
            reports.append((report, read_json(folder / "inputs/oracle.json")))
        if stale:
            return result("STALE", "Expected input identities differ", stale_cases=stale)
        numerator = 0
        for index, (report, oracle) in enumerate(reports):
            if data["kind"] == "success_count":
                numerator += report["status"] == "VERIFIED_FOR_DECLARED_CHECKS"
            else:
                if report["failure"] or report["status"] in {"INTEGRITY_ERROR", "INFRA_ERROR", "REPEAT_DISAGREEMENT"}:
                    raise ValueError("Regression observations lack a trustworthy complete execution")
                ids = {p["id"] for p in oracle["probes"] if p["group"] == "regression"}
                rows = [r for r in report["observations"] if r["probe_id"] in ids]
                case = read_json(safe_path(root, refs[index]["package"]) / "inputs/case.json")
                expected = {(phase, a, p) for phase in ("before", "after") for a in range(1, case["repeats"] + 1) for p in ids}
                if {(r["phase"], r["attempt"], r["probe_id"]) for r in rows} != expected or len(rows) != len(expected):
                    raise ValueError("Missing regression observations")
                if any(r["observation"]["outcome"] not in {"MATCH", "MISMATCH"} for r in rows):
                    raise ValueError("Regression timeout/error cannot establish a pass")
                if any(r["observation"]["outcome"] != "MATCH" for r in rows if r["phase"] == "before"):
                    raise ValueError("Regression claim requires a passing baseline")
                numerator += all(r["observation"]["outcome"] == "MATCH" for r in rows if r["phase"] == "after")
        observed = {"numerator": numerator, "denominator": len(scope["case_ids"]), "denominator_policy": "all_declared_cases"}
        matches = observed == data["assertion"] and (data["kind"] != "regression_all" or numerator == len(reports))
        return result("SUPPORTED_FOR_SCOPE" if matches else "CONTRADICTED", "Computed from host observations within the explicitly pinned scope",
                      observed=observed, excluded_from_numerator=dict(Counter(r["status"] for r, _ in reports if r["status"] != "VERIFIED_FOR_DECLARED_CHECKS")))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return result("INSUFFICIENT_EVIDENCE", str(exc))


def draft(packages, output, kind):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Draft output already exists")
    refs, suites, cases, count = [], set(), [], 0
    for package in packages:
        package = Path(package).resolve()
        report = verify(package)
        case = read_json(package / "inputs/case.json")
        suites.add((case["suite_id"], case["suite_sha256"]))
        cases.append(case["case_id"])
        if not package.is_relative_to(output.parent):
            raise ValueError("Claim must be placed above its evidence packages; external paths are not accepted")
        refs.append({"case_id": case["case_id"], "package": package.relative_to(output.parent).as_posix(),
                     "manifest_sha256": digest((package / "manifest.json").read_bytes()), "expected": report["identities"]})
        count += report["status"] == "VERIFIED_FOR_DECLARED_CHECKS"
    if len(suites) != 1 or len(set(cases)) != len(cases):
        raise ValueError("Draft requires unique cases from one versioned suite")
    suite, sha = suites.pop()
    value = {"schema_version": 2, "evaluation_kind": "host-function-v1", "claim_id": output.stem,
             "text": "Review this draft: " + kind + " over the explicitly listed cases.", "approval": "UNREVIEWED",
             "kind": kind, "scope": {"suite_id": suite, "suite_sha256": sha, "case_ids": cases},
             "assertion": {"numerator": count if kind == "success_count" else len(cases), "denominator": len(cases), "denominator_policy": "all_declared_cases"}, "evidence": refs}
    write_json(output, value)
    return value
