# Container executor acceptance

Live runs: 2026-11-03. Final review: 2026-11-04 (Asia/Bangkok).

The experimental `docker-fixtures-v1` executor passed its declared live checks
on this Windows host using Docker Desktop's Linux engine. The source/patch
catalog remains mandatory. This result does not admit external code or certify
the sandbox against escapes or forged observations.

## Recorded results

| Check | Result | Evidence |
| --- | --- | --- |
| Full suite with live Docker enabled | 134 passed, 1 skipped, 151.22 s | [JUnit](container-full-tests.xml) |
| Earlier focused live run | 4 passed, 62.16 s | [JUnit](container-live-tests.xml) |
| Final adapter/admission checks (November 4) | 25 passed, including rejection of a rehashed unregistered patch before Docker access | [JUnit](container-admission-tests.xml) |
| Correct patch | VERIFIED_FOR_DECLARED_CHECKS | [Package](../../examples/container-evidence/good-88d4b8780666/report.html) |
| Regressive patch | REGRESSION_DETECTED | [Package](../../examples/container-evidence/regression-657db9dc5f0e/report.html) |
| Deliberately slow patch | INCONCLUSIVE | [Package](../../examples/container-evidence/timeout-4f515ea83d60/report.html) |
| Container good-case replay | Same input identities and decision, different run ID | Full-suite `test_live_fixture_evaluation[good-VERIFIED_FOR_DECLARED_CHECKS]` |
| Packaged evidence | Manifests and decision consistency verified; scoped regression claim supported | [Claim result](../../examples/container-evidence/results.json) |
| Schemas | 4 schemas, 20 artifacts validated | [Result](container-schema-results.json) |
| Git byte preservation | 721 evidence files unchanged with `core.autocrlf=true` | [Result](checkout-bytes.json) |

The skipped test requires Windows symlink-creation privileges. None of the four
live tests were skipped. The focused and full runs overlap and are not additive.

The live probe observed UID 65534, no forwarded host-secret variable, no Docker
socket, only the loopback interface, denied root/input writes, cgroup memory/PID/
CPU limits, zero effective capabilities, no-new-privileges and seccomp filtering.
Evaluation tests verified package consistency and removal of recorded containers.
The final inventory on November 4 found no `patchreplay-` containers; the original
`mfg-data-pipeline_pgdata` volume was still listed and was never mounted by these tests.

## Runtime and recovery

[Runtime metadata](container-runtime.json) records Docker 29.9.2,
WSL2 Linux `6.6.87.2-microsoft-standard-WSL2`, cgroup v2 and linux/amd64.

- Base: `python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30`
- Built image: `sha256:6234ccbd3a3481bd5c878f06c7714e0a4b98d46e07c4341d5bf4ca76a06fdf6e`

Docker startup had previously failed on `sailor-ingest.sock`. Launch through
Explorer restored availability; see [recovery](docker-recovery.md). The first
live attempt subsequently hit the 15-second `docker info` timeout. A later probe
was responsive and both recorded passing runs completed. The engine version
observed after recovery was 29.7.2 and during acceptance was 29.9.2; the cause of
that version change was not established, and no upgrade was performed by this task.

The image is local, not published. A rebuild may have a new image ID. Exact-input
replay requires the recorded engine/environment and local image. Docker/kernel
versions are recorded here but are not yet in the replay fingerprint.

## Scope of the next gate

The fixture executor is ready for further controlled-fixture work. External
repository execution remains gated on independent observation capture, adversarial
forgery tests and authenticated producer provenance. A signature alone would not
make an in-container forged result trustworthy. See the [roadmap](../roadmap.md).

## GitHub acceptance

The container workflow subsequently passed on Ubuntu for commit
`6853e7d0ecd12510cbd0c7e6a0abd1ad5d2cfe28`:
[run 41762035366](https://github.com/svkhun/PatchReplay/actions/runs/41762035366).
It built its own immutable evaluator image and passed the live policy/evaluation
tests, including good-case replay. The run retains its own image metadata, JUnit
and evidence artifacts; those build identities need not equal this host's image.

Relevant `main` pushes, pull requests and manual dispatch trigger that workflow.
The same commit also passed all four Windows/Ubuntu Python 3.11/3.12 jobs in
[run 41762035246](https://github.com/svkhun/PatchReplay/actions/runs/41762035246),
including tests, the synthetic demo, claim validation and installed-wheel smoke
checks. This is additional runtime validation, not external-code admission.
The earlier baseline's CI record remains in [phase 2](phase2.md).
