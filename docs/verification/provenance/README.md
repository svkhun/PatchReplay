# Phase 2: offline signed provenance

Date: 2026-11-04 (Asia/Bangkok). Scope: host-only signing and verification of
existing evidence snapshots against an external key and expected subject.

## Local verification

| Check | Observed result | Evidence |
| --- | --- | --- |
| Full regression suite in isolated provenance venv | 193 passed, 7 skipped, 145.08 s | [JUnit](full-tests.xml) |
| Final provenance tests after streaming-directory guard | 36 passed, 1 skipped, 20.71 s | [JUnit](provenance-tests.xml) |
| Offline signing demonstration | 1 authenticated expected subject, 7 correctly rejected variants | [Results](../../../examples/provenance-evidence/results.json) |
| Final wheel build, isolated installed-wheel CLI | Authenticated the checked-in bundle using external demo trust inputs | [Record](wheel.json) |
| Byte preservation through Git clean filters | 736 identity-bearing files unchanged with `core.autocrlf=true` | [Record](checkout-bytes.json) |
| Dependency compatibility | `pip check` reported no broken requirements | Observed command result |

The full local run preceded the final directory-count guard and its extra test;
the focused final run covers that change. Counts overlap and must not be added.
Five full-suite skips are opt-in Docker tests, intentionally not enabled for this
offline provenance change; two require Windows symlink privileges. The final
focused run skips only its symlink test. Live Docker passes from earlier milestones
are separate evidence, not newly executed acceptance for this milestone.

Tests cover changed/missing/added artifacts, invalid signatures, untrusted keys,
forged key IDs, signed but unexpected runs, rehashed and re-signed artifacts with
stale external expectations, protocol-domain separation, key/expectation files
inside a bundle, wrong passwords, unencrypted private keys, input drift,
duplicate JSON/request IDs, oversized files/counts, offline operation and CLI exits.
They also authenticate genuine recorded `REGRESSION_DETECTED` and `INCONCLUSIVE`
packages to demonstrate that authentication is not a passing test result.

The base evaluator venv was not changed: cryptography remains absent there and
the optional CLI returns documented `UNAVAILABLE`/exit 2. The original evaluator
engine hash still equals the recorded container evidence's engine identity.
No candidate code or container was executed by the new provenance operations.

The isolated host venv used cryptography 50.0.2, cffi 2.1.1 and pycparser 3.12,
alongside the existing pinned runtime. The crypto dependency is optional and not
part of the evaluator Docker image. The final wheel was installed into a separate
target and imported with `-I`; its module origin was asserted to be that target.

The demo key was random and encrypted. Its temporary private file was removed
when the demo finished, its password was not printed, and only the public key
appears in checked-in evidence. This demo key is not a maintained release-signing
identity. Neither it nor its adjacent expectation constitutes independent trust.

## Boundaries

See [the contract and operator workflow](../../provenance.md). The verifier proves
key-pinned signature validity and exact expected-subject/file binding. It does not
establish a real-world signer, trusted timestamp, revocation/freshness, code
correctness, uncompromised host, or truthful pytest observer. Existing arbitrary
repository admission remains disabled. Private keys/trust anchors must stay
outside the subject and bundle and under the operator's control.

## Remote acceptance

Implementation commit `a245cc10d3f84ef24e4e0b05186fa912fe9c8bae` passed all four
Windows/Ubuntu Python 3.11/3.12 jobs in
[GitHub run 41794985873](https://github.com/svkhun/PatchReplay/actions/runs/41794985873).
Each job ran the final test suite, original synthetic demo/claim checks, offline
provenance demo, wheel build and verification using the installed wheel. Workflow
artifacts retain the JUnit, wheel and independently generated demo evidence.

This run covers the final streaming-directory guard and extra count-limit test.
No new live container workflow was required for this host-only change; the
evaluator/observer/container source and image inputs were unchanged. This remains
scoped provenance acceptance, not sandbox or cryptographic certification.
