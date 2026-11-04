# Recorded container evaluations

These are real runs of the registered synthetic fixtures through Docker Desktop's
Linux engine, not mocked results. They demonstrate three decisions, not a suite
success rate or coding-agent performance.

| Case | Observed decision | Report |
| --- | --- | --- |
| Good correction | VERIFIED_FOR_DECLARED_CHECKS | [HTML](good-88d4b8780666/report.html) |
| Regressive correction | REGRESSION_DETECTED | [HTML](regression-657db9dc5f0e/report.html) |
| Deliberately slow patch | INCONCLUSIVE | [HTML](timeout-4f515ea83d60/report.html) |

The package manifests and decision consistency were verified. EvidenceCI's
[explicit regression claim](claim-regressions.json) was
[supported for its declared scope](results.json).

```sh
python -m patchreplay check examples/container-evidence/claim-regressions.json
```

Image used:
`sha256:6234ccbd3a3481bd5c878f06c7714e0a4b98d46e07c4341d5bf4ca76a06fdf6e`.
See [runtime/build identities](../../docs/verification/container-runtime.json)
and [live verification](../../docs/verification/container-acceptance.md).
The image is local, not published to a registry. Rebuilding can produce a different
image ID; that is a new environment rather than an identical replay.

All package bytes are preserved by `.gitattributes`. External patches remain
disabled because hostile code could interfere with an observer in the same
container; passing these checks does not resolve producer authenticity.
