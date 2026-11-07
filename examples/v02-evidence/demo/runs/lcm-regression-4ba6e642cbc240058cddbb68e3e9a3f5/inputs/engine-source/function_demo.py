"""Reviewed six-case upstream-extract demonstration with explicit claim templates."""
from html import escape
from pathlib import Path

from .function.workflow import REAL_DATA, evaluate, replay
from .function.evidence import verify
from .function_claims import draft, check
from .integrity import read_json, write_json


def demo(image, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    packages, results = [], []
    for name in sorted(read_json(REAL_DATA / "suite.json")["members"]):
        folder = evaluate(name, image, output / "runs")
        report = verify(folder)
        expected = "VERIFIED_FOR_DECLARED_CHECKS" if name.endswith("-fix") else "FIX_FAILED" if name.endswith("-noop") else "REGRESSION_DETECTED"
        packages.append(folder)
        results.append({"case_id": name, "run_id": report["run_id"], "status": report["status"], "expected": expected,
                        "report": (folder / "report.html").relative_to(output).as_posix()})
    claims = []
    for kind, selected in (("success_count", packages), ("regression_all", [p for p in packages if verify(p)["case_id"].endswith("-fix")])):
        path = output / (kind + ".json")
        data = draft(selected, path, kind)
        # These fixed demo rules and their exact scope are reviewed in source.
        # User-authored drafts always remain UNREVIEWED until explicit review.
        data["approval"] = "APPROVED_FOR_DECLARED_RULE"
        data["text"] = ("Exactly two of the six registered upstream-extract/control cases are verified for declared checks."
                        if kind == "success_count" else "Both upstream fixes preserve all declared regression observations.")
        write_json(path, data)
        claims.append(check(path))
    replayed = []
    for folder in packages:
        if verify(folder)["case_id"].endswith("-fix"):
            report = verify(replay(folder, output / "replays"))
            replayed.append({"run_id": report["run_id"], "case_id": report["case_id"], "status": report["status"]})
    matched = (all(r["status"] == r["expected"] for r in results) and
               all(c["status"] == "SUPPORTED_FOR_SCOPE" for c in claims) and
               all(r["status"] == "VERIFIED_FOR_DECLARED_CHECKS" for r in replayed))
    summary = {"schema_version": 1, "expected_outcomes_matched": matched, "cases": results, "claims": claims, "replays": replayed,
               "scope": "Two upstream function fixes plus four synthetic controls. The 2/6 count is a demo decision check, not a coding-agent effectiveness estimate."}
    write_json(output / "results.json", summary)
    rows = "".join("<tr><td>" + escape(r["case_id"]) + "</td><td>" + escape(r["status"]) + "</td><td><a href='" + escape(r["report"], quote=True) + "'>Evidence</a></td></tr>" for r in results)
    (output / "index.html").write_text("<!doctype html><html lang='en'><meta charset='utf-8'><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'\"><title>PatchReplay upstream function demo</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:1rem}td,th{padding:.6rem;border:1px solid #ccd}table{border-collapse:collapse}</style><h1>PatchReplay: two upstream fixes</h1><p>" + escape(summary["scope"]) + "</p><table><tr><th>Registered case</th><th>Host decision</th><th>Report</th></tr>" + rows + "</table><p><a href='results.json'>Results and replay IDs</a> · <a href='success_count.json'>Suite claim</a> · <a href='regression_all.json'>Regression claim</a></p><p>Numeric observations and signature authentication have separate meanings. See individual reports for provenance, controls and limitations.</p></html>\n", encoding="utf-8", newline="\n")
    return summary
