"""Generate editor-facing JSON Schemas; cross-field rules also run in Python."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from patchreplay.contracts import Status
from patchreplay.integrity import write_json

STRING = {"type": "string"}
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
REVISION = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
NAME = {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]{0,79}$"}
COUNT = {"type": "integer", "minimum": 0}
PATH = {"type": "string", "minLength": 1, "description": "Relative path; runtime rejects traversal, links, device names and reserved characters."}


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def array(items):
    return {"type": "array", "items": items}


def save(name, schema):
    write_json(ROOT / "schemas" / f"{name}.schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "title": f"PatchReplay {name} v1", **schema})


def main():
    ids = obj({"source_revision": REVISION, **{k: HASH for k in
              ("patch_sha256", "evaluator_sha256", "suite_sha256", "environment_sha256", "engine_sha256", "case_sha256", "inputs_sha256")}})
    save("case", obj({"schema_version": {"const": 1}, "case_id": NAME, "title": {"type": "string", "minLength": 1, "maxLength": 300},
        "source_id": NAME, "source_revision": REVISION, "patch": PATH, "patch_sha256": HASH,
        "evaluator_id": NAME, "evaluator_sha256": HASH, "suite_id": NAME, "suite_sha256": HASH,
        "repeats": {"type": "integer", "minimum": 1, "maximum": 5},
        "timeout_seconds": {"type": "number", "minimum": 0.05, "maximum": 60},
        "required_pytest": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"}}))
    save("claim", obj({"schema_version": {"const": 1}, "claim_id": {"type": "string", "minLength": 1},
        "text": {"type": "string", "minLength": 1}, "kind": {"enum": ["success_count", "regression_all"]},
        "scope": obj({"suite_id": STRING, "suite_sha256": HASH, "case_ids": {**array(NAME), "minItems": 1, "uniqueItems": True}}),
        "assertion": obj({"numerator": COUNT, "denominator": COUNT, "denominator_policy": {"const": "all_declared_cases"}}),
        "evidence": array(obj({"case_id": NAME, "package": PATH, "manifest_sha256": HASH, "expected": ids}))}))
    process = {"command": array(STRING), "exit_code": {"type": ["integer", "null"]}, "timeout": {"type": "boolean"},
               "duration_seconds": {"type": "number", "minimum": 0}, "error": {"type": ["string", "null"]}, "log": PATH}
    check = obj({**process, "id": STRING, "phase": {"enum": ["before_bug", "before_regression", "after_bug", "after_regression"]},
                 "attempt": {"type": "integer", "minimum": 1},
                 "outcome": {"enum": ["PASS", "EXPECTED_FAILURE", "FAIL", "CHECK_ERROR", "INFRA_ERROR", "INTEGRITY_ERROR", "TIMEOUT"]},
                 "signature": HASH, "expected_nodes": array(STRING), "records": {"type": ["string", "null"]}, "junit": {"type": ["string", "null"]}})
    save("report", obj({"schema_version": {"const": 1}, "case_id": NAME, "title": STRING, "run_id": STRING,
        "created_at": {"type": "string", "format": "date-time"}, "evaluator_version": STRING, "suite_id": NAME,
        "identities": ids, "executor": {"const": "controlled-fixtures-v1"}, "repeats": {"type": "integer", "minimum": 1},
        "timeout_seconds": {"type": "number", "minimum": 0.05}, "checks": array(check), "steps": array(obj({**process, "kind": STRING})),
        "limitations": array(STRING), "replay": STRING, "cache": obj({"enabled": {"const": False}, "reason": STRING}),
        "status": {"enum": [s.value for s in Status]}, "reason": STRING}))
    save("manifest", obj({"schema_version": {"const": 1}, "algorithm": {"const": "sha256"},
                           "files": {"type": "object", "additionalProperties": HASH, "required": ["report.json"]}}))


if __name__ == "__main__":
    main()
