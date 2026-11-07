# Version 0.2 acceptance: Phases 4–6

Date: 2026-11-07 (Asia/Bangkok). Scope: two registered upstream function extracts,
synthetic controls, function EvidenceCI claims, replay/provenance and a prepared
offline release with two explicitly simulated reviewer roles.

## Scope delivered

Phase 4 pins the before/fix commits for boltons default clamp bounds and TheAlgorithms
zero-input LCM. Raw source, license notices, adapters and adaptation records are
preserved and hashed. Both cases have synthetic noop/regression controls. These
are declared function observations through wrappers, not full upstream builds or
complete upstream test-suite results. See [case records](../../real-cases.md).

Phase 5 adds function claim schema 2. The complete six-case suite produces the
reviewed 2/6 success count, while the two actual fixes support the declared
regression-preservation claim. Unreviewed drafts are rejected; missing/error/timeout
observations cannot count as passing checks. Legacy pytest claim meanings remain
unchanged. See [claim rules](../../function-claims.md).

Phase 6 prepares the installed-wheel demo, reviewer/trust guides, release ZIP tooling
and two scripted role rehearsals in separate wheel environments. The user explicitly
authorized simulation instead of actual human trials. Both simulations passed;
`SIMULATED_AUTOMATED` and zero human participants are recorded. No human usability,
comprehension or task-time result is claimed. See [simulated trials](simulated-trials.json).

## Local checks

| Check | Result | Evidence |
| --- | --- | --- |
| Full regression suite, isolated provenance venv | 284 passed, 21 skipped, 252.33 s | [JUnit](full-tests.xml) |
| Final real Docker suite | 19 passed, no skips, 763.67 s | [JUnit](live-tests.xml) |
| New immutable archive guards, added after full suite | 3 passed, 2.98 s | [JUnit](archive-tests.xml) |
| Installed wheel, actual Docker | Synthetic good run/replay and full six-case upstream demo, claims and both fix replays passed | [Wheel record](wheel.json) |
| Runtime source equality | Installed wheel's engine source inventory equals the source checkout tested | [Inventory](wheel-runtime.json) |
| Published schemas | 6 case contracts, 8 archived reports and 2 claims validated using separate QA dependencies | [Record](schema-checks.json) |
| Host-only signing of real evidence | Authenticated expected boltons-fix subject; temporary private key removed | [Signed example](../../../examples/v02-evidence/provenance/result.json) |
| Simulated maintainer and recipient roles | 2 passed; 0 human participants | [Record](simulated-trials.json) |

Counts overlap and must not be added. Nineteen full-suite skips are opt-in live
Docker tests, run separately. Two local skips require Windows symlink privileges.
The archive guards only read evidence and were added after the full suite. CI must
cover the final complete test set on the implementation commit.

The initial development run caught Python-3.14-only syntax in an unused upstream
dependency CLI footer. Original upstream source is now stored as `.py.txt` data;
only the supported dependency function body is included in the executable candidate.
The final byte-compilation regression passed. A preliminary Docker run detected
input/engine drift while development edits were still in progress; it is not final
acceptance. No historical evidence was regenerated or resealed.

[Archived installed-wheel demo](../../../examples/v02-evidence/README.md) preserves
eight packages, both supported claims and the signed real subject unchanged.
Dependency lock files were reused; signing dependencies remain outside evaluator
images and the base evaluator venv. Docker's existing immutable evaluator image was
used locally; no reset, prune or WSL reset was performed.

## Remaining boundaries

Interactive browser QA could not be completed. Computer Use stopped because it
could not determine the current browser URL on Windows confidently enough to
enforce policy. Browser automation was stopped; no alternate route bypassed that
guard. HTML content, escaping, schemas and deterministic report consistency were
tested offline. Visual browser acceptance remains unmeasured.

The offline release is a prepared review artifact, not a package-registry publication
or production approval. Matching responses do not prove internal execution;
signatures do not make false observations truthful. Host, oracle, reviewed image,
Docker daemon and kernel remain trusted. Arbitrary source/command/repository intake
and generic pytest observer integrity remain separate future work.

## Final live and remote acceptance

The frozen-source Docker run passed all 19 tests, including both upstream fixes,
four synthetic controls, supported claims and fresh-ID replays. It reused immutable
image `sha256:6234ccbd3a3481bd5c878f06c7714e0a4b98d46e07c4341d5bf4ca76a06fdf6e`.
Exact implementation SHA and GitHub Actions links are added when remote workflows
complete. Local passes are not remote CI results.
