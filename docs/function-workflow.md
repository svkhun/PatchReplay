# Integrated host-function workflow (Phase 3)

This page records the Phase 3 synthetic scope in version 0.1. Version 0.2 adds
[registered upstream extracts](real-cases.md) using case schema 2 and the same numeric
observation protocol, plus [function claim schema 2](function-claims.md). Existing
case schema 1 and historical packages retain their meanings and bytes.

Phase 3 exposes the reviewed integer-function observer through the installed CLI.
It retains the source/patch admission gate and preserves the local/pytest commands.
All bundled cases are synthetic. There is no arbitrary repository, command, source
path or patch option. `function-run` requires Docker and never falls back to local
execution. A function report has `schema_version: 2` and
`evaluation_kind: host-function-v1`; legacy pytest reports remain schema 1.

## Run, inspect and replay

Use the base evaluator environment and build/resolve an immutable local image as
described in [container setup](container-executor.md). Replace the image placeholder
with the actual `sha256:` image ID; mutable tags are rejected.

```sh
python -m patchreplay function-list
python -m patchreplay function-run good --image sha256:<64-hex-image-id> --output function-runs
python -m patchreplay function-run regression --image sha256:<64-hex-image-id> --output function-runs
python -m patchreplay verify function-runs/<printed-run-id>
python -m patchreplay replay function-runs/<printed-run-id> --output function-replays
```

Open the printed `report.html` offline. It shows the declared scope, repeats,
before/after arguments, expected/observed integers, host decisions, cleanup state,
bounded raw responses, identities and links to input snapshots. `report.json`
also contains request IDs, exact Docker create arguments, exit/timeout metadata,
duration, errors and raw bytes encoded losslessly as base64. `patch-steps.json` and
logs record Git preparation when reached. Preflight failures produce sealed reports.
Invalid admission/arguments exit 2 before execution; evaluated failures exit 1;
verified declared checks exit 0. `verify` returns 0 for a consistent failed report
too: consistency does not mean test success.

## Contract and admission

`schemas/function-case.schema.json` defines registered case version 1. It pins source
bytes, exact text patch, approved patched bytes, callable interface, host oracle and
decision-rule identity, suite, policy, repeats and per-request timeout. The interface
is deliberately limited to `candidate.clamp(int, int, int) -> int`; arguments and
answers are bounded to `[-(2**53-1), 2**53-1]`. Exceptions are execution errors.

The resolved case binding in `report.identities` adds the immutable image, host
environment, Docker server/kernel/architecture/cgroup/security metadata and engine
source inventory. Image selection is an operator trust decision: identity pinning
does not review or certify its contents. The image must already exist locally.

The code pins the reviewed suite hash. `load_registered` checks the entire suite,
exact case, oracle and source/patch/patched hashes before Docker is invoked. Git
applies only the reviewed `candidate.py` diff in a disposable repository; its output
must equal the approved patched hash. `scripts/build_function_fixtures.py` is a
maintainer authoring aid, not an automatic admission mechanism. Changes require
review of the resulting data and an explicit suite identity update in the engine.

The thirteen cases cover correct, incorrect, incomplete, regressive, already-fixed,
broken-baseline, forged-record, forged-status, duplicate, wrong-request, disconnected,
overflowing and timed-out responses. Each uses two repeats, four probes and both
phases: sixteen fresh containers per completed case. Cleanup failure stops execution
explicitly; missing observations never silently reduce declared scope.

Only `candidate.py` and the untrusted `guest.py` adapter enter the read-only mount.
Requests contain protocol version, fresh correlation ID and numeric arguments.
Expected answers, baseline values, decision rules, signing keys/passwords and host
evidence directories never enter the container. Existing Docker limits apply:
non-root, no network, read-only root/input, dropped capabilities, no-new-privileges,
memory/CPU/PID/file limits and bounded scratch. Attach retains at most 4,097 bytes
to detect overflow past the 4,096-byte protocol limit. Removal and absence are checked
separately from termination of the attach client.

