# Offline provenance example

[Results](results.json) record one authenticated subject and seven correctly
rejected variants: changed, missing or added artifact; invalid signature;
untrusted key; wrong expected run; and unsigned bundle.

The [bundle](bundle/attestation.json) signs a snapshot of the earlier observer
experiment. Its intentionally forged pytest records remain labeled as a negative
demonstration; signing them does not make them genuine test passes.

```sh
python -m patchreplay_provenance verify --bundle examples/provenance-evidence/bundle --trusted-key examples/provenance-evidence/trust/demo-public.pem --expectation examples/provenance-evidence/trust/observer.expected.json
```

Install the optional host dependencies first; see [the guide](../../docs/provenance.md).
The public key and expectation in `trust/` are illustrative inputs for this demo.
They are not independently authenticated organizational trust anchors. In real
use, obtain and review both through a separately controlled channel.

The temporary encrypted private key and its random password were not retained.
No private key is included in this directory. The checked-in signature can be
verified offline; generating a new demo yields a different identity/signature.

All bytes are preserved by `.gitattributes`. Files inside `bundle/artifacts/` are
unchanged snapshots, including prose and relative links from the original context.
