# Offline evidence provenance

The optional host-only CLI signs a snapshot of evidence and verifies it against
two external trust inputs: an explicitly trusted public key and an expected-subject
file reviewed by the recipient. Successful verification returns
`AUTHENTICATED_FOR_EXPECTED_SUBJECT`. This is separate from any test verdict.

It supports `patchreplay-v1` sealed packages and `observer-v1` experiment output.
It never executes evidence content, starts Docker, or fetches keys from a network.
The installed `patchreplay` and `evidenceci` commands keep their existing behavior.

## Try the checked-in example

```sh
python -m pip install -r requirements-provenance.lock
python -m pip install --no-deps -e .
python -m patchreplay_provenance verify --bundle examples/provenance-evidence/bundle --trusted-key examples/provenance-evidence/trust/demo-public.pem --expectation examples/provenance-evidence/trust/observer.expected.json
python scripts/provenance_demo.py --output provenance-output
```

Use a new demo output directory each time. The demo checks one valid subject and
seven rejection cases. It generates a random, encrypted private key in a temporary
host directory and retains only its public key. The checked-in key identifies this
demonstration; it is not an authenticated maintainer or organization identity.

When installing from this source tree, `pip install '.[provenance]'` adds the optional
cryptography dependency. The installed wheel includes the same CLI. The lock file pins its
transitive dependencies for the tested environment. Signing dependencies are not
added to `requirements.lock` or to the evaluator image. A separate host venv avoids
changing environment fingerprints needed by existing exact-input replays.

## Operator workflow

1. Obtain the producer's public-key fingerprint through a separately trusted
   channel. Keep that key outside the evidence bundle.
2. Run `prepare` on a reviewed subject. Inspect its run ID, input identities and
   exact artifact hashes, then store the expectation in a separately controlled
   location. `prepare` drafts data; it does not imply human approval or establish
   independent truth about the test results.
3. Sign the approved snapshot on the host. Private key, password and expectation
   are not supplied to the evaluator container.
4. Send the bundle. The recipient verifies it using their own key and expectation.
   Selecting a key or expectation merely because it arrived with the bundle does
   not establish external trust.

```sh
# Set PATCHREPLAY_SIGNING_PASSWORD through a private prompt or secret manager.
# The value is never a command-line argument; minimum length is 16 bytes.
patchreplay-provenance keygen --private-key .patchreplay/keys/producer.pem --public-key trusted-producer.pem --password-env PATCHREPLAY_SIGNING_PASSWORD
patchreplay-provenance prepare --subject examples/observer-evidence --kind observer-v1 --output expected-observer.json
patchreplay-provenance sign --subject examples/observer-evidence --expectation expected-observer.json --private-key .patchreplay/keys/producer.pem --password-env PATCHREPLAY_SIGNING_PASSWORD --output signed-observer
patchreplay-provenance verify --bundle signed-observer --trusted-key trusted-producer.pem --expectation expected-observer.json
```

For a regular sealed package, use `--kind patchreplay-v1` with its run directory.
Both failing and successful test packages may be authentic. Authentication never
changes a `REGRESSION_DETECTED`, `INCONCLUSIVE` or other original test status.

Private keys use encrypted PKCS8 PEM and new files only. POSIX creation requests
mode 0600; Windows inherits the destination directory ACL, so choose a protected
host key directory. No overwrite flag is supplied. No private key or password is
published by the demo. The PEM-content guard is not a general secret scanner.

## Version 1 wire contract

A bundle contains exactly `attestation.json` and an `artifacts/` directory.
The latter is an independent byte-for-byte snapshot, with no links or executable
import step. Partial signing outputs without an attestation are rejected.

`attestation.json` has exactly `statement` and `signature`:

| Statement field | Meaning |
| --- | --- |
| `type` | Fixed `patchreplay.provenance.v1` |
| `algorithm` | Fixed `Ed25519`; no algorithm negotiation or fallback |
| `key_id` | `sha256:` plus SHA-256 of the raw 32-byte public key |
| `signed_at` | UTC text `YYYY-MM-DDTHH:MM:SSZ`; signer-asserted, not a trusted timestamp |
| `subject` | The complete expected-subject object described below |

`signature` is strict base64 encoding of a 64-byte Ed25519 signature over:

```text
b"PatchReplay provenance v1\x00" + canonical_json(statement)
```

Canonical JSON here is the project's defined Python serialization: sorted keys,
compact separators, ASCII escaping, UTF-8 bytes, no non-finite numbers. Signed
metadata contains strings, maps and nulls, with no floating-point fields. This is
a project-specific format, not a claim of DSSE, in-toto or RFC 8785 compatibility.
Artifact hashes cover exact original bytes, including newlines. Duplicate JSON
fields, extra envelope fields, unsupported types and malformed signatures fail.

The expectation has exactly `type` (`patchreplay.expected-subject.v1`), `kind`,
`run_id`, `bindings`, and `artifacts` (relative filename to SHA-256). The signature
covers the entire expectation. The verifier also requires an equal expectation
supplied externally, preventing substitution of another validly signed run.

- `patchreplay-v1`: binds all existing source revision, patch, evaluator, suite,
  environment, engine, case and combined-input identities, plus policy and image
  (null for local execution). The existing manifest/decision consistency checks
  run offline; this does not authenticate the original pytest observer.
- `observer-v1`: binds source digests by fixture, the ordered function probes and
  expected values as evaluator identity, recorded experiment-engine identity,
  policy, image and unique request IDs. Its run ID is `observer-` plus the digest
  of sorted request IDs. `patch_sha256` is explicitly null because the experiment
  has no patch input. This adapter checks identity structure and uniqueness; it
  does not re-execute or independently certify the reported decisions.

Limits: 512 regular files, 2 MB per artifact, 32 MB total, 2,048 filesystem entries,
240-character relative paths, 512 KB metadata and 16 KB key files. Symlinks,
Windows reparse points, traversal and special files are rejected. Hashes cover
the regular-file set; empty artifact directories are not semantic content.

## Trust limits and key lifecycle

A key fingerprint identifies a key, not a legal person, repository owner, genuine
runner or trustworthy operating system. The host, signing process, crypto library,
key storage and separately managed trust inputs must be trusted. Concurrent
hostile filesystem mutation, compromised signing hosts and stolen keys are outside
this implementation's guarantees. A signature can authenticate a false report.

The offline verifier has no certificate authority, transparency log, revocation
service, trusted clock or one-time-use ledger. Verifying the same authorized bundle
again succeeds; this is not a freshness or anti-replay guarantee. To rotate trust,
distribute a new reviewed public-key fingerprint independently. Stop using a
compromised key as a trusted input; an old copy of that key will still verify its
old signatures. Changing a timestamp cannot make an untrusted producer trusted.

Exit codes: 0 for completed operation/authentication, 1 for rejected input or an
operational error, 2 for invalid CLI syntax or missing optional dependency.

Implementation uses PyCA's [Ed25519 signing/verification](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ed25519/)
and [encrypted key serialization](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/serialization/).
No signature primitive is implemented in this project.

See the [phase 2 verification record](verification/provenance/README.md) for local
tests, installed-wheel verification and the exact implementation commit's CI run.
