"""Local controlled-fixture evaluator and self-contained evidence packaging."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.metadata
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

from . import __version__
from .contracts import CaseSpec, PHASES, Status, decide
from .integrity import IntegrityError, digest, fixture_hash, identity, patch_paths, read_json, safe_path, seal_package, tree_files, tree_hash, write_json
from .process import clean_environment, execute
from .executors import LocalExecutor, DockerExecutor

PACKAGE = Path(__file__).resolve().parent
DATA = PACKAGE / "data"
POLICY = "controlled-fixtures-v1"
LIMITATIONS = [
    "Synthetic controlled fixtures only; this is not a coding-agent benchmark or evidence of general correctness.",
    "The local executor is not a security sandbox. External repositories and unregistered patches are rejected.",
    "A clean environment removes inherited credentials; it does not restrict host filesystem access or network access.",
    "Timeouts and repeated observations bound this evaluation; they cannot prove determinism or absence of flakes.",
    "SHA-256 detects changes relative to a trusted manifest anchor; it does not authenticate the producer.",
    "Replay records dependencies and platform identity but does not snapshot the OS, hardware, or scheduling.",
]


def engine_files() -> dict[str, str]:
    paths = [*PACKAGE.glob("*.py"), *PACKAGE.glob("templates/*.html")]
    return {p.relative_to(PACKAGE).as_posix(): digest(p.read_bytes()) for p in sorted(paths)}


def environment() -> dict:
    git = shutil.which("git")
    git_version = None
    if git:
        try:
            with tempfile.TemporaryDirectory(prefix="patchreplay-probe-") as tmp:
                git_version = subprocess.run([git, "--version"], env=clean_environment(Path(tmp)),
                                             capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    packages = {d.metadata["Name"].lower(): d.version for d in importlib.metadata.distributions() if d.metadata["Name"]}
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "platform": platform.platform(), "machine": platform.machine(), "packages": dict(sorted(packages.items())),
            "git": git_version, "executor": POLICY}


def load_case(path: Path) -> tuple[CaseSpec, bytes]:
    case = CaseSpec.parse(read_json(path))
    patch_file = safe_path(path.parent.resolve(), case.patch)
    return case, patch_file.read_bytes()


def approved_inputs(case: CaseSpec, patch: bytes) -> tuple[Path, Path, dict]:
    catalog = read_json(DATA / "catalog.json")
    source = safe_path(DATA / "sources", case.source_id)
    evaluator = safe_path(DATA / "evaluators", case.evaluator_id)
    if case.source_id not in catalog["sources"] or case.evaluator_id not in catalog["evaluators"]:
        raise IntegrityError("Only registered, controlled fixture sources and evaluators may execute")
    if fixture_hash(source) != catalog["sources"][case.source_id] or case.source_revision != "sha256:" + fixture_hash(source):
        raise IntegrityError("Source snapshot changed or does not match its revision")
    if fixture_hash(evaluator) != catalog["evaluators"][case.evaluator_id] or case.evaluator_sha256 != fixture_hash(evaluator):
        raise IntegrityError("Approved evaluator changed or does not match the pinned identity")
    if digest(patch) != case.patch_sha256:
        raise IntegrityError("Patch bytes do not match the case's hash")
    contract = read_json(evaluator / "contract.json")
    touched = patch_paths(patch)
    if not touched.issubset(set(contract["patchable_paths"])):
        raise IntegrityError("Patch touches protected evaluator/tests or a path outside the source allowlist: " + ", ".join(sorted(touched)))
    if case.patch_sha256 not in catalog["patches"].values():
        raise IntegrityError("Unregistered patch: external code requires a future isolated executor")
    suite = read_json(DATA / "suite.json")
    declared = {k: v for k, v in case.as_dict().items() if k not in {"patch", "title", "suite_sha256"}}
    if (case.suite_id != suite["suite_id"] or case.suite_sha256 != suite["suite_sha256"]
            or identity(suite["members"]) != suite["suite_sha256"]
            or suite["suite_sha256"] != catalog["suite_sha256"]
            or suite["members"].get(case.case_id) != declared):
        raise IntegrityError("Case does not match its approved suite member; review and version evaluator inputs first")
    return source, evaluator, contract


def interpret(result: dict, expected: list[str], phase: str, exit_code: int) -> tuple[str, str]:
    """Interpret pytest records, not stdout or exit code alone."""
    if not isinstance(result, dict) or result.get("exit_code") != exit_code or not isinstance(result.get("records"), list):
        return "INFRA_ERROR", identity({"invalid_result": True})
    records = result["records"]
    if any(not isinstance(r, dict) or set(r) != {"node", "when", "outcome", "exception"}
           or r["node"] not in expected or r["when"] not in {"setup", "call", "teardown"}
           or r["outcome"] not in {"passed", "failed", "skipped"}
           or (r["exception"] is not None and not isinstance(r["exception"], str)) for r in records):
        return "INFRA_ERROR", identity({"invalid_records": True})
    signature = identity({"exit_code": exit_code, "records": records})
    if exit_code in (2, 4, 5):
        return "CHECK_ERROR", signature  # Collection, usage, or no tests; never a reproduced assertion.
    if exit_code not in (0, 1):
        return "INFRA_ERROR", signature
    complete = len(records) == len(expected) * 3 and all(
        sum(r["node"] == node and r["when"] == when for r in records) == 1
        for node in expected for when in ("setup", "call", "teardown")
    )
    if not complete:
        return "CHECK_ERROR", signature
    if any(r["outcome"] == "skipped" for r in records):
        return "CHECK_ERROR", signature
    clean_lifecycle = all(r["outcome"] == "passed" for r in records if r["when"] != "call")
    calls = [r for r in records if r["when"] == "call"]
    if clean_lifecycle and all(r["outcome"] == "passed" for r in calls) and exit_code == 0:
        return "PASS", signature
    if clean_lifecycle and exit_code == 1:
        if phase == "before_bug" and all(r["outcome"] == "failed" and r["exception"] == "AssertionError" for r in calls):
            return "EXPECTED_FAILURE", signature
        return "FAIL", signature
    return "CHECK_ERROR", signature


def run_check(root: Path, work: Path, source: Path, evaluator: Path, contract: dict, case: CaseSpec,
              phase: str, attempt: int, executor=None) -> dict:
    executor = executor or LocalExecutor()
    check_id = f"{phase}-{attempt}"
    folder = work / check_id
    folder.mkdir()
    shutil.copytree(source, folder / "source")
    shutil.copytree(evaluator, folder / "evaluator", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(PACKAGE / "worker.py", folder / "worker.py")
    executor.prepare(folder)
    baseline = tree_files(folder)
    result_path = root / "checks" / f"{check_id}.json"
    log = root / "logs" / f"{check_id}.log"
    selection = "bug" if phase.endswith("bug") else "regression"
    command = [sys.executable, "-I", "-B", str(folder / "worker.py"), str(folder / "source"),
               str(folder / "evaluator"), selection, str(result_path), str(attempt)]
    result = executor.check(command, folder, clean_environment(work / "homes" / check_id), case.timeout_seconds, log)
    outcome = "INFRA_ERROR"
    signature = identity({"process_error": result["error"]})
    if result["timeout"]:
        outcome = "TIMEOUT"
    elif not result["error"] and result_path.exists():
        try:
            outcome, signature = interpret(read_json(result_path), contract[selection], phase, result["exit_code"])
        except (ValueError, OSError):
            outcome = "INFRA_ERROR"
    if tree_files(folder) != baseline:
        outcome = "INTEGRITY_ERROR"
    return {**result, "id": check_id, "phase": phase, "attempt": attempt, "outcome": outcome,
            "signature": signature, "expected_nodes": contract[selection],
            "log": log.relative_to(root).as_posix(),
            "records": result_path.relative_to(root).as_posix() if result_path.exists() else None,
            "junit": result_path.with_suffix(".xml").relative_to(root).as_posix() if result_path.with_suffix(".xml").exists() else None}


def evaluate(case_path: Path, output: Path, executor=None) -> Path:
    executor = executor or LocalExecutor()
    case, patch = load_case(case_path.resolve())
    output = output.resolve()
    if output.is_relative_to(PACKAGE):
        raise ValueError("Evidence output must be outside the installed package")
    if any((parent / "manifest.json").is_file() for parent in (output, *output.parents)):
        raise ValueError("Evidence output must not be inside an already sealed package")
    run_id = f"{case.case_id}-{uuid.uuid4().hex[:12]}"
    root = output / run_id
    root.mkdir(parents=True, exist_ok=False)
    (root / "checks").mkdir()
    env = environment()
    if isinstance(executor, DockerExecutor):
        env["container"] = executor.identity()
    inputs = root / "inputs"
    inputs.mkdir()
    normalized = {**case.as_dict(), "patch": "patch.diff"}
    write_json(inputs / "case.json", normalized)
    (inputs / "patch.diff").write_bytes(patch)
    write_json(inputs / "environment.json", env)
    write_json(inputs / "engine.json", {"version": __version__, "files": engine_files()})
    for relative in engine_files():
        destination = inputs / "engine-source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PACKAGE / relative, destination)
    (inputs / "requirements.txt").write_text(
        "# Observed environment; install PatchReplay from the matching source separately.\n" +
        "".join(f"{name}=={version}\n" for name, version in env["packages"].items() if name != "patchreplay"),
        encoding="utf-8", newline="\n")
    shutil.copy2(DATA / "suite.json", inputs / "suite.json")
    ids = {"source_revision": case.source_revision, "patch_sha256": case.patch_sha256,
           "evaluator_sha256": case.evaluator_sha256, "suite_sha256": case.suite_sha256,
           "environment_sha256": identity(env), "engine_sha256": identity(engine_files()),
           "case_sha256": identity(normalized)}
    ids["inputs_sha256"] = identity(ids)
    report = {"schema_version": 1, "case_id": case.case_id, "title": case.title, "run_id": run_id,
              "created_at": datetime.now(timezone.utc).isoformat(), "evaluator_version": __version__,
              "suite_id": case.suite_id, "identities": ids, "executor": executor.policy,
              "repeats": case.repeats, "timeout_seconds": case.timeout_seconds,
              "checks": [], "steps": [], "limitations": LIMITATIONS,
              "replay": "python -m patchreplay replay <this-package-directory> --output replay-output",
              "cache": {"enabled": False, "reason": "MVP always executes; identities are reserved for future exact-input cache keys."}}
    try:
        source, evaluator, contract = approved_inputs(case, patch)
        if isinstance(executor, DockerExecutor):
            executor.preflight()
            report["limitations"] = [line for line in LIMITATIONS if "local executor" not in line and "clean environment" not in line] + [
                "Container policy is experimental and admitted fixtures only. Same-container code can forge pytest observations; external patches remain disabled.",
                "Container checks use a read-only fixture mount, disabled network and resource limits. These controls are not a security certification."]
        shutil.copytree(source, inputs / "source", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(evaluator, inputs / "evaluator", ignore=shutil.ignore_patterns("__pycache__"))
        if env["packages"].get("pytest") != case.required_pytest or not env["git"]:
            report["status"] = Status.INFRA.value
            report["reason"] = f"Environment preflight failed: pytest {case.required_pytest} and usable Git are required. Nothing was installed."
        else:
            with tempfile.TemporaryDirectory(prefix="patchreplay-") as tmp:
                work = Path(tmp)
                pristine = work / "pristine"
                shutil.copytree(source, pristine, ignore=shutil.ignore_patterns("__pycache__"))
                patched = work / "patched"
                shutil.copytree(source, patched, ignore=shutil.ignore_patterns("__pycache__"))
                git = shutil.which("git")
                # An empty .git boundary prevents a parent repository from affecting git apply.
                init = execute([git, "init", "--quiet", str(patched)], work, clean_environment(work / "git-home"), 10, root / "logs" / "git-init.log")
                report["steps"].append({**init, "kind": "git_init", "log": "logs/git-init.log"})
                if init["error"] or init["timeout"] or init["exit_code"] != 0:
                    report.update(status=Status.INFRA.value, reason="Could not initialize the disposable patch workspace.")
                else:
                    for operation in ("check", "apply"):
                        args = [git, "-c", "core.autocrlf=false", "apply", "--whitespace=error-all"]
                        if operation == "check":
                            args.append("--check")
                        args.append(str(inputs / "patch.diff"))
                        step = execute(args, patched, clean_environment(work / "git-home"), 10, root / "logs" / f"patch-{operation}.log")
                        report["steps"].append({**step, "kind": f"patch_{operation}", "log": f"logs/patch-{operation}.log"})
                        if step["error"] or step["timeout"] or step["exit_code"] != 0:
                            status = Status.INFRA if step["error"] or step["timeout"] else Status.FIX_FAILED
                            report.update(status=status.value, reason=f"Patch {operation} did not complete successfully; see the patch log.")
                            break
                    else:
                        # Copy only known files; .git is never passed to executed fixtures or the evidence snapshot.
                        patched_clean = work / "patched-clean"
                        shutil.copytree(patched, patched_clean, ignore=shutil.ignore_patterns(".git"))
                        for rel in contract["protected_source_paths"]:
                            if (pristine / rel).read_bytes() != (patched_clean / rel).read_bytes():
                                raise IntegrityError(f"Protected file changed after git apply: {rel}")
                        shutil.copytree(patched_clean, inputs / "patched-source")
                        for attempt in range(1, case.repeats + 1):
                            for phase in PHASES:
                                selected = pristine if phase.startswith("before") else patched_clean
                                report["checks"].append(run_check(root, work, selected, evaluator, contract, case, phase, attempt, executor))
                        status, reason = decide(report["checks"], case.repeats)
                        report.update(status=status.value, reason=reason)
    except IntegrityError as exc:
        report.update(status=Status.INTEGRITY.value, reason=str(exc))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report.update(status=Status.INFRA.value, reason=f"{type(exc).__name__}: {exc}")
    write_json(root / "report.json", report)
    from .reporting import render_report
    render_report(root, report)
    seal_package(root)
    return root


def replay(package: Path, output: Path) -> Path:
    from .integrity import verify_package
    from .claims import validate_report
    report = verify_package(package)
    validate_report(package, report)
    if report["identities"]["engine_sha256"] != identity(engine_files()):
        raise IntegrityError("Evaluator engine changed. Restore the recorded version before exact-input replay.")
    current_env = environment()
    executor = None
    recorded = read_json(package / "inputs" / "environment.json")
    if "container" in recorded:
        executor = DockerExecutor(recorded["container"]["image"])
        current_env["container"] = executor.identity()
    if report["identities"]["environment_sha256"] != identity(current_env):
        raise IntegrityError("Environment changed. Restore recorded Python, packages, Git and platform before exact-input replay.")
    return evaluate(package / "inputs" / "case.json", output, executor)
