# Host-owned observation experiment

Historical Phase 1 experiment. Phase 3 provides an independent installed
[host-function workflow](function-workflow.md), preserving this experiment and its
recorded artifacts. The new report format does not reinterpret these results.

Status: a repository-only prototype for registered integer function probes.
It is not a new public executor, arbitrary pytest isolation, or external repository
admission. Existing PatchReplay commands retain their reviewed source/patch catalog.

## Threat and demonstrated weakness

The existing worker imports the candidate in the same process as pytest. The
container bridge then reads records from a filesystem writable by that process.
Read-only source and evaluator mounts do not make those output records authentic.

The fixed `forge_records` fixture writes passing records to `/work/records.json`
and exits without executing the declared test bodies. The experiment invokes the
internal Docker adapter with that reviewed attack fixture. If the existing
`interpret` function returns `PASS`, the experiment has reproduced the weakness.
This is a single-check demonstration, not a fabricated production evidence package
or a claim that the public catalog admitted the attack. It deliberately bypasses
admission only in this fixed test harness; no external path or source argument exists.

## New boundary

```text
Trusted host                               Untrusted container
approved probes + expected values          candidate.py + guest.py
fresh request ID and numeric arguments  ->  execute one function request
strict response parser                 <-  bounded JSON numeric answer
compare observed value to expected
record result and forcibly remove container
```

The host owns the expected values, protocol validation, comparison and final
record. Only `candidate.py` and `guest.py` enter the input mount. The evaluator,
expected values, host output folder, credentials and signing keys are not mounted.
A fresh container is used for every request. The guest sends no verdict: extra
fields such as `status: PASS` invalidate the response.

The protocol accepts exactly one UTF-8 JSON object with integer `protocol: 1`,
the current `request_id` and a bounded integer `value`. It rejects duplicate
fields/messages, non-finite numbers, booleans as integers, missing/extra fields,
wrong request IDs and excessive nesting. The host retains at most 4,097 response
bytes in memory, detects overflow beyond 4,096 bytes, and kills the attach client.
Timeout, nonzero exit or cleanup failure cannot yield `MATCH`. Container removal
is separate from terminating the Docker CLI.

The Docker controls are inherited from [the fixture executor](container-executor.md).
Scratch mounts are created under the selected workspace. The first attempt using
an AppData temp path timed out at Docker create; a subsequent workspace-mount run
passed. The precise cause was not independently traced.

## What this proves, and what it does not

`MATCH` means the returned integer equals the host's expected integer for that
one request. A candidate may compute, hardcode or guess that correct answer.
The observer cannot prove which internal code ran, hide a public test corpus,
or establish behavior on other inputs. Request IDs reject accidental cross-run
responses; the guest sees them, so they are not authentication or an anti-forgery
secret. Neither hashes nor a future signature would turn a false observation into
truth.

Trust assumptions: the host oracle and experiment code, reviewed image, Docker
daemon and host kernel are trusted. The candidate, guest adapter, stdout and guest
filesystem are untrusted. This experiment addresses result comparison for a tiny
black-box interface; it does not establish container escape resistance, side-channel
resistance, generic pytest observation integrity, or producer authenticity.

## Run and inspect

From the repository root, with the pinned runtime installed and an immutable
image built as described in the container guide:

```sh
python -m experiments.observer_boundary --image sha256:<local-image-id> --output test-output/observer-demo
python -m pytest tests/test_observer_boundary.py -q
# Set PATCHREPLAY_TEST_IMAGE to enable the live test:
python -m pytest tests/test_observer_live.py -q
```

Use a new output directory per run. `results.json` includes source/experiment
hashes, requests, host expectations, bounded raw responses, decisions and cleanup
results. `legacy-demonstration/` retains the intentionally forged records and its
interpretation. These files are experimental observations, not sealed PatchReplay
packages; `patchreplay verify/check/replay` do not accept them as such.

The expected demo contains 15 host observations: four inputs each for buggy and
correct clamp functions, plus record forgery, verdict injection, duplicate output,
wrong-round response, empty disconnect, timeout and excessive output. The legacy
weakness must reproduce, correct answers must match, buggy lower-bound answers
must mismatch, all seven adverse cases must be rejected or time out, and every
container must be removed. GitHub container CI runs this same acceptance test.

## Decision before the next phase

Local verification and archived observations are in the
[phase 1 record](verification/observer/README.md).

Keep arbitrary repository intake disabled. This interface is suitable for further
reviewed, black-box function cases; it is not a transparent replacement for pytest.
Next, define the trust/attestation contract for host-produced observations and
review which real bugs can be expressed through this limited interface. Preserve
the distinction between an authenticated producer and a correct observation.
