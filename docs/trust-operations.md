# Operator trust and signing procedure

Signing is optional and host-only. Use the pinned provenance dependencies in a
separate environment. Private keys/passwords never enter candidate mounts or bundles.
The existing provenance CLI requires an external trusted key and expected-subject
file during verification. An adjacent demo key is an illustration, not an identity.

Before sharing operational evidence, the producer and recipient must agree through
an independently controlled channel on the public-key fingerprint, expected run,
case/suite/input identities and exact artifact hashes. Store approved expectations
outside subjects/bundles. `prepare` creates a draft; review is an operator action.
No project-wide production signing identity is provisioned by this release.

Keep encrypted signing keys in host-controlled storage. Supply passwords through a
private prompt or secret manager environment injection, never command-line arguments.
Back up encrypted keys under the operator's access policy. Restrict who can sign.

For rotation, independently distribute and acknowledge the new key fingerprint
before using it. Retain the old public key for explicitly authorized historical
verification. If compromise is suspected, stop signing with the key, communicate
revocation independently, and reject affected trust decisions according to the
recipient's incident policy. The offline verifier does not implement online
revocation, trusted timestamps, certificate chains or automatic freshness checks.

A valid signature binds the expected artifacts to the supplied trusted key. It does
not establish a real-world identity, truthful host observations, code correctness or
container security. Test verdicts and authentication remain separate outputs.
