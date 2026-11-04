# Recorded Phase 3 function evidence

These are immutable copies of real local Docker observations from the Phase 3
acceptance run, not simulated passing records. All evaluated programs are reviewed
synthetic fixtures. Package names preserve their original run IDs; copying did not
regenerate reports, manifests or signatures.

- `good-*`: the declared wrong baseline values reproduced; patched bug and regression
  observations matched in both repeats.
- `regression-*`: the patch corrected the lower bound but broke the upper-bound probe.
- `timeout-*`: patched requests exhausted their budgets; this is never bug reproduction
  or a successful correction.
- `provenance/`: an offline signed snapshot of the good package, with a temporary demo
  key's public key and expected subject. The private key was removed, not published.

Open each `report.html` for an offline table and raw response view. Verify a package
with `python -m patchreplay verify <package>`. Replay additionally requires matching
engine/environment/image identities; restoring those is the operator's responsibility.

```sh
python -m patchreplay_provenance verify --bundle examples/function-evidence/provenance/bundle --trusted-key examples/function-evidence/provenance/trust/public.pem --expectation examples/function-evidence/provenance/trust/expected.json
```

The checked-in public key and adjacent expectation are demonstration inputs, not
independent evidence of a maintainer's identity or an established trust channel.
`AUTHENTICATED_FOR_EXPECTED_SUBJECT` does not mean the code is correct or observations
truthful. Request IDs correlate answers; a matching integer proves only that declared
observation. No real-project, arbitrary-code, escape-resistance or production claim
is made. See [acceptance evidence](../../docs/verification/function/README.md) and
[the contract](../../docs/function-workflow.md).
