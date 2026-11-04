# Prioritized roadmap

The controlled-fixture container prototype has passed [local live acceptance](verification/container-acceptance.md),
including replay and cleanup. The earlier baseline CI passed on Windows/Ubuntu;
that result does not cover the new adapter. The next P0 gate is independent
observation integrity for external code, not relaxing the existing catalog.

| Priority | User benefit | Deliverable and acceptance gate |
| --- | --- | --- |
| P0 | Safely review an external patch | Extend the tested fixture executor with independent observation capture and adversarial escape/forgery tests. Keep signing authority and verdict computation outside evaluated code. Reject forged, missing, duplicated or cross-run observations. No catalog bypass before this gate. |
| P0 | Trust who produced shared evidence | Signed provenance/attestations, externally stored anchors, release-specific engine identity, verified package import. |
| P1 | Evaluate real maintained repositories | Git commit + patch intake, license/provenance records, deterministic dependency environment, two sourced real bug cases. Keep synthetic and real results separate. |
| P1 | Understand baseline/patch failure causes | More detailed collection/setup failure attribution, structured diagnostics and bounded streaming logs; test infrastructure outages separately from patch-induced import errors. |
| P1 | Detect more instability without excess cost | Configurable reviewed repeat policy, seed capture and per-node disagreement display; budget-aware execution without silently reducing declared checks. |
| P2 | Build a claim without manual hash copying | CLI claim drafting from reviewed runs, clearly marked unapproved until the user confirms text-to-rule mapping and expected input identities. |
| P2 | Help maintainers inspect failures | Optional AI log summaries with exact artifact/line references and explicit live/recorded/mock provenance. No effect on verdicts. |
| P2 | Propose stronger bug examples | Issue-to-reproducer assistant; require human approval and a new evaluator/suite identity before execution as criteria. |
| P3 | Save repeated evaluation cost | Cache keyed by every recorded input and execution policy; validate anchor on retrieval, mark reused observations, never silently treat cached results as new repeats. |
| P3 | Review inside GitHub | Check-run attachment, artifact retention and access policy, explicit publication authorization; retain the offline path. |

Before inviting external users: complete executor and provenance threat-model
review, run the checked-in CI on both supported OS families, validate clean
installation and replay on a second machine, add real-project provenance, and
test the reporting workflow with at least two maintainers. None of those future
validation outcomes is claimed by this MVP.
