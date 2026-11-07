"""Registered function workflow, immutable input snapshots and exact-input replay."""
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import uuid

from patchreplay.engine import PACKAGE, environment
from patchreplay.executors import DockerExecutor
from patchreplay.integrity import (IntegrityError, digest, identity, patch_paths, read_json,
                                   seal_package, tree_files, tree_hash, write_json)
from patchreplay.process import clean_environment, execute
from .contract import KIND, POLICY, LIMITATIONS, limitations, equal, parse_case, parse_oracle, schedule, decide
from .transport import observe

DATA = PACKAGE / "data/function"
SUITE_SHA256 = "fb14a31914cffe1561190499720a8aa806347ff68e709b9834660fc21bb91ddd"
REAL_DATA = PACKAGE / "data/real"
REAL_SUITE_SHA256 = "ce24a56d3335e09081d61ffd28aa51d6e48f9315cc258e166e17183485c2880d"


def registered_names():
    return sorted([*read_json(DATA / "suite.json")["members"], *read_json(REAL_DATA / "suite.json")["members"]])


def engine_files():
    paths = [*PACKAGE.glob("*.py"), *(PACKAGE / "function").glob("*.py")]
    return {p.relative_to(PACKAGE).as_posix(): digest(p.read_bytes()) for p in sorted(paths)}


def load_registered(name):
    data = REAL_DATA if name in read_json(REAL_DATA / "suite.json")["members"] else DATA
    suite = read_json(data / "suite.json")
    equal(identity(suite), REAL_SUITE_SHA256 if data == REAL_DATA else SUITE_SHA256, "Registered function suite drift")
    if name not in suite["members"]:
        raise IntegrityError("Only registered function case names are admitted; use function-list")
    folder = data / name
    case = parse_case(read_json(folder / "case.json"))
    equal(case, {**suite["members"][name], "suite_sha256": identity(suite)}, "Registered case drift")
    oracle = parse_oracle(read_json(folder / "oracle.json" if data == REAL_DATA else DATA / "oracle.json"))
    if case["schema_version"] == 2:
        equal(tree_hash(folder / "provenance"), case["provenance_sha256"], "Upstream provenance drift")
    equal(identity(oracle), case["evaluator_sha256"], "Registered evaluator drift")
    source, patch, patched = [(folder / file).read_bytes() for file in ("source.py", "patch.diff", "patched.py")]
    for value, key in ((source, "source_sha256"), (patch, "patch_sha256"), (patched, "patched_sha256")):
        equal(digest(value), case[key], "Registered input drift: " + key)
    equal(sorted(patch_paths(patch)), ["candidate.py"], "Patch path is not admitted")
    return case, oracle, suite, source, patch, patched


def runtime_environment(executor):
    executor.preflight()
    info = json.loads(executor.control(["info", "--format", "{{json .}}"] ))
    image = json.loads(executor.control(["image", "inspect", executor.image]))[0]
    return {"host": environment(), "docker": {k: info.get(k) for k in (
        "ServerVersion", "KernelVersion", "OSType", "Architecture", "CgroupDriver", "CgroupVersion",
        "DefaultRuntime", "SecurityOptions")},
        "image": {k: image.get(k) for k in ("Id", "Os", "Architecture")}}


def bindings(case, env, engine, image):
    values = {"source_revision": "sha256:" + case["source_sha256"],
              "patch_sha256": case["patch_sha256"], "evaluator_sha256": case["evaluator_sha256"],
              "suite_sha256": case["suite_sha256"], "case_sha256": identity(case),
              "environment_sha256": identity(env), "engine_sha256": identity(engine),
              "policy": POLICY["id"], "image": image}
    values["inputs_sha256"] = identity(values)
    return values


def apply_patch(root, scratch, source, expected):
    """Apply registered text bytes with Git; never import or execute candidate code."""
    git = shutil.which("git")
    if not git:
        raise OSError("Git is required to apply the registered patch")
    with tempfile.TemporaryDirectory(prefix="apply-", dir=scratch) as temporary:
        work = Path(temporary)
        (work / "candidate.py").write_bytes(source)
        steps = []
        commands = [[git, "init", "--quiet", str(work)],
                    [git, "-c", "core.autocrlf=false", "apply", "--check", "--whitespace=error-all", str(root / "inputs/patch.diff")],
                    [git, "-c", "core.autocrlf=false", "apply", "--whitespace=error-all", str(root / "inputs/patch.diff")]]
        for index, command in enumerate(commands):
            log = root / "logs" / f"patch-{index}.log"
            step = execute(command, work, clean_environment(work / "home"), 10, log)
            steps.append({**step, "log": log.relative_to(root).as_posix()})
            write_json(root / "patch-steps.json", {"steps": steps})
            if step["timeout"] or step["error"] or step["exit_code"] != 0:
                raise OSError("Registered patch preparation failed; inspect patch-steps.json")
        patched = (work / "candidate.py").read_bytes()
        equal(digest(patched), digest(expected), "Applied patch differs from approved result")
        return patched


