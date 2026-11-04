# Security boundary and limitations

The [Phase 3 host-function workflow](function-workflow.md) keeps numeric comparison
and aggregate decisions on the host for registered integer-function cases. It
addresses guest verdict forgery for that interface only; it does not authenticate
internal execution or fix the legacy pytest observer's trust boundary. Optional
signatures bind a key to expected artifacts, not truthful code behavior. External
sources and patches remain disabled in both workflows.

## What is supported

The local executor admits only this release's controlled, registered synthetic
source/evaluator/patch combinations. It does not accept arbitrary GitHub URLs,
local external repositories, unregistered patch code or arbitrary commands.
No elevated permissions, repository credentials, Git remotes or API keys are
required to run the demo.

Before choosing the executor, `doctor` probes Python, pytest, Git, Docker and
Podman. Container presence does not enable external code execution. A container
executor is experimental and available only for approved fixtures; see
[its policy and remaining gates](container-executor.md). Local execution remains the default.

Controls implemented:

- Fresh temporary copies for each phase; no mutation of a user's working tree.
- Strict relative paths; rejects absolute paths, traversal, Windows ADS/device
  names, symlinks/junctions, quoted paths, mode changes and binary diffs.
- Patch path allowlist plus complete patch-byte registration. Git's default
  outside-worktree protection stays enabled; `--unsafe-paths` is never used.
- Evaluator and source hashes checked before execution; all files in each
  check workspace compared again afterward.
- Python isolated mode, disabled pytest plugin autoload/conftest, fixed node IDs,
  no shell, no inherited PATH/PYTHONPATH or credential environment variables.
- Temporary HOME and temp paths. Git global/system config and prompting disabled.
- Per-command timeout. POSIX process groups are killed; Windows starts a
  suspended process, assigns it to a kill-on-close Job Object, then resumes it.
  Failure to assign a job fails closed. Tests exercise descendant termination.
- Escaped report content and a restrictive offline Content Security Policy.
- A separately anchored manifest hash for claims, full file-set comparison,
  content hashes, identities, and recomputation of check/report decisions.

## What is not provided

The local executor is **not a sandbox**. Its Python has the host user's OS access.
Removing inherited secrets from the environment does not prevent reading host
files or contacting the network. The local executor has no network restriction,
filesystem namespace, syscall policy, memory quota, CPU quota or disk quota.
The 1 MB log retention limit is applied after process completion, not during
execution. Malicious code could attack the evaluator or forge observations.
Therefore only reviewed fixture bytes are allowed to execute.

Process-tree cleanup is not a security boundary, especially for detached or
adversarial POSIX descendants. The tested fixtures do not detach processes. Parent
crashes, OS crashes, kill failures and a full disk may leave temporary files or
incomplete artifacts. Unsealed/inconsistent evidence must not be accepted.

SHA-256 is tamper detection relative to a trusted anchor, not a signature or an
attestation. If an attacker can replace the producer, artifacts and the trusted
claim manifest together, this MVP cannot establish authenticity. Store claims
and their manifest anchors in a separately reviewed/trusted context. Plain
`verify` without an anchor checks internal consistency only.

Logs, snapshots and argv may contain local absolute paths or data supplied by
the fixture author. Review before sharing. There is no automatic secret scanner
and no claim that artifacts are safe to publish without review.

## Required before accepting external patches

Implement and independently test an executor with an immutable environment
image, no host mounts/secrets, network policy, non-root process identity,
resource quotas, process lifecycle guarantees, and external observation capture.
Then threat-model malicious source, patches, tests, build hooks, dependencies,
artifact paths, symlink races and forged outputs. Decide whether containers meet
the threat model or a VM boundary is necessary. Do not bypass the catalog to
simulate this support.

## AI boundary

No live model, recorded model result, or mock model output is used by the current
runtime. An optional future assistant may propose a reproducer, summarize logs
with artifact/line references, or draft claim mappings. All such artifacts must
record `mode: live|recorded|mock`, model/provenance, referenced artifact hashes,
and human approval status. Proposed tests cannot enter an approved evaluator
without explicit review and a new evaluator/suite identity. A model's prose
must never override the deterministic decision or EvidenceCI status.