## Host decision semantics

Each bug probe declares the correct answer and its exact wrong baseline answer.
Every baseline bug observation across repeats must equal that declared wrong value;
a different wrong answer is not reproduction. Baseline regressions and all patched
observations must match their correct answers. Numeric disagreement across repeats
is inconclusive even when every response is syntactically valid.

Precedence: explicit workflow failure; integrity failure; infrastructure/cleanup
failure; timeout; execution error; invalid response; missing/duplicate observations;
repeat disagreement; failing baseline regressions; bug not reproduced; regression
after patch; incomplete correction; success. Regression takes precedence over an
incomplete fix when both occur, with both problems visible in the per-probe table.
Distinct statuses are specified in `schemas/function-report.schema.json`.

Malformed JSON, guest `PASS` fields, duplicate keys/messages, wrong request IDs,
empty output, booleans/floats/non-finite/out-of-range answers and overflow are rejected.
Neither exit 0 nor an absent response establishes bug reproduction.

## Evidence and replay

The manifest remains version 1: its file inventory can seal either report format
without changing their meanings. `verify` explicitly dispatches by report kind.
The function validator checks snapshots, engine files, case/suite/policy, environment
and image bindings, request uniqueness/arguments, transport metadata, numeric host
decisions, aggregate verdict and deterministic HTML/JSON consistency. It executes
neither stored engine nor candidate code. A fabricated complete producer record can
still be internally consistent: the host is a trust assumption.

Replay verifies the original package and requires the admitted case, evaluator,
engine, image, policy and applicable host/Docker environment to match. It creates
fresh run/request IDs and preserves the original package. Changing installed optional
packages, Python, Git or Docker/kernel metadata can reject exact-input replay. Use
the recorded evaluator environment, not the separate provenance venv. Hardware,
host load, scheduling, randomness and physical daemon identity are not controlled.

Historical packages remain untouched. CLI integration changes the current engine
hash, so older exact-engine replay requires its recorded software; their offline
verification and provenance remain supported. EvidenceCI claim schema 1 stays
pytest-only and deliberately rejects function reports. A future explicit claim
adapter can add that scope without reinterpreting old claims; it is not required
to inspect, verify, replay or sign these packages.

## Optional host-only provenance

Use the separate optional provenance environment. Do not install signing dependencies
into the evaluator environment merely to sign a run. Follow the independent key and
expectation trust procedure in [provenance](provenance.md).

```sh
python -m patchreplay_provenance prepare --subject function-runs/<run-id> --kind host-function-v1 --output trusted/function.expected.json
python -m patchreplay_provenance sign --subject function-runs/<run-id> --expectation trusted/function.expected.json --private-key private/producer.pem --password-env PATCHREPLAY_SIGNING_PASSWORD --output signed-function
python -m patchreplay_provenance verify --bundle signed-function --trusted-key trusted/producer-public.pem --expectation trusted/function.expected.json
```

Review/store expectations independently. Keys, passwords and signing authority stay
on the host outside subject/bundle directories. Verification requires both explicit
external trust inputs and returns `AUTHENTICATED_FOR_EXPECTED_SUBJECT`. Failed test
packages can authenticate too. A signature does not establish truthful observations,
correct code, real-world signer identity, freshness or a trusted timestamp. Signing
a false report does not make it true.

## Boundary and next milestone

A match establishes only the declared numeric observation, not which implementation
ran: a guest may compute or hardcode an answer. Request IDs correlate; they do not
authenticate. The host, oracle, reviewed image, Docker daemon and kernel are trusted.
This does not establish generic pytest isolation, arbitrary-code safety, container
escape resistance or production readiness.

The next milestone is separately reviewed real-project cases with source/license
provenance and reproducible dependencies that fit the limited interface. Phase 3
contains no real-project cases and does not relax admission for future work.
See [acceptance evidence](verification/function/README.md).
