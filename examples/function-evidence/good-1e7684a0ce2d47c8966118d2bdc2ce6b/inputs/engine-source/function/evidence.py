"""Offline verification of function packages; never executes recorded source."""
import base64
from html import escape
import json
import math
from pathlib import Path
import re

from patchreplay.contracts import require_keys, sha
from patchreplay.executors import DockerExecutor
from patchreplay.integrity import digest, identity, read_json, safe_path, tree_files, verify_package
from .contract import KIND, POLICY, LIMITATIONS, equal, parse_case, parse_oracle, schedule, decide
from .transport import interpret, MAX_RESPONSE

REPORT_KEYS = {"schema_version", "evaluation_kind", "run_id", "case_id", "created_at", "identities",
               "observations", "failure", "status", "reason", "limitations"}
ROW_KEYS = {"request", "container_name", "command", "duration_seconds", "raw_base64", "response_sha256",
            "exit_code", "timeout", "overflow", "error", "container_removed", "input_changed", "cleanup_error",
            "observation", "phase", "attempt", "probe_id"}


def render(report, case, oracle):
    rows = []
    probes = {p["id"]: p for p in oracle["probes"]}
    for row in report["observations"]:
        p = probes[row["probe_id"]]
        cells = [row["phase"], row["attempt"], p["group"], p["id"], p["args"], p["expected"],
                 row["observation"].get("value", "—"), row["observation"]["outcome"], row["container_removed"]]
        rows.append("<tr>" + "".join("<td>" + escape(str(c)) + "</td>" for c in cells) + "</tr>")
    raw = "".join("<details><summary>" + escape(f'{r["phase"]} / {r["attempt"]} / {r["probe_id"]}') +
                  "</summary><pre>" + escape(base64.b64decode(r["raw_base64"]).decode("utf-8", errors="replace")) +
                  "</pre></details>" for r in report["observations"])
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
            "<meta name='viewport' content='width=device-width, initial-scale=1'><title>PatchReplay host function evidence</title>"
            "<style>body{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#17263c}"
            "table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #ccd4df;padding:.4rem;text-align:left}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4f8;padding:1rem}summary{cursor:pointer}</style>"
            "<h1>Host-owned function evaluation</h1><p>Format: host-function-v1 / report schema 2. "
            "Numeric responses are judged on the host; this is separate from legacy pytest evidence.</p>"
            "<h2>" + escape(report["status"]) + "</h2><p>" + escape(report["reason"]) + "</p>"
            "<p>Run: " + escape(report["run_id"]) + " · Case: " + escape(case["case_id"]) + "</p>"
            "<p><a href='report.json'>Full JSON</a> · <a href='manifest.json'>File hashes</a> · "
            "<a href='inputs/case.json'>Case</a> · <a href='inputs/oracle.json'>Host oracle</a> · "
            "<a href='inputs/patch.diff'>Patch</a> · <a href='inputs/environment.json'>Environment</a></p>"
            "<h2>Declared observations</h2><p>" + str(case["repeats"]) + " repeats; " +
            str(len(schedule(case, oracle))) + " required observations. Every bug probe must reproduce its "
            "declared wrong baseline value; baseline regressions must match. Errors never establish reproduction.</p>"
            "<table><thead><tr>" + "".join("<th>" + h + "</th>" for h in
                ["Phase", "Repeat", "Group", "Probe", "Arguments", "Expected", "Observed", "Host outcome", "Removed"]) +
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table><h2>Bounded raw responses</h2>" + raw +
            "<h2>Identities</h2><pre>" + escape(json.dumps(report["identities"], indent=2, sort_keys=True)) +
            "</pre><h2>Scope and limitations</h2><ul>" + "".join("<li>" + escape(v) + "</li>" for v in report["limitations"]) +
            "</ul><h2>Replay</h2><pre>python -m patchreplay replay &lt;this-package&gt; --output replay-output</pre></html>\n")


