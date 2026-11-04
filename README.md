# PatchReplay

**Turn a bug fix into a replayable evidence package.**

PatchReplay evaluates an existing patch against independently pinned bug examples
and regression checks. EvidenceCI checks explicit numeric claims against the
resulting packages. Python + pytest, local CLI, offline HTML, no API key.

[Inspect recorded demo evidence](examples/evidence/index.html) ·
[Read the verification record](docs/verification/README.md)

The next iteration adds an experimental Docker adapter for approved fixtures.
See [container setup and acceptance gates](docs/container-executor.md) and
[phase 2 verification](docs/verification/phase2.md). External patches remain disabled.

> MVP boundary: only the bundled, registered synthetic sources and patches may
> execute. The local executor is **not a sandbox**. External repositories are
> deliberately unsupported until a hardened executor is implemented.

## Quickstart

Requirements: Python 3.11+, Git. Tested runtime dependencies are pinned in
`requirements.lock`. Commands below assume an activated virtual environment.

```sh
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip install -e .
python -m patchreplay doctor
python -m patchreplay run good
python -m patchreplay demo --output demo-output
```

Open `demo-output/index.html` in any browser. The ten cases include successful,
ineffective, narrow, regressive, evaluator-tampering, environment-failure,
timeout, unstable, already-fixed, and syntax-error patches. The demo also checks
six explicit claims. Intentional negative cases are expected; `demo` exits 0
only when **every case and claim matches its reviewed expected outcome**.

```sh
python -m patchreplay list
python -m patchreplay examples my-cases
python -m patchreplay run my-cases/good.json --output my-runs
python -m patchreplay verify my-runs/<run-id>
python -m patchreplay replay my-runs/<run-id> --output replay-output
python -m patchreplay check demo-output/claim-suite-supported.json
evidenceci demo-output/claim-wrong-number.json
python -m pytest
```

Use the run directory printed by the CLI in place of `<run-id>`. `run` returns
0 only for `VERIFIED_FOR_DECLARED_CHECKS`, 1 for an evaluated nonverified result,
and 2 for invalid arguments/input or an operational CLI failure. `check` returns
0 only for `SUPPORTED_FOR_SCOPE`; a rejected claim returns 1. `verify` checks
consistency, not test success or producer authenticity.

## What a reviewer gets

- Before/after observations for the exact approved pytest nodes, repeated in
  fresh working directories. Baseline regressions must already pass.
- Source snapshot revision, patch SHA-256, evaluator/suite identities, engine
  source hashes, environment inventory, recorded argv, exits, timing and logs.
- A static HTML report, raw pytest records, JUnit XML, JSON report, input
  snapshots and a SHA-256 manifest. Failed preflights produce reports too.
- Exact-input replay that checks the current engine and environment before
  creating a new run. A replay is a new observation, not a determinism promise.
- EvidenceCI rules for complete-suite success counts and all-regression claims.
  Missing runs cannot disappear from the denominator. Timeouts, infrastructure
  errors and inconclusive cases count as nonverified in suite success claims.

The fixture suite is **synthetic**. Its 1/10 verified count demonstrates decision
boundaries; it is not an estimate of a coding agent's effectiveness. No AI model
was used by the runtime, and no generated reproducer is automatically accepted.

## Inspect the implementation

| Area | Source |
| --- | --- |
| Typed case contract and decision rules | `src/patchreplay/contracts.py` |
| Snapshot verification and patch evaluation | `src/patchreplay/engine.py` |
| Paths, hashes and package integrity | `src/patchreplay/integrity.py` |
| Controlled subprocess and pytest observations | `process.py`, `worker.py` |
| Explicit claim validation | `src/patchreplay/claims.py` |
| Offline reports | `reporting.py`, `templates/report.html` |
| Independently reviewed synthetic evaluator | `src/patchreplay/data/evaluators/clamp-v1/` |
| Fixture authoring and suite versioning | `scripts/build_fixtures.py` |

See [architecture](docs/architecture.md), [evaluation semantics](docs/evaluation-semantics.md),
[evidence contracts](docs/contracts.md), [security and limitations](docs/security.md),
[demo storyboard](docs/demo-storyboard.md), and [prioritized roadmap](docs/roadmap.md).

## Development

There is no result cache. There are no arbitrary setup shell commands and no
implicit dependency installation during evaluation. Fixture changes require
human review of the source, patch, evaluator, catalog and suite identities
together; `scripts/build_fixtures.py` is a maintainer authoring tool, not a way
to approve third-party code automatically.

The published baseline passed its Windows/Linux Python 3.11/3.12
[CI matrix](https://github.com/svkhun/PatchReplay/actions/runs/41603343984).
The experimental container adapter has passed [local live acceptance](docs/verification/container-acceptance.md);
its new GitHub workflow has not run yet. MIT license. Do not submit secrets in fixture files or
logs; the evidence package deliberately preserves them as supplied.
