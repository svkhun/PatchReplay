# Evaluation semantics v1

The evaluator is a human-authored synthetic specification, stored outside the
patch target and hashed before execution. For the clamp fixture it declares two
bug nodes and three regression nodes. All cases run two attempts per phase.

| Phase | Required observation for verification |
| --- | --- |
| `before_bug` | Every declared node fails at the call phase with `AssertionError`; setup and teardown pass |
| `before_regression` | Every declared node passes |
| `after_bug` | Every declared node passes |
| `after_regression` | Every declared node passes |

No skipped or xfailed node counts as a pass. Missing/duplicate/unexpected nodes,
collection failures and empty suites are never proof of bug reproduction. Both
the process exit status and complete per-node records must agree. Logs provide
context; string matching on stdout does not determine the verdict.

## Decision precedence

1. Detected changes to protected inputs → `EVALUATION_INTEGRITY_FAILED`.
2. Uninterpretable process/recorder failure or missing check attempts → `INFRA_ERROR`.
3. Any timed-out check → `INCONCLUSIVE`.
4. Different record signatures across repeated attempts → `INCONCLUSIVE`.
5. All baseline bug examples already pass → `BUG_NOT_REPRODUCED`.
6. Other baseline bug failures or a failing baseline regression → `INCONCLUSIVE`.
7. After-patch bug checks do not all pass → `FIX_FAILED`.
8. After-patch regression checks do not all pass → `REGRESSION_DETECTED`.
9. Otherwise → `VERIFIED_FOR_DECLARED_CHECKS`.

Preflight integrity rejection and environment preparation failure stop before
tests. The package records the relevant reason. A patch that Git cannot apply
is `FIX_FAILED`; inability to start Git or a Git operation timeout is `INFRA_ERROR`.

A syntax/import/collection failure only after applying the patch is attributed
to the patch (`FIX_FAILED` for bug checks, `REGRESSION_DETECTED` for regression
checks), because the equivalent baseline checks completed. Pytest internal
errors or a missing recorder output remain infrastructure failures. If a check
times out, this MVP does not infer whether code, machine load, or infrastructure
caused the timeout. It reports uncertainty.

When more than one condition is true, the first applicable condition wins. The
report still preserves all observed checks. Repetition disagreement compares
exit codes, node outcomes, lifecycle phases and exception types, not timing or
log paths. Two matching attempts are limited observations, not a flake-free proof.

## Synthetic case inventory

| Case | Intended behavior | Expected decision |
| --- | --- | --- |
| `good` | Correctly enforces both bounds | Verified for declared checks |
| `ineffective` | Adds a comment; leaves the bug | Fix failed |
| `narrow` | Handles only the first bug example | Fix failed |
| `regression` | Repairs lower bound but removes upper-bound clipping | Regression detected |
| `protected` | Edits a protected repository test path | Evaluation integrity failed |
| `environment-error` | Requests deliberately unavailable pytest 0.0.0 | Infrastructure error before tests |
| `timeout` | A reviewed patch deliberately sleeps beyond its check budget | Inconclusive |
| `unstable` | Deliberately alternates behavior by attempt number | Inconclusive |
| `already-fixed` | Baseline already contains the correction | Bug not reproduced |
| `syntax-error` | Introduces invalid Python syntax | Fix failed |

The unstable fixture is a deterministic simulation of inconsistent observations.
It is not a measured naturally flaky test. The timeout fixture really sleeps;
it is terminated by the process executor. The environment fixture runs a real
version preflight, with no attempted download or installation.

## EvidenceCI decisions

The prose `text` field is a reviewer label. Its correspondence to the structured
`kind`, `scope` and `assertion` must be reviewed by a person. EvidenceCI does not
read arbitrary prose and discover its meaning.

| Decision | Meaning |
| --- | --- |
| `SUPPORTED_FOR_SCOPE` | Required artifacts are present and consistent, identities match, and the explicit arithmetic/predicate holds |
| `STALE` | Intact evidence differs from one or more explicitly expected identities |
| `CONTRADICTED` | Complete, current observations disagree with the stated count or all-regression predicate |
| `INSUFFICIENT_EVIDENCE` | Malformed claim, missing/tampered artifacts, duplicate runs, incomplete scope or uninterpretable required checks |

Missing/tampered evidence takes precedence over stale identities. Staleness
takes precedence over arithmetic. EvidenceCI cannot independently know a new
desired source revision: the caller must update the expected identities in the
claim manifest. A stale claim is not discovered by wall-clock age alone.

`success_count` requires the entire roster of the versioned suite. Its numerator
counts only `VERIFIED_FOR_DECLARED_CHECKS`; its denominator includes **all**
declared cases, including timeouts, errors and inconclusive cases. Missing
packages produce insufficient evidence rather than a reduced denominator.

`regression_all` permits an explicit subset of suite case IDs and requires every
after-patch regression check in every repeat to pass. A valid observed failing
regression contradicts the claim. Missing, timed-out or uninterpretable checks
provide insufficient evidence. This claim says nothing about bug reproduction;
an ineffective patch may still pass all regression checks.
