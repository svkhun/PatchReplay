"""Reproducible synthetic demonstrations, including intentionally false claims."""

from copy import deepcopy
from pathlib import Path

from .claims import check_claim
from .contracts import Status
from .engine import DATA, evaluate
from .integrity import digest, read_json, write_json
from .reporting import render_index

EXPECTED = {"good": Status.VERIFIED.value, "ineffective": Status.FIX_FAILED.value, "narrow": Status.FIX_FAILED.value,
            "regression": Status.REGRESSION.value, "protected": Status.INTEGRITY.value,
            "environment-error": Status.INFRA.value, "timeout": Status.INCONCLUSIVE.value,
            "unstable": Status.INCONCLUSIVE.value, "already-fixed": Status.NOT_REPRODUCED.value,
            "syntax-error": Status.FIX_FAILED.value}
EXPECTED_CLAIMS = {"suite-supported": "SUPPORTED_FOR_SCOPE", "wrong-number": "CONTRADICTED",
                   "regression-supported": "SUPPORTED_FOR_SCOPE", "stale-patch": "STALE",
                   "missing-evidence": "INSUFFICIENT_EVIDENCE", "tampered-evidence": "INSUFFICIENT_EVIDENCE"}


def demo(output: Path, progress=lambda message: print(message, flush=True)) -> dict:
    if output.exists() and any(output.iterdir()):
        raise ValueError("Demo output must be empty or new; existing evidence is never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for name in EXPECTED:
        folder = evaluate(DATA / "cases" / f"{name}.json", output)
        report = read_json(folder / "report.json")
        reports.append((folder, report))
        progress(f'{name}: {report["status"]}')
    suite = read_json(DATA / "suite.json")
    refs = [{"case_id": r["case_id"], "package": p.name, "manifest_sha256": digest((p / "manifest.json").read_bytes()), "expected": r["identities"]} for p, r in reports]
    # The expected numerator is fixed by the reviewed fixture suite, not inferred from this run.
    supported = {"schema_version": 1, "claim_id": "suite-supported", "text": "One of ten synthetic cases is verified for its declared checks.",
                 "kind": "success_count", "scope": {"suite_id": suite["suite_id"], "suite_sha256": suite["suite_sha256"], "case_ids": list(EXPECTED)},
                 "assertion": {"numerator": 1, "denominator": 10, "denominator_policy": "all_declared_cases"}, "evidence": refs}
    wrong = deepcopy(supported)
    wrong.update(claim_id="wrong-number", text="Eight of ten synthetic cases were verified.")
    wrong["assertion"]["numerator"] = 8
    regression = deepcopy(supported)
    regression.update(claim_id="regression-supported", kind="regression_all", text="The good patch passes every declared regression check.")
    regression["scope"]["case_ids"] = ["good"]
    regression["assertion"] = {"numerator": 1, "denominator": 1, "denominator_policy": "all_declared_cases"}
    regression["evidence"] = [deepcopy(refs[0])]
    stale = deepcopy(regression)
    stale.update(claim_id="stale-patch", text="The expected patch identity changed after this run.")
    stale["evidence"][0]["expected"]["patch_sha256"] = "0" * 64
    missing = deepcopy(supported)
    missing.update(claim_id="missing-evidence", text="The suite claim is missing one evidence package.")
    missing["evidence"][0]["package"] = "missing-package"
    tampered = deepcopy(regression)
    tampered.update(claim_id="tampered-evidence", text="The supplied manifest does not match the separately pinned anchor.")
    tampered["evidence"][0]["manifest_sha256"] = "f" * 64
    results = []
    for claim in (supported, wrong, regression, stale, missing, tampered):
        path = output / f'claim-{claim["claim_id"]}.json'
        write_json(path, claim)
        results.append(check_claim(path))
    write_json(output / "claims" / "results.json", {"schema_version": 1, "claims": results})
    checks = [{"case_id": r["case_id"], "actual": r["status"], "expected": EXPECTED[r["case_id"]], "package": p.name} for p, r in reports]
    passed = all(c["actual"] == c["expected"] for c in checks) and all(r["status"] == EXPECTED_CLAIMS[r["claim_id"]] for r in results)
    summary = {"schema_version": 1, "expectations_met": passed, "cases": checks, "claim_results": results,
               "scope": "Synthetic workflow demonstration; not general coding-agent performance."}
    write_json(output / "suite-results.json", summary)
    render_index(output, reports, results)
    return summary

