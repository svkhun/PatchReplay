# Phase 1: host-owned observation experiment

Date: 2026-11-04 (Asia/Bangkok). This milestone delivers a threat model, a fixed
demonstration of the existing observation weakness, and a limited host-oracle
prototype. The broader arbitrary-code admission gate remains open.

## Executed verification

- Full local suite with Docker enabled: **163 passed, 1 skipped in 177.07 seconds**
  ([JUnit](tests.xml)). Only the Windows symlink-privilege test was skipped.
- The suite includes 27 new host protocol/transport/lifecycle tests, plus one live
  experiment test containing 15 oracle observations and the legacy demonstration.
  These counts are subsets of the full result, not additional passes.
- Legacy forged records were interpreted as `PASS` for a single check without
  executing the declared test bodies. This is the expected negative demonstration.
- Host oracle: buggy lower-bound cases produced two `MISMATCH` results; the other
  six normal requests produced `MATCH`. Six adverse cases produced
  `INVALID_RESPONSE`; the deliberately stalled fixture produced `TIMEOUT`.
- The seven adverse fixtures cover record forgery, verdict injection, duplicate
  output, wrong request ID, disconnect, timeout and output overflow. Unit tests
  also cover malformed values, duplicate fields, nonzero exit, create timeout,
  cleanup failure and absence of the oracle from the input mount.
- Every recorded container was removed. A final `docker ps -a` filtered to
  `patchreplay-` returned no containers.
- Archived experiment hashes match the current experiment source. Workflow
  routing and local documentation links were checked.

See [recorded results](../../../examples/observer-evidence/results.json).
Docker server observed: 29.9.2. Immutable local image:
`sha256:6234ccbd3a3481bd5c878f06c7714e0a4b98d46e07c4341d5bf4ca76a06fdf6e`.

The first live attempt timed out at Docker create while using an AppData temp
mount. After moving scratch mounts into the workspace, the focused run passed
in 32.98 seconds and the full run passed. The precise cause of the first timeout
was not independently traced. No factory reset, image/volume deletion or Docker
upgrade was performed.

## Interpretation and remaining work

The host now checks a numeric answer against its own expected value. It does not
accept guest-supplied pass/fail records as authoritative. This is useful for
reviewed black-box function cases, but does not authenticate internal execution,
establish producer identity, or isolate arbitrary pytest evaluators. A guest that
returns the expected value has matched only that request, whether computed or
hardcoded. Request IDs are visible correlation values, not secrets.

The installed PatchReplay engine and fixture catalog were unchanged. The new
repository-only experiment does not invalidate existing engine identities or
enable external repositories. Next work is the host-observation provenance
contract and selection of reviewed real cases that fit this limited interface.

## Remote acceptance

The container workflow, including the observer live test, passed on GitHub's
Ubuntu runner for `5b081a859e406dc9bddedb655a8eed57ef2dee4c`:
[run 41764292012](https://github.com/svkhun/PatchReplay/actions/runs/41764292012).
It built its own immutable image and retained JUnit, image metadata and the
experiment results as workflow artifacts. Its image identity may differ from
the local image above. Passing these declared tests is not sandbox certification.

The same commit passed all four Windows/Ubuntu Python 3.11/3.12 jobs in
[run 41764291998](https://github.com/svkhun/PatchReplay/actions/runs/41764291998),
including the regression suite, synthetic demo, claim checks and installed-wheel
smoke test. The live Docker tests run in the separate container workflow above;
their skips in the ordinary matrix are not counted as live acceptance.