def evaluate(name, image, output, *, expected_bindings=None):
    # All admission checks precede Docker and candidate execution.
    case, oracle, suite, source, patch, patched = load_registered(name)
    executor = DockerExecutor(image)
    output = Path(output).resolve()
    if output.is_relative_to(PACKAGE) or any((p / "manifest.json").exists() for p in (output, *output.parents)):
        raise ValueError("Output must be outside installed code and existing sealed evidence")
    root = output / (name + "-" + uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / "inputs"
    for file, value in (("case.json", case), ("oracle.json", oracle), ("suite.json", suite), ("policy.json", POLICY)):
        write_json(inputs / file, value)
    for file, value in (("source.py", source), ("patch.diff", patch), ("patched.py", patched)):
        (inputs / file).write_bytes(value)
    if case["schema_version"] == 2:
        shutil.copytree(REAL_DATA / name / "provenance", inputs / "provenance")
    engine = engine_files()
    write_json(inputs / "engine.json", {"files": engine})
    for relative in engine:
        target = inputs / "engine-source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((PACKAGE / relative).read_bytes())
    env = {"host": environment(), "docker": None, "image": None}
    write_json(inputs / "execution.json", bindings(case, env, engine, image))
    report = {"schema_version": 2, "evaluation_kind": KIND, "run_id": root.name, "case_id": name,
              "created_at": datetime.now(timezone.utc).isoformat(), "identities": {}, "observations": [],
              "failure": None, "status": "INFRA_ERROR", "reason": "", "limitations": limitations(case)}
    stage = "preflight"
    try:
        env = runtime_environment(executor)
        write_json(inputs / "environment.json", env)
        resolved = bindings(case, env, engine, image)
        write_json(inputs / "execution.json", resolved)
        if expected_bindings is not None:
            equal(resolved, expected_bindings, "Replay inputs changed between verification and execution")
        stage = "patch"
        with tempfile.TemporaryDirectory(prefix=".function-work-", dir=output) as temporary:
            scratch = Path(temporary)
            patched = apply_patch(root, scratch, source, patched)
            stage = "execution"
            before = tree_files(inputs)
            for phase, attempt, probe in schedule(case, oracle):
                row = observe(executor, source if phase == "before" else patched, probe, case["timeout_seconds"], scratch)
                report["observations"].append({**row, "phase": phase, "attempt": attempt, "probe_id": probe["id"]})
                if not row["container_removed"]:
                    raise OSError("Cleanup failed; remaining declared observations were not executed")
            equal(tree_files(inputs), before, "Recorded inputs changed during execution")
            equal(engine_files(), engine, "Engine changed during execution")
            load_registered(name)  # Detect source/oracle/catalog drift during execution too.
            equal(runtime_environment(executor), env, "Environment changed during execution")
    except IntegrityError as exc:
        report["failure"] = {"stage": stage, "kind": "INTEGRITY_ERROR", "detail": str(exc)}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        report["failure"] = {"stage": stage, "kind": "INFRA_ERROR", "detail": str(exc)}
    write_json(inputs / "environment.json", env)
    report["identities"] = bindings(case, env, engine, image)
    report["status"], report["reason"] = decide(report["observations"], case, oracle, report["failure"])
    write_json(root / "report.json", report)
    from .evidence import render
    (root / "report.html").write_text(render(report, case, oracle), encoding="utf-8", newline="\n")
    seal_package(root)
    return root


def replay(package, output):
    from .evidence import verify
    package = Path(package).resolve()
    report = verify(package)
    case, oracle, suite, source, patch, patched = load_registered(report["case_id"])
    equal(read_json(package / "inputs/case.json"), case, "Replay case drift")
    equal(report["identities"]["engine_sha256"], identity(engine_files()), "Replay engine drift")
    executor = DockerExecutor(report["identities"]["image"])
    equal(read_json(package / "inputs/environment.json"), runtime_environment(executor), "Replay environment/image drift")
    return evaluate(case["case_id"], executor.image, output, expected_bindings=report["identities"])
