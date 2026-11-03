# Recorded synthetic demonstration

Open [the offline index](evidence/index.html) to inspect the recorded cases and
claims. These packages were produced by running the real local evaluator on
Windows. They are not mocked results or model output. The fixture source itself
is synthetic; neither the 1/10 count nor any timing estimates general agent or
real-project performance.

Every run folder contains its manifest, saved inputs, JSON/HTML reports and the
logs that were actually produced. Some preflight failures intentionally contain
no check logs. The six claim files at the root demonstrate support, contradiction,
staleness, missing evidence and a mismatched manifest anchor. The tampered-anchor
example deliberately uses the wrong hash; the actual successful package is
preserved unchanged.

From the repository root:

```sh
python -m patchreplay check examples/evidence/claim-suite-supported.json
python -m patchreplay check examples/evidence/claim-wrong-number.json
python -m patchreplay demo --output demo-output
```

The second command intentionally exits 1. Generate fresh evidence on your own
machine. Exact-input replay of the recorded Windows packages requires the
recorded Python, distribution versions, Git, platform and engine identities.
Cross-platform reruns create new environment identities instead of pretending
to be identical replays. See [verification notes](../docs/verification/README.md).

Do not edit or add files inside a sealed run folder. Claims and verification
results belong outside it. `.gitattributes` preserves every byte in `evidence/`
so raw Windows logs retain their recorded hashes across Git checkouts.
