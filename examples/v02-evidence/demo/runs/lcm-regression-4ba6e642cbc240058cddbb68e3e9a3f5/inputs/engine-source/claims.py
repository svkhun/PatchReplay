"""EvidenceCI: explicit scope, arithmetic, and identity rules; no language model."""

from __future__ import annotations

from pathlib import Path

from .contracts import CaseSpec, ClaimStatus, Status, decide, require_keys, sha
from .engine import interpret
from .integrity import IntegrityError, digest, identity, read_json, safe_path, tree_files, tree_hash, verify_package

IDENTITY_KEYS = {"source_revision", "patch_sha256", "evaluator_sha256", "suite_sha256", "environment_sha256",
                 "engine_sha256", "case_sha256", "inputs_sha256"}


def validate_report(root: Path, report: dict) -> None:
    if report.get("schema_version") != 1 or report.get("status") not in {s.value for s in Status}:
        raise IntegrityError("Unsupported report schema or status")
    ids = report.get("identities")
    require_keys(ids, IDENTITY_KEYS, "Report identities")
    case_data = read_json(root / "inputs" / "case.json")
    case = CaseSpec.parse(case_data)
    if (report["case_id"] != case.case_id or report["suite_id"] != case.suite_id
            or report["repeats"] != case.repeats or report["timeout_seconds"] != case.timeout_seconds):
        raise IntegrityError("Report scope differs from its case specification")
    actual = {"source_revision": case.source_revision, "patch_sha256": digest((root / "inputs" / "patch.diff").read_bytes()),
              "evaluator_sha256": case.evaluator_sha256, "suite_sha256": case.suite_sha256,
              "environment_sha256": identity(read_json(root / "inputs" / "environment.json")),
              "engine_sha256": identity(read_json(root / "inputs" / "engine.json")["files"]),
              "case_sha256": identity(case_data)}
    actual["inputs_sha256"] = identity(actual)
    if actual != ids or case.patch_sha256 != actual["patch_sha256"]:
        raise IntegrityError("Input fingerprints do not agree with stored inputs")
    if identity(tree_files(root / "inputs" / "engine-source")) != ids["engine_sha256"]:
        raise IntegrityError("Recorded engine source differs from its identity")
    suite = read_json(root / "inputs" / "suite.json")
    if identity(suite["members"]) != ids["suite_sha256"] or suite["suite_id"] != case.suite_id:
        raise IntegrityError("Suite definition differs from its identity")
    member = {k: v for k, v in case_data.items() if k not in {"patch", "title", "suite_sha256"}}
    if suite["members"].get(case.case_id) != member:
        raise IntegrityError("Case does not match the declared suite roster")
    for name, expected in (("source", case.source_revision[7:]), ("evaluator", case.evaluator_sha256)):
        path = root / "inputs" / name
        if path.exists() and tree_hash(path) != expected:
            raise IntegrityError(f"Stored {name} snapshot does not match its identity")
    checks = report["checks"]
    if not isinstance(checks, list):
        raise IntegrityError("Invalid check list")
    if checks:
        contract = read_json(root / "inputs" / "evaluator" / "contract.json")
        if not (root / "inputs" / "source").is_dir() or not (root / "inputs" / "patched-source").is_dir():
            raise IntegrityError("Executed checks lack source snapshots")
        for check in checks:
            selection = "bug" if check["phase"].endswith("bug") else "regression"
            if check["expected_nodes"] != contract[selection]:
                raise IntegrityError("Observed check selection differs from the approved evaluator")
            safe_path(root, check["log"]).read_bytes()
            if check["timeout"]:
                if check["outcome"] != "TIMEOUT":
                    raise IntegrityError("Timeout observation conflicts with check outcome")
            elif check["records"]:
                outcome, signature = interpret(read_json(safe_path(root, check["records"])), contract[selection], check["phase"], check["exit_code"])
                if check["outcome"] != "INTEGRITY_ERROR" and (outcome != check["outcome"] or signature != check["signature"]):
                    raise IntegrityError("Check decision conflicts with raw pytest records")
            elif check["outcome"] != "INFRA_ERROR":
                raise IntegrityError("Check lacks raw observation records")
        status, _ = decide(checks, case.repeats)
        if report["status"] != status.value:
            raise IntegrityError("Report verdict conflicts with check decisions")
    elif report["status"] not in {Status.INFRA.value, Status.INTEGRITY.value, Status.FIX_FAILED.value}:
        raise IntegrityError("A conclusive test verdict requires actual check records")