def validate(root, report):
    from .workflow import bindings
    require_keys(report, REPORT_KEYS, "Function report")
    equal([report["schema_version"], report["evaluation_kind"]], [2, KIND], "Unsupported function report version")
    case = parse_case(read_json(root / "inputs/case.json"))
    oracle = parse_oracle(read_json(root / "inputs/oracle.json"))
    suite = read_json(root / "inputs/suite.json")
    equal(case, {**suite["members"][case["case_id"]], "suite_sha256": identity(suite)}, "Suite/case inconsistency")
    equal(case["suite_id"], suite["suite_id"], "Suite ID mismatch")
    equal(report["case_id"], case["case_id"], "Report case mismatch")
    if not isinstance(report["run_id"], str) or not re.fullmatch(re.escape(case["case_id"]) + r"-[0-9a-f]{32}", report["run_id"]):
        raise ValueError("Invalid function run identity")
    from datetime import datetime
    if not isinstance(report["created_at"], str) or datetime.fromisoformat(report["created_at"]).tzinfo is None:
        raise ValueError("Invalid creation time")
    equal(identity(oracle), case["evaluator_sha256"], "Oracle drift")
    equal(read_json(root / "inputs/policy.json"), POLICY, "Policy drift")
    for file, key in (("source.py", "source_sha256"), ("patched.py", "patched_sha256"), ("patch.diff", "patch_sha256")):
        equal(digest((root / "inputs" / file).read_bytes()), case[key], "Input snapshot drift")
    engine = read_json(root / "inputs/engine.json")["files"]
    if not engine or not all(sha(v) for v in engine.values()):
        raise ValueError("Invalid engine inventory")
    equal(tree_files(root / "inputs/engine-source"), engine, "Engine snapshot drift")
    env = read_json(root / "inputs/environment.json")
    require_keys(env, {"host", "docker", "image"}, "Environment")
    image = report["identities"]["image"]
    executor = DockerExecutor(image)  # Validates identity syntax only; never calls Docker.
    equal(report["identities"], bindings(case, env, engine, image), "Resolved execution bindings drift")
    equal(read_json(root / "inputs/execution.json"), report["identities"], "Pre-execution binding drift")
    equal(report["limitations"], LIMITATIONS, "Missing or changed limitations")
    failure = report["failure"]
    if failure is not None:
        require_keys(failure, {"stage", "kind", "detail"}, "Failure")
        if (failure["stage"] not in {"preflight", "patch", "execution"} or
                failure["kind"] not in {"INTEGRITY_ERROR", "INFRA_ERROR"} or
                not isinstance(failure["detail"], str) or not failure["detail"]):
            raise ValueError("Invalid failure attribution")
    rows = report["observations"]
    if not isinstance(rows, list) or len(rows) > len(schedule(case, oracle)):
        raise ValueError("Invalid observation count")
    if rows or not failure:
        if not isinstance(env["docker"], dict) or not isinstance(env["image"], dict):
            raise ValueError("Executed observations require Docker environment identities")
        equal(env["image"]["Id"], image, "Observed image drift")
        steps = read_json(root / "patch-steps.json")["steps"]
        if len(steps) != 3 or any(s["exit_code"] != 0 or s["timeout"] or s["error"] for s in steps):
            raise ValueError("Executed observations require successful patch preparation")
        for step in steps:
            safe_path(root, step["log"]).read_bytes()
    probes = {p["id"]: p for p in oracle["probes"]}
    seen = set()
    for row in rows:
        require_keys(row, ROW_KEYS, "Function observation")
        request = row["request"]
        require_keys(request, {"protocol", "request_id", "args"}, "Request")
        rid = request["request_id"]
        if not isinstance(rid, str) or not re.fullmatch(r"[0-9a-f]{32}", rid) or rid in seen:
            raise ValueError("Invalid or duplicate request ID")
        seen.add(rid)
        probe = probes[row["probe_id"]]
        equal(request, {"protocol": 1, "request_id": rid, "args": probe["args"]}, "Request differs from host oracle")
        if row["phase"] not in {"before", "after"} or type(row["attempt"]) is not int or not 1 <= row["attempt"] <= case["repeats"]:
            raise ValueError("Invalid observation phase/repeat")
        equal(row["container_name"], "patchreplay-function-" + rid, "Container correlation mismatch")
        for flag in ("timeout", "overflow", "container_removed", "input_changed"):
            if type(row[flag]) is not bool:
                raise ValueError("Invalid transport flag")
        for key in ("error", "cleanup_error"):
            if row[key] is not None and (not isinstance(row[key], str) or not row[key]):
                raise ValueError("Invalid transport error")
        if row["container_removed"] != (row["cleanup_error"] is None):
            raise ValueError("Contradictory cleanup result")
        if row["exit_code"] is not None and type(row["exit_code"]) is not int:
            raise ValueError("Invalid exit code")
        elapsed = row["duration_seconds"]
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("Invalid execution duration")
        if not isinstance(row["raw_base64"], str) or len(row["raw_base64"]) > 5500:
            raise ValueError("Oversized encoded response")
        raw = base64.b64decode(row["raw_base64"], validate=True)
        equal(row["overflow"], len(raw) > MAX_RESPONSE, "Overflow flag conflicts with response")
        command = row["command"]
        if not isinstance(command, list) or not all(isinstance(v, str) for v in command):
            raise ValueError("Invalid command metadata")
        if command:
            if "--mount" not in command or command.index("--mount") + 1 >= len(command):
                raise ValueError("Missing mount metadata")
            mount = command[command.index("--mount") + 1]
            if not mount.startswith("type=bind,source=") or not mount.endswith(",target=/input,readonly"):
                raise ValueError("Invalid guest mount metadata")
            expected = executor.create_args(row["container_name"], Path.cwd(), "bug", 1)
            expected[expected.index("--mount") + 1] = mount
            expected[-3:] = ["/input/guest.py", json.dumps(request, sort_keys=True, separators=(",", ":"))]
            equal(command, expected, "Recorded command differs from execution policy")
        elif row["error"] is None:
            raise ValueError("Missing execution command")
        equal(row["observation"], interpret(row, probe["expected"]), "Guest response contradicts host observation")
    equal([report["status"], report["reason"]], list(decide(rows, case, oracle, failure)), "Report contradicts host verdict")
    equal((root / "report.html").read_text(encoding="utf-8"), render(report, case, oracle), "HTML/JSON report mismatch")


def verify(root, anchor=None):
    root = Path(root).resolve()
    report = verify_package(root, anchor)
    validate(root, report)
    return report
