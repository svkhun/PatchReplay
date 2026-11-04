# Phase 2: baseline confirmation and experimental executor

Update: Docker startup was subsequently recovered by launching through Windows
Explorer; see [the recovery record](docker-recovery.md). Subsequent
[live container acceptance](container-acceptance.md) passed the declared controls
and fixture decisions. The original blocked observations below are retained as history.

Date: 2026-11-03. Baseline commit: `4a5c1421f17b06d68416c69bb92c8b547f92d453`.

## Baseline gate: passed within the recorded scope

GitHub [run 41603343984](https://github.com/svkhun/PatchReplay/actions/runs/41603343984)
completed successfully. All four jobs passed: Windows and Ubuntu, each using
Python 3.11 and 3.12. These results apply to the baseline commit, not the new
container adapter.

A clean local clone of that committed baseline was created without hardlinks.
Its checked-in suite claim verified as `SUPPORTED_FOR_SCOPE` (1/10). The clone
was built and installed into a separate target directory, then its installed
CLI evaluated `good` as `VERIFIED_FOR_DECLARED_CHECKS`. Runtime dependencies
came from the already pinned local venv; this was not a new machine installation.

## Initial container gate: implemented, live acceptance blocked (historical)

The new adapter has immutable-image selection, local Linux-daemon preflight,
resource and mount policy, pre-start inspection, fixed artifact destinations,
timeout cleanup, and executor identity in the evidence environment. Local
execution goes through the same adapter interface. See the
[container design](../container-executor.md).

Docker Desktop on this host fails during startup while renaming
`sailor-ingest.sock` to its stale-socket path, reporting Windows error 1920,
“The file cannot be accessed by the system.” The backend was not running.
Removing only that stale runtime socket and querying its reparse metadata both
failed with the same OS error. No factory reset, data-directory deletion,
volume/image removal, WSL reset or Windows security-setting change was performed.
The attempted startup/status CLI processes were stopped.

The real unavailable-daemon CLI path was exercised: it produced a sealed HTML/
JSON package with `INFRA_ERROR` and no check executions. Unit tests also exercise
rejection of mutable image tags, weakened configuration, container creation
timeout cleanup, and an injected artifact-path field. These tests validate host
logic; they do not prove live isolation.

The full local regression run completed with **115 passed and 5 skipped** in
111.08 seconds ([JUnit](phase2-tests.xml)). Skips were four live-container tests
and the existing Windows symlink-privilege test. A subsequent focused executor
run passed **24 tests**, including 15 additional policy/transport rejection cases;
nine overlap the full run. No live-container pass is claimed.

Four opt-in live tests and a manual/PR Linux workflow are supplied. They must pass
before claiming the container controls were verified. At that point the live gate
was open: Docker had not started and the new workflow had not run. This local
block was subsequently resolved; see the acceptance record linked above.

## Remaining external-code gate

Even after live policy tests pass, independent observation capture is required:
the evaluated Python and observer share a container/user and hostile code may
forge observations. The original source/patch allowlist stays enabled. A fully
forged producer is outside EvidenceCI's artifact-consistency guarantees. External
repository intake is not enabled by this iteration.

The subsequent recovery preserved existing images and volumes. No factory reset
was required; see the separate recovery record.
