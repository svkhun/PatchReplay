"""Escaped, offline, dependency-free HTML reports."""

from html import escape
from pathlib import Path
from string import Template

from .contracts import PHASES, Status
from .integrity import read_json, safe_path


def e(value) -> str:
    return escape(str(value), quote=True)


def pill(outcome: str) -> str:
    category = "" if outcome in {"PASS", "EXPECTED_FAILURE"} else "uncertain" if outcome in {"TIMEOUT", "CHECK_ERROR"} else "bad"
    return f'<span class="pill {category}">{e(outcome)}</span>'


def render_report(root: Path, report: dict) -> None:
    checks = report["checks"]
    labels = {"before_bug": "Bug / before", "before_regression": "Regression / before", "after_bug": "Bug / after", "after_regression": "Regression / after"}
    rows = []
    for phase in PHASES:
        for check in (c for c in checks if c["phase"] == phase):
            rows.append(f'<tr><td>{e(labels[phase])}</td><td>{check["attempt"]}</td><td>{pill(check["outcome"])}</td>'
                        f'<td>{e(check["exit_code"])}</td><td>{check["duration_seconds"]:.2f}s</td><td><a href="{e(check["log"])}">Log</a></td></tr>')
    table = '<div class="scroll"><table><thead><tr><th>Check</th><th>Attempt</th><th>Observation</th><th>Exit</th><th>Time</th><th>Evidence</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>' if rows else '<div class="empty">No tests ran. The preflight or integrity decision above explains why. See available setup logs below.</div>'
    contract_path = root / "inputs" / "evaluator" / "contract.json"
    if contract_path.exists():
        contract = read_json(contract_path)
        criteria = '<p>' + e(contract["approval"]) + '</p>'
        for selection in ("bug", "regression"):
            criteria += f'<h3>{selection.title()} nodes</h3><ul>' + ''.join(f'<li><code>{e(node)}</code></li>' for node in contract[selection]) + '</ul>'
        criteria += '<p><strong>Required baseline:</strong> ' + e(contract["baseline_failure"]) + '.</p>'
    else:
        criteria = '<div class="empty">Evaluator was not admitted. No criteria were executed.</div>'
    logs = []
    for row in [*report["steps"], *checks]:
        path = safe_path(root, row["log"])
        content = path.read_text(encoding="utf-8", errors="replace")[:20_000] if path.exists() else "Log unavailable."
        label = row.get("id", row.get("kind", "Step"))
        logs.append(f'<details><summary>{e(label)} · exit {e(row["exit_code"])} · {row["duration_seconds"]:.2f}s</summary>'
                    f'<p>Timeout: {e(row["timeout"])} · <a href="{e(row["log"])}">Full retained log</a></p>'
                    '<h3>Command (recorded argv)</h3><pre>' + e(repr(row["command"])) + '</pre><pre>' + e(content) + '</pre></details>')
    after = [c for c in checks if c["phase"].startswith("after")]
    metrics = [("Check groups passing after", f'{sum(c["outcome"] == "PASS" for c in after)} / {len(after)}' if after else "Not run"),
               ("Attempts per phase", report["repeats"]), ("Timeout per check", f'{report["timeout_seconds"]:g}s'),
               ("Total check time", f'{sum(c["duration_seconds"] for c in checks):.2f}s')]
    tone = "#126b59" if report["status"] == Status.VERIFIED else "#996412" if report["status"] in {Status.INCONCLUSIVE, Status.NOT_REPRODUCED} else "#a04030"
    template = Template((Path(__file__).parent / "templates" / "report.html").read_text(encoding="utf-8"))
    html = template.substitute(title=e(report["title"]), status=e(report["status"]), reason=e(report["reason"]), tone=tone,
        checks=table, criteria=criteria, logs="".join(logs) or '<div class="empty">No subprocess logs were produced.</div>',
        identities=''.join(f'<div class="identity"><span>{e(key)}</span><code>{e(value)}</code></div>' for key, value in report["identities"].items()),
        limitations=''.join(f'<li>{e(line)}</li>' for line in report["limitations"]),
        metrics=''.join(f'<div class="metric"><small>{e(label)}</small><strong>{e(value)}</strong></div>' for label, value in metrics),
        replay=e(report["replay"]), version=e(report["evaluator_version"]), run_id=e(report["run_id"]), created_at=e(report["created_at"]))
    (root / "report.html").write_text(html, encoding="utf-8", newline="\n")


def render_index(output: Path, reports: list[tuple[Path, dict]], claims: list[dict]) -> None:
    rows = ''.join(f'<tr><td><a href="{e(path.name)}/report.html">{e(r["case_id"])}</a></td><td>{e(r["status"])}</td><td>{e(r["reason"])}</td></tr>' for path, r in reports)
    claim_rows = ''.join(f'<tr><td>{e(c["claim_id"])}</td><td>{e(c["status"])}</td><td>{e(c["reason"])}</td></tr>' for c in claims)
    style = (Path(__file__).parent / "templates" / "report.html").read_text().split('<style>')[1].split('</style>')[0]
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>PatchReplay / Demo evidence</title><style>{style}</style></head><body>
<header class="bar"><div class="brand">Patch<b>Replay</b></div><span>CONTROLLED FIXTURE LAB</span></header><main>
<div class="eyebrow">MVP / local evaluation</div><h1>A patch is a proposal.<br>Make its evidence reviewable.</h1>
<p class="lede">Ten synthetic cases. Declared criteria. Inspectable before-and-after observations. No API key, backend, or model call.</p>
<section class="notice"><strong>This is a workflow demonstration.</strong> The fixture outcomes do not measure the success rate of a coding agent. Open a case to inspect its checks, limitations, logs, and replay instructions.</section>
<section class="card"><h2>Patch evaluations</h2><div class="scroll"><table><thead><tr><th>Case</th><th>Decision</th><th>Reason</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section class="card"><h2>EvidenceCI / explicit claims</h2><p>Claims use declared numeric rules and pinned evidence identities. Natural-language truth is outside this tool's scope.</p><div class="scroll"><table><thead><tr><th>Claim</th><th>Decision</th><th>Reason</th></tr></thead><tbody>{claim_rows}</tbody></table></div><p><a href="claims/results.json">Claim results</a> · <a href="suite-results.json">Suite results</a></p></section>
<footer>PatchReplay · Synthetic fixture suite v1 · No result cache · Offline HTML</footer></main></body></html>'''
    (output / "index.html").write_text(html, encoding="utf-8", newline="\n")
