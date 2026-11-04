# Prioritized roadmap

Phase 3 integrates the [registered host-function workflow](function-workflow.md):
versioned contracts, Docker-only observations, strict host decisions, JSON/HTML
packages, replay and external-trust provenance. The synthetic function scope is
implemented; external-code and real-project gates remain future work.
See [acceptance evidence](verification/function/README.md).

The controlled-fixture container prototype has passed [local and GitHub live acceptance](verification/container-acceptance.md),
including replay and cleanup. Its commit also passed the four-job Windows/Ubuntu
CI matrix. The next P0 gate is independent
observation integrity for external code, not relaxing the existing catalog.

The [host-owned observation experiment](observer-boundary.md) explores this gate
for a limited integer-function interface and reproduces the current in-process
pytest weakness. It does not admit arbitrary external code or replace pytest.

Phase 2 adds [offline signed provenance](provenance.md) for existing packages and
observer output, with externally supplied keys/expectations and a snapshot of
signed files. Public key distribution and review remain operator responsibilities;
the implementation does not establish real-world identity or observation truth.

| Priority | User benefit | Deliverable and acceptance gate |
| --- | --- | --- |
| P0 | Safely review an external patch | Extend the tested fixture executor with independent observation capture and adversarial escape/forgery tests. Keep signing authority and verdict computation outside evaluated code. Reject forged, missing, duplicated or cross-run observations. No catalog bypass before this gate. |
| P0 | Trust who produced shared evidence | Offline key-pinned signatures and expected-subject verification implemented. Remaining deployment work: independently distribute trusted keys/expectations and define organizational rotation/revocation policy. |
| P1 | Evaluate real maintained repositories | Git commit + patch intake, license/provenance records, deterministic dependency environment, two sourced real bug cases. Keep synthetic and real results separate. |
| P1 | Understand baseline/patch failure causes | More detailed collection/setup failure attribution, structured diagnostics and bounded streaming logs; test infrastructure outages separately from patch-induced import errors. |
| P1 | Detect more instability without excess cost | Configurable reviewed repeat policy, seed capture and per-node disagreement display; budget-aware execution without silently reducing declared checks. |
| P2 | Build a claim without manual hash copying | CLI claim drafting from reviewed runs, clearly marked unapproved until the user confirms text-to-rule mapping and expected input identities. |
| P2 | Help maintainers inspect failures | Optional AI log summaries with exact artifact/line references and explicit live/recorded/mock provenance. No effect on verdicts. |
| P2 | Propose stronger bug examples | Issue-to-reproducer assistant; require human approval and a new evaluator/suite identity before execution as criteria. |
| P3 | Save repeated evaluation cost | Cache keyed by every recorded input and execution policy; validate anchor on retrieval, mark reused observations, never silently treat cached results as new repeats. |
| P3 | Review inside GitHub | Check-run attachment, artifact retention and access policy, explicit publication authorization; retain the offline path. |

Before inviting external-code users: complete executor and provenance threat-model
review, add reviewed real-project provenance, and test the reporting workflow
with at least two maintainers. CI now covers both supported OS families, installed
wheel smoke checks and container replay on a separate Ubuntu runner; it does not
establish a safe arbitrary-code boundary or maintainer usability.
