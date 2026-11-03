"""Optional release QA with jsonschema==4.23.0 and PyYAML==6.0.2.

These are developer tools, not dependencies of the evaluator. An isolated
--qa-deps directory keeps the observed evaluator environment unchanged.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa-deps", type=Path)
    parser.add_argument("--demo", type=Path, default=ROOT / "examples" / "evidence")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "verification" / "schema-results.json")
    args = parser.parse_args()
    if args.qa_deps:
        sys.path.insert(0, str(args.qa_deps.resolve()))
    from jsonschema import Draft202012Validator
    import yaml

    validators = {}
    for path in (ROOT / "schemas").glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validators[path.name.split(".")[0]] = Draft202012Validator(schema)
    files = [("case", p) for p in (ROOT / "src" / "patchreplay" / "data" / "cases").glob("*.json")]
    files.extend(("claim", p) for p in args.demo.glob("claim-*.json"))
    for folder in args.demo.iterdir():
        if folder.is_dir() and (folder / "manifest.json").is_file():
            files.extend((name, folder / relative) for name, relative in
                         (("report", "report.json"), ("manifest", "manifest.json"), ("case", "inputs/case.json")))
    for name, path in files:
        validators[name].validate(json.loads(path.read_text(encoding="utf-8")))
    workflow = yaml.load((ROOT / ".github" / "workflows" / "ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"push", "pull_request"}
    assert workflow["permissions"] == {"contents": "read"}
    assert len(workflow["jobs"]["controlled-fixtures"]["strategy"]["matrix"]["os"]) == 2
    result = {"schema_version": 1, "passed": True, "schemas": len(validators), "validated_artifacts": len(files),
              "ci_yaml": "parsed; execution on GitHub was not performed"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
