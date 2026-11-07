# Recorded version 0.2 evidence

`demo/` is an unchanged copy of a completed installed-wheel Docker demo: two pinned
upstream fixes, four synthetic controls, both claim files and two fresh-ID replays.
Open [the offline index](demo/index.html), inspect the source/license/adapter records
under each package's `inputs/provenance/`, and run:

```sh
python -m patchreplay check examples/v02-evidence/demo/success_count.json
python -m patchreplay check examples/v02-evidence/demo/regression_all.json
```

The 2/6 count includes four controls and is not a model-effectiveness estimate.
Only declared function observations were tested; these are not full upstream builds
or complete test-suite results. Historical upstream commits are pinned; this does
not claim current releases retain their historical defects.

`provenance/` contains the signed real boltons-fix snapshot. Its random encrypted
private key was removed after host-only signing. Only the demo public key and
expected-subject file remain. They illustrate explicit external verifier inputs;
their adjacency is not an independently established maintainer trust channel.

```sh
python -m patchreplay_provenance verify --bundle examples/v02-evidence/provenance/bundle --trusted-key examples/v02-evidence/provenance/trust/public.pem --expectation examples/v02-evidence/provenance/trust/expected.json
```

Authentication does not establish correct code or truthful host observations.
The source/patch admission gate remains enabled. Recorded packages and signatures
were copied without reformatting or resealing. Exact-input replay requires matching
recorded engine, image and environment; ordinary offline verification does not.
