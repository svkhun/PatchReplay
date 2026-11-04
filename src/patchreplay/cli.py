"""Small command surface with stable automation-friendly exit codes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from . import __version__
from .claims import check_claim, validate_report
from .contracts import Status
from .engine import DATA, environment, evaluate, replay
from .executors import DockerExecutor
from .integrity import read_json, verify_package, write_json


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="patchreplay", description="Turn a bug fix into a replayable evidence package. Controlled fixtures only.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Inspect Python, pytest, Git and available container engines")
    sub.add_parser("list", help="List bundled cases")
    sub.add_parser("function-list", help="List reviewed host-function cases (Docker only)")
    function = sub.add_parser("function-run", help="Evaluate a registered integer function with a host-owned oracle")
    function.add_argument("case", help="Registered function case name; external paths are rejected")
    function.add_argument("--image", required=True, help="Immutable local Docker image ID")
    function.add_argument("--output", type=Path, default=Path(".patchreplay/function-runs"))
    export = sub.add_parser("examples", help="Copy editable case specifications and patches for inspection")
    export.add_argument("destination", type=Path)
    run = sub.add_parser("run", help="Evaluate a bundled name or case JSON file")
    run.add_argument("case")
    run.add_argument("--executor", choices=["local", "docker"], default="local")
    run.add_argument("--image", help="Immutable local Docker image ID; required for --executor docker")
    run.add_argument("--output", type=Path, default=Path(".patchreplay/runs"))
    rep = sub.add_parser("replay", help="Verify and rerun a package under identical recorded inputs")
    rep.add_argument("package", type=Path)
    rep.add_argument("--output", type=Path, default=Path(".patchreplay/replays"))
    verify = sub.add_parser("verify", help="Verify package integrity and decision consistency")
    verify.add_argument("package", type=Path)
    verify.add_argument("--manifest-sha256", help="Optional separately trusted manifest anchor")
    check = sub.add_parser("check", help="Check an explicit EvidenceCI claim manifest")
    check.add_argument("manifest", type=Path)
    check.add_argument("--evidence-root", type=Path)
    check.add_argument("--output", type=Path)
    demo = sub.add_parser("demo", help="Run all synthetic cases and claim examples")
    demo.add_argument("--output", type=Path, default=Path("demo-output"))
    return p


def doctor() -> dict:
    state = environment()
    engines = {}
    for name in ("docker", "podman"):
        executable = shutil.which(name)
        detail = {"available": bool(executable), "responsive": False}
        if executable:
            try:
                command = [executable, "info"]
                proc = subprocess.run(command, capture_output=True, text=True, timeout=5)
                detail["responsive"] = proc.returncode == 0
                detail["exit_code"] = proc.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                detail["error"] = type(exc).__name__
        engines[name] = detail
    return {"environment": state, "container_engines": engines, "selected_executor": "controlled-fixtures-v1",
            "external_repositories_supported": False,
            "note": "Docker fixture executor is experimental; external repositories remain disabled.",
            "ready": state["packages"].get("pytest") == "8.3.5" and bool(state["git"])}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
            print(json.dumps(result, indent=2))
            return 0 if result["ready"] else 2
        if args.command == "list":
            print("\n".join(p.stem for p in sorted((DATA / "cases").glob("*.json"))))
            return 0
        if args.command == "function-list":
            from .function.workflow import DATA as FUNCTION_DATA, load_registered
            names = sorted(read_json(FUNCTION_DATA / "suite.json")["members"])
            for name in names:
                load_registered(name)
            print("\n".join(names))
            return 0
        if args.command == "function-run":
            from .function.workflow import evaluate as evaluate_function
            folder = evaluate_function(args.case, args.image, args.output)
            report = read_json(folder / "report.json")
            print(json.dumps({"status": report["status"], "reason": report["reason"], "package": str(folder),
                              "report": str(folder / "report.html")}, indent=2))
            return 0 if report["status"] == Status.VERIFIED.value else 1
        if args.command == "examples":
            if args.destination.exists():
                raise ValueError("Destination already exists; choose a new directory")
            shutil.copytree(DATA / "cases", args.destination)
            print(args.destination.resolve())
            return 0
        if args.command in {"run", "replay"}:
            if args.command == "run":
                candidate = Path(args.case)
                if not candidate.exists():
                    # Only exact known names can select packaged fixtures.
                    available = {p.stem: p for p in (DATA / "cases").glob("*.json")}
                    if args.case not in available:
                        raise ValueError(f"Unknown case: {args.case}. Use 'patchreplay list'.")
                    candidate = available[args.case]
                if args.executor == "docker" and not args.image:
                    raise ValueError("--executor docker requires --image sha256:<local immutable image ID>")
                if args.executor == "local" and args.image:
                    raise ValueError("--image requires --executor docker")
                folder = evaluate(candidate, args.output, DockerExecutor(args.image) if args.executor == "docker" else None)
            else:
                recorded = verify_package(args.package.resolve())
                if recorded.get("evaluation_kind") == "host-function-v1":
                    from .function.workflow import replay as replay_function
                    folder = replay_function(args.package, args.output)
                else:
                    folder = replay(args.package.resolve(), args.output)
            report = read_json(folder / "report.json")
            print(json.dumps({"status": report["status"], "reason": report["reason"], "package": str(folder), "report": str(folder / "report.html")}, indent=2))
            return 0 if report["status"] == Status.VERIFIED.value else 1
        if args.command == "verify":
            report = verify_package(args.package.resolve(), args.manifest_sha256)
            if report.get("evaluation_kind") == "host-function-v1":
                from .function.evidence import validate
                validate(args.package.resolve(), report)
            else:
                validate_report(args.package.resolve(), report)
            print(json.dumps({"integrity": "CONSISTENT", "anchored": bool(args.manifest_sha256), "status": report["status"]}))
            return 0
        if args.command == "check":
            result = check_claim(args.manifest, args.evidence_root)
            if args.output:
                write_json(args.output, result)
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "SUPPORTED_FOR_SCOPE" else 1
        if args.command == "demo":
            from .demo import demo
            result = demo(args.output.resolve())
            print(f'Expected outcomes matched: {result["expectations_met"]}')
            print(f'Report: {(args.output / "index.html").resolve()}')
            return 0 if result["expectations_met"] else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"patchreplay: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 2


def evidence_main() -> int:
    return main(["check", *sys.argv[1:]])
