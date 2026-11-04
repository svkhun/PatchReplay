# Phase 3: integrated host-function acceptance

Date: 2026-11-04 (Asia/Bangkok). Scope: installed CLI integration for reviewed
synthetic integer-function cases, host-owned before/after decisions, replayable
evidence and optional host-only provenance. No Phase 4 real-project intake was added.

## Executed local checks

| Check | Observed result | Evidence |
| --- | --- | --- |
| Full regression suite in separate provenance venv | 258 passed, 20 skipped, 269.07 s | [JUnit](full-tests.xml) |
| Final live Docker suite: legacy controls, observer experiment, integrated function cases/replay | 18 passed, no skips, 506.66 s | [JUnit](live-tests.xml) |
| Function cases in that live suite | 13 cases plus a new-ID replay; all expected statuses matched; 224 host observations | [Run identities and outcomes](live-summary.json) |
| Installed wheel in a new isolated evaluator venv | Listed all 13 cases; good run, offline verify, replay and second verify passed using real Docker | [Wheel record](wheel.json) |
| Archived package and signed-example guards, added after the full suite | 2 passed, 64 deselected, 1.56 s; subprocess creation forbidden | [JUnit](archive-tests.xml) |
| Optional signing of real successful evidence | Authenticated expected subject with ephemeral key; private key removed | [Recorded bundle result](../../../examples/function-evidence/provenance/result.json) |
| Optional signing of real regression evidence | Authenticated expected subject while retaining `REGRESSION_DETECTED` | [Result](regression-provenance.json) |
| Dependency compatibility | Both original venvs and isolated wheel venv passed `pip check`; base evaluator still has no cryptography | Observed CLI results |
| Final container cleanup | `docker ps -a --filter name=patchreplay-` returned no containers | Observed CLI result |
| Git checkout byte preservation | All 228 new files checked preserved bytes with `core.autocrlf=true` | [Record](checkout-bytes.json) |

Counts overlap and must not be added. Eighteen full-suite skips are opt-in live
Docker tests that were then executed in the separate live suite; the remaining two
require Windows symlink privileges. The final archive guard tests only read sealed
packages; they did not modify the implementation tested by the full/live suites.

The final source includes a resolved execution binding written before observations,
revalidation at replay's execution boundary and post-run environment checks. An
earlier 13-case live pass and 247-pass regression run preceded those checks and are
not the final acceptance numbers above.

The full suite covers admission/source/oracle drift; correct, ineffective, incomplete
and regressive patches; unreproduced bugs and broken baseline regressions; forged
verdicts/records, duplicate/missing/wrong-ID/oversized responses; timeout, execution,
infrastructure and cleanup failure; repeat disagreement; replay input/environment/
engine drift and new identities; resealed report/package inconsistencies; explicit
schema separation; optional provenance and external expected-subject rejection.

Docker server: `29.9.2`. Local immutable image:
`sha256:6234ccbd3a3481bd5c878f06c7714e0a4b98d46e07c4341d5bf4ca76a06fdf6e`.
Docker was started through the documented Explorer recovery route. Restricted shell
access could not reach its named pipe, so authorized live checks used elevated tool
access. One approval-service usage-limit interruption was retried successfully;
that unexecuted request is not counted as a test. No reset, prune or WSL reset occurred.

The wheel was built without new runtime dependencies and installed into a fresh venv.
Its module origin was asserted outside the checkout and recorded as `site-packages`.
The wheel-smoke helper's relative-output normalization was subsequently corrected;
its no-Docker path smoke passed too. No runtime engine change was made after the
final full/live build. Both original environments were preserved.

## Inspectable artifacts and boundaries

[Recorded examples](../../../examples/function-evidence/README.md) preserve the exact
good, regression and timeout packages from the final live run. All remaining live
run identities and outcomes are in the summary; CI retains full live outputs as
workflow artifacts. No historical Phase 1/2 evidence was regenerated or resealed.

HTML content, escaping and deterministic JSON consistency are tested. Interactive
browser visual QA was not completed: the preview tool timed out.

Signatures use an ephemeral demonstration key. The public key and expectation are
examples of explicit verifier inputs, not independently established maintainer trust.
Failed packages can authenticate. Neither signatures nor matching numeric answers
prove internal implementation, truthful host observations or general correctness.
The host, reviewed image, Docker daemon and kernel remain trust assumptions.

Arbitrary-code safety, generic pytest isolation, container escape resistance and
production readiness remain unestablished. EvidenceCI claim version 1 remains
pytest-only. The next milestone is separately reviewed real-project source/license
provenance and dependency environments fitting this limited function interface.

## Remote acceptance

Implementation commit `d28052c390c010d5787e8b545cde57551ec513b2` passed both workflows:

- [Evaluate and verify, run 41801157643](https://github.com/svkhun/PatchReplay/actions/runs/41801157643):
  all four Windows/Ubuntu Python 3.11/3.12 jobs passed, including the final archive
  guards, legacy synthetic demo/claims, provenance demo and installed-wheel checks.
- [Container acceptance, run 41801157608](https://github.com/svkhun/PatchReplay/actions/runs/41801157608):
  18 live tests passed in 122.29 seconds, followed by an installed-wheel good run,
  verification, new-ID replay and second verification using real Docker.

| Matrix job | Test result |
| --- | --- |
| Ubuntu, Python 3.11 | 261 passed, 19 skipped, 25.75 s |
| Ubuntu, Python 3.12 | 261 passed, 19 skipped, 30.09 s |
| Windows, Python 3.11 | 262 passed, 18 skipped, 55.19 s |
| Windows, Python 3.12 | 262 passed, 18 skipped, 78.18 s |

All ordinary-matrix jobs skip the 18 opt-in Docker tests executed in the separate
container workflow. Ubuntu additionally skips the Windows Job Object lifecycle
test. These skipped checks are not counted as live passes. Windows CI could execute
both symlink guards that lacked privileges locally. Counts across jobs overlap.

[Remote record](remote-acceptance.json) retains exact run SHA/URLs, job IDs and
relevant observed log lines. Workflow artifacts retain generated evidence, JUnit,
wheel output and immutable image metadata. The Ubuntu image was independently built;
its identity need not match the local Windows-hosted Docker image. This remains
scoped synthetic acceptance, not sandbox or cryptographic certification.
