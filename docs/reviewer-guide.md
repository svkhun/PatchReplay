# PatchReplay 0.2 reviewer trial

Use Python 3.11 or 3.12, Git and Docker Desktop with Linux containers. Use a fresh
directory and venv. Keep signing dependencies in a different host venv.

```sh
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install -r requirements.lock
python -m pip install --no-deps wheel/patchreplay-0.2.0-py3-none-any.whl
python -m patchreplay doctor
python -m patchreplay function-list
```

Build the reviewed evaluator using `containers/Dockerfile` in the matching source
checkout. Record the base RepoDigest and resulting image ID. Use `--pull=never`
runtime behavior; evaluation never installs dependencies or fetches source.
The source checkout's container guide has the full build recipe. For existing
recorded runs, rebuilding an image is not guaranteed to reproduce its image ID;
restore the recorded image and software environment for exact-input replay.

```sh
python -m patchreplay function-demo --image sha256:<immutable-image-id> --output reviewer-demo
python -m patchreplay check reviewer-demo/success_count.json
python -m patchreplay check reviewer-demo/regression_all.json
```

Open `reviewer-demo/index.html`. Six cases comprise two upstream fixes and four
synthetic controls. Expect two verified fixes, two ineffective controls and two
regressive controls. The 2/6 count is a decision demonstration, not a benchmark.
The command also replays both successful fixes with fresh run IDs.

Each reviewer independently completes these tasks:

1. Install the wheel in a clean venv and record OS/Python/Docker versions.
2. Run the demo and identify the upstream commit, source adaptation, license and
   meaning of the exception sentinel in each successful case's input provenance.
3. Identify why each control is nonverified. Check both repeats in a case report.
4. Run `verify` and `replay` for a successful case. Explain why the run ID changes.
5. Modify the asserted numerator in a copy of the claim and confirm rejection.
6. Draft a claim with `claim-draft`. Confirm `check` rejects its UNREVIEWED status.
   Review the text, rule, suite and expected identities before explicitly setting
   `approval` to `APPROVED_FOR_DECLARED_RULE` in the draft JSON.
7. In a separate provenance venv, verify a demo bundle with independently selected
   public key and expectation paths. Explain why authentication is not test success.
8. Record confusing steps, exact failures, task completion and time spent. Use an
   alias; avoid personal data and secrets. Return the completed trial record.

Two independent human records are required for a claim of human-usability acceptance. CI,
agent testing and automated fresh environments do not substitute for those records.
The repository template is `docs/reviewer-trial-template.json`; blank templates
are not completed trials. Do not mark acceptance until both records are reviewed.

For the current milestone the user authorized simulated trials instead. Run
`scripts/simulate_reviewers.py` with separate installed-wheel evaluator/provenance
interpreters, a completed function demo and signed bundle. Its records explicitly
say `SIMULATED_AUTOMATED`, with zero human participants. This completes the scoped
automated rehearsal; human usability/comprehension remains unmeasured.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Docker unavailable or pipe denied | Start Docker Desktop interactively; confirm the local Linux context. Never use local execution as a fallback. Windows recovery instructions are in `docs/verification/docker-recovery.md`. |
| Image rejected | Resolve the existing image to a full `sha256:` ID; tags are unsupported. |
| Admission drift | Restore the reviewed release; do not rewrite catalog hashes to approve unknown code. |
| Replay engine/environment drift | Restore the original Python, package inventory, Git, Docker/kernel metadata, image and engine. A new release evaluates as a new observation. |
| Signature UNAVAILABLE | Install the optional locked provenance dependencies in a separate host venv. |
| Signature rejected | Recheck independently trusted key and expected subject; do not trust replacement files merely because they arrived with the bundle. |

Review evidence before sharing: logs and command metadata retain local paths.
