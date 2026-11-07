"""Two explicitly simulated reviewer scenarios; never records human participation."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def run(evaluator, provenance, demo, signed, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    records = []
    def command(python, module, args, expected=0):
        result = subprocess.run([str(python), "-I", "-m", module, *map(str, args)], capture_output=True, text=True, timeout=300, cwd=output)
        record = {"module": module, "args": list(map(str,args)), "exit_code": result.returncode, "expected_exit": expected,
                  "stdout": result.stdout, "stderr": result.stderr}
        if result.returncode != expected:
            raise RuntimeError(json.dumps(record))
        return record
    for python in (evaluator, provenance):
        origin = subprocess.check_output([str(python), "-I", "-c", "import patchreplay; print(patchreplay.__file__)"], text=True).strip()
        if "site-packages" not in origin:
            raise ValueError("Simulated reviewer must use an installed wheel")
    demo, signed = Path(demo).resolve(), Path(signed).resolve()
    summary = json.loads((demo / "results.json").read_text())
    first = next(r for r in summary["cases"] if r["case_id"] == "boltons-fix")
    package = demo / Path(first["report"]).parent
    scenario_a = output / "maintainer"
    scenario_a.mkdir()
    subject = scenario_a / package.name
    shutil.copytree(package, subject)
    tasks = [command(evaluator, "patchreplay", ["doctor"]),
             command(evaluator, "patchreplay", ["function-list"]),
             command(evaluator, "patchreplay", ["verify", subject]),
             command(evaluator, "patchreplay", ["check", demo / "success_count.json"]),
             command(evaluator, "patchreplay", ["check", demo / "regression_all.json"]),
             command(evaluator, "patchreplay", ["claim-draft", subject, "--kind", "regression_all", "--output", scenario_a / "draft.json"]),
             command(evaluator, "patchreplay", ["check", scenario_a / "draft.json"], expected=1)]
    records.append({"scenario": "maintainer", "mode": "SIMULATED_AUTOMATED", "tasks": tasks, "passed": True})
    scenario_b = output / "recipient"
    scenario_b.mkdir()
    bundle = scenario_b / "bundle"
    shutil.copytree(signed / "bundle", bundle)
    key, expectation = signed / "trust/public.pem", signed / "trust/expected.json"
    tasks = [command(provenance, "patchreplay_provenance", ["verify", "--bundle", bundle, "--trusted-key", key, "--expectation", expectation])]
    wrong = json.loads(expectation.read_text())
    wrong["run_id"] = "wrong-expected-run"
    (scenario_b / "wrong.json").write_text(json.dumps(wrong), encoding="utf-8")
    tasks.append(command(provenance, "patchreplay_provenance", ["verify", "--bundle", bundle, "--trusted-key", key, "--expectation", scenario_b / "wrong.json"], expected=1))
    tasks.append(command(provenance, "patchreplay", ["replay", subject, "--output", scenario_b / "wrong-env"], expected=2))
    tasks.append(command(evaluator, "patchreplay", ["replay", subject, "--output", scenario_b / "replays"]))
    report = bundle / "artifacts/report.json"
    report.write_bytes(report.read_bytes() + b"\n")
    tasks.append(command(provenance, "patchreplay_provenance", ["verify", "--bundle", bundle, "--trusted-key", key, "--expectation", expectation], expected=1))
    records.append({"scenario": "evidence-recipient", "mode": "SIMULATED_AUTOMATED", "tasks": tasks, "passed": True})
    result = {"schema_version": 1, "mode": "SIMULATED_AUTOMATED", "human_participants": 0,
              "scope": "Two scripted roles in isolated installed-wheel environments. No human usability or comprehension result is claimed.", "scenarios": records}
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("evaluator-python", "provenance-python", "demo", "signed", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = run(args.evaluator_python.resolve(), args.provenance_python.resolve(), args.demo, args.signed, args.output)
    print(json.dumps({"mode": result["mode"], "human_participants": 0, "scenarios_passed": len(result["scenarios"])}))
