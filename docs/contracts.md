# Contracts and artifacts (schema version 1)

This page describes legacy pytest case/report/claim version 1. Phase 3 adds
separate `function-case.schema.json` (case version 1) and
`function-report.schema.json` (report version 2, `host-function-v1`). See the
[function contract and validator](function-workflow.md). The manifest stays version 1;
legacy EvidenceCI claims do not silently accept the new evaluation kind.

`CaseSpec` is a frozen dataclass with strict runtime validation. Claim manifests
are validated with closed key sets and typed predicates in `claims.py`.
Public JSON Schemas under `schemas/` support editor integration; runtime
cross-field, file-integrity and decision checks remain authoritative.

## Case

Required fields: `schema_version`, `case_id`, `title`, `source_id`,
`source_revision`, `patch`, `patch_sha256`, `evaluator_id`, `evaluator_sha256`,
`suite_id`, `suite_sha256`, `repeats`, `timeout_seconds`, `required_pytest`.
The patch path is relative to the case JSON directory; `..` is forbidden.
Repetitions are integers 1–5; timeout is finite and 0.05–60 seconds. Exact pytest
versions are required. Unknown fields, duplicate JSON keys, NaN, infinity and
booleans used as counts are rejected.

Suite membership pins all execution-relevant case fields. The suite hash is
calculated over its member mapping, excluding titles, patch file locations and
the suite hash itself to avoid circular identities. The case hash includes the
entire saved case, with its patch path normalized to `patch.diff`.

## Run package

```text
<case-id>-<unique-run-id>/
  report.json                 # Verdict, identities, checks, steps, scope
  report.html                 # Offline reviewer report
  manifest.json               # SHA-256 of every other file
  inputs/
    case.json                 # Normalized, replayable case
    patch.diff                # Exact bytes evaluated
    source/                   # Baseline snapshot (after admission)
    patched-source/           # Patched snapshot (after application)
    evaluator/                # Reviewed tests and node contract
    suite.json                # Full declared roster and suite identity
    environment.json          # Python, platform, packages, Git, policy
    requirements.txt          # Observed installed distributions
    engine.json               # Version and source-file hashes
    engine-source/            # Evaluator implementation and template
  checks/<phase>-<attempt>.json
  checks/<phase>-<attempt>.xml # JUnit, when pytest produced it
  logs/<phase>-<attempt>.log
  logs/git-init.log
  logs/patch-check.log
  logs/patch-apply.log
```

Artifacts that were never produced are absent and references are null. A failed
preflight still has the case, patch, environment, engine, suite and report; it
has no fabricated check logs. Durations are monotonic wall-clock seconds,
exit codes are process return values (or null when spawn failed), and timeout
is recorded separately. Commands are argv arrays, never shell strings.

The manifest excludes itself. Its byte SHA-256 is pinned by a separate claim.
Changing any file, omitting a file, or adding a file invalidates the package.
Do not write claim verification output inside an existing sealed package.

## Claim manifest

Generate real examples using `patchreplay demo`. The minimal shape is:

```json
{
  "schema_version": 1,
  "claim_id": "reviewed-regression-claim",
  "text": "The good patch passes all declared regression checks.",
  "kind": "regression_all",
  "scope": {
    "suite_id": "synthetic-clamp-v1",
    "suite_sha256": "<64 lowercase hex characters>",
    "case_ids": ["good"]
  },
  "assertion": {
    "numerator": 1,
    "denominator": 1,
    "denominator_policy": "all_declared_cases"
  },
  "evidence": [{
    "case_id": "good",
    "package": "good-<run-id>",
    "manifest_sha256": "<SHA-256 of manifest.json bytes>",
    "expected": {
      "source_revision": "sha256:<tree hash>",
      "patch_sha256": "<hash>",
      "evaluator_sha256": "<hash>",
      "suite_sha256": "<hash>",
      "environment_sha256": "<hash>",
      "engine_sha256": "<hash>",
      "case_sha256": "<hash>",
      "inputs_sha256": "<hash>"
    }
  }]
}
```

Placeholders above are illustrative and deliberately not valid hashes. Use
the hashes from the reviewed package in a real manifest. Package paths resolve
relative to the claim file's directory, or an explicit `--evidence-root`.
Claims cannot escape that root. Reordered distinct references are allowed;
duplicate cases/runs, incomplete rosters and cherry-picked suite counts are not.

## Consumer compatibility

Consumers must require schema version 1 and known statuses. New statuses or
schema versions must fail closed. `check` emits machine-readable JSON with
`status`, `reason`, and, when arithmetic is possible, `observed` and `asserted`.
There is no implication that `text` was semantically validated. Snapshot hashes
are byte-sensitive; use the repository's LF checkout policy.
