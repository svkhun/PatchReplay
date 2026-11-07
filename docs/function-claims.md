# EvidenceCI function claims (schema 2)

Legacy schema 1 retains its pytest meanings. Schema 2 explicitly declares
`evaluation_kind: host-function-v1`; it never reinterprets pytest records. Its closed
contract is `schemas/function-claim.schema.json`. It binds suite/case scope, exact
manifest anchors and the complete expected execution identities, including image
and policy. Verification is offline and never executes evidence content.

```sh
python -m patchreplay claim-draft runs/<run-id> --kind regression_all --output claims.json
```

Place the draft above its evidence directories. Review the text-to-rule mapping,
case list, identities, assertions and manifest anchors, then explicitly change
`approval` from `UNREVIEWED` to `APPROVED_FOR_DECLARED_RULE`. `check` rejects unreviewed
drafts. The fixed `function-demo` templates are reviewed in source; they are not an
automatic approval mechanism for arbitrary user-authored prose.

`success_count` requires the entire pinned suite roster. Every declared case remains
in the denominator, including controls, timeouts, failures and inconclusive results.
Only `VERIFIED_FOR_DECLARED_CHECKS` contributes to the numerator. For the upstream
demo this is 2/6: two real fixes and four synthetic controls. This count demonstrates
decision boundaries and is not an estimate of model effectiveness.

`regression_all` allows an explicit subset of one suite. It requires complete numeric
before/after regression observations, a passing regression baseline and no integrity,
infrastructure or repeat-disagreement result. Every selected case must pass all
declared after-regression observations. Timeouts, malformed/missing/duplicate records
cannot establish a pass. Bug correction and regression preservation remain distinct.

Missing/duplicate references, mixed suite identities, mixed report kinds and invalid
packages are rejected. A changed external expectation is STALE. Valid observations
that contradict the stated counts yield CONTRADICTED. Consistent supported counts
yield SUPPORTED_FOR_SCOPE. Signature authentication remains independent of this rule.