def parse_claim(data: dict) -> dict:
    require_keys(data, {"schema_version", "claim_id", "text", "kind", "scope", "assertion", "evidence"}, "Claim")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or data["kind"] not in {"success_count", "regression_all"}:
        raise ValueError("Unsupported claim schema or kind")
    for key in ("claim_id", "text"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"{key} must be nonempty text")
    scope = data["scope"]
    require_keys(scope, {"suite_id", "suite_sha256", "case_ids"}, "Scope")
    if not isinstance(scope["suite_id"], str) or not sha(scope["suite_sha256"]):
        raise ValueError("Scope requires a suite identity")
    cases = scope["case_ids"]
    if not isinstance(cases, list) or not cases or any(not isinstance(c, str) for c in cases) or len(set(cases)) != len(cases):
        raise ValueError("Scope must name unique case IDs")
    assertion = data["assertion"]
    require_keys(assertion, {"numerator", "denominator", "denominator_policy"}, "Assertion")
    if any(type(assertion[k]) is not int or assertion[k] < 0 for k in ("numerator", "denominator")):
        raise ValueError("Counts must be nonnegative integers, not booleans")
    if assertion["denominator_policy"] != "all_declared_cases":
        raise ValueError("Only all_declared_cases is supported: timeout/error/inconclusive stay in the denominator")
    if not isinstance(data["evidence"], list):
        raise ValueError("evidence must be a list")
    for ref in data["evidence"]:
        require_keys(ref, {"case_id", "package", "manifest_sha256", "expected"}, "Evidence reference")
        if not isinstance(ref["case_id"], str) or not isinstance(ref["package"], str) or not sha(ref["manifest_sha256"]):
            raise ValueError("Evidence requires case ID, package path, and manifest hash")
        require_keys(ref["expected"], IDENTITY_KEYS, "Expected identities")
        if any(not sha(v) for k, v in ref["expected"].items() if k != "source_revision"):
            raise ValueError("Expected fingerprints must be SHA-256 values")
        source = ref["expected"]["source_revision"]
        if not isinstance(source, str) or not source.startswith("sha256:") or not sha(source[7:]):
            raise ValueError("Expected source revision must be content addressed")
    return data


def check_claim(path: Path, evidence_root: Path | None = None) -> dict:
    try:
        if read_json(path).get("schema_version") == 2:
            from .function_claims import check
            return check(path, evidence_root)
    except (OSError, ValueError):
        pass
    claim_id = path.stem

    def result(status, reason, **extra):
        return {"schema_version": 1, "claim_id": claim_id, "status": status.value, "reason": reason, **extra}

    try:
        claim = parse_claim(read_json(path))
        claim_id = claim["claim_id"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return result(ClaimStatus.INSUFFICIENT, f"Invalid claim manifest: {exc}")
    scope = claim["scope"]
    refs = claim["evidence"]
    if len(refs) != len(scope["case_ids"]) or {r["case_id"] for r in refs} != set(scope["case_ids"]):
        return result(ClaimStatus.INSUFFICIENT, "Missing, duplicate, or out-of-scope evidence references; the denominator cannot shrink.")
    root = (evidence_root or path.parent).resolve()
    reports = []
    stale = []
    run_ids = set()
    try:
        for ref in refs:
            folder = safe_path(root, ref["package"])
            report = verify_package(folder, ref["manifest_sha256"])
            validate_report(folder, report)
            if report["case_id"] != ref["case_id"] or report["run_id"] in run_ids:
                raise IntegrityError("Duplicate run or case mismatch")
            run_ids.add(report["run_id"])
            if report["identities"] != ref["expected"] or report["suite_id"] != scope["suite_id"] or report["identities"]["suite_sha256"] != scope["suite_sha256"]:
                stale.append(ref["case_id"])
            suite = read_json(folder / "inputs" / "suite.json")
            if claim["kind"] == "success_count" and set(scope["case_ids"]) != set(suite["members"]):
                raise IntegrityError("Suite success_count must cover the complete versioned roster")
            reports.append(report)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return result(ClaimStatus.INSUFFICIENT, f"Evidence is incomplete or inconsistent: {exc}")
    if stale:
        return result(ClaimStatus.STALE, "Evidence no longer matches the explicitly expected input identities.", stale_cases=stale)
    if claim["kind"] == "success_count":
        numerator = sum(r["status"] == Status.VERIFIED.value for r in reports)
    else:
        numerator = 0
        for report in reports:
            rows = [c for c in report["checks"] if c["phase"] == "after_regression"]
            if len(rows) != report["repeats"] or any(c["outcome"] in {"TIMEOUT", "INFRA_ERROR", "INTEGRITY_ERROR", "CHECK_ERROR"} for c in rows):
                return result(ClaimStatus.INSUFFICIENT, "At least one declared regression check has no interpretable pass/fail observation.")
            numerator += all(c["outcome"] == "PASS" for c in rows)
    denominator = len(scope["case_ids"])
    observed = {"numerator": numerator, "denominator": denominator, "denominator_policy": "all_declared_cases"}
    expected = claim["assertion"]
    matches = numerator == expected["numerator"] and denominator == expected["denominator"]
    if claim["kind"] == "regression_all":
        matches = matches and numerator == denominator
    status = ClaimStatus.SUPPORTED if matches else ClaimStatus.CONTRADICTED
    return result(status, f"Observed {numerator}/{denominator} within the declared scope. All declared cases remain in the denominator.",
                  observed=observed, asserted=expected,
                  excluded_from_numerator={s.value: sum(r["status"] == s.value for r in reports) for s in Status if s != Status.VERIFIED} if claim["kind"] == "success_count" else {})
