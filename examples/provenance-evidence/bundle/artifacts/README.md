# Recorded host-oracle experiment

These are experimental observations of registered synthetic fixtures, not sealed
PatchReplay evidence packages or a benchmark of coding agents.

- [Results](results.json): 15 observations matched the expected decision table;
  all created containers were removed.
- [Known legacy weakness](legacy-demonstration/demonstration.json): the internal
  pytest-record interpreter accepted forged records as `PASS` for one check.
- [Forged records](legacy-demonstration/records.json): intentionally fake test
  observations produced by the reviewed attack fixture. They are not real passes.
- [Verification record](../../docs/verification/observer/README.md) and
  [threat model](../../docs/observer-boundary.md).

The old path was exercised through an internal test harness. The public evaluator
still rejects unregistered source/patch bytes. The same record-forgery fixture
produced `INVALID_RESPONSE` with the new host-owned function oracle.

`results.json` records the current experiment source hashes, immutable image,
requests and host expectations. It has no trusted signature or manifest anchor.
Re-run from the repository using the command in the threat-model document;
`patchreplay verify/check/replay` does not consume this experimental format.
