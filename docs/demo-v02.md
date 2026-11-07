# PatchReplay 0.2 demo walkthrough

1. Show `function-list`: two reviewed upstream fixes, four synthetic controls and
   the original synthetic suite remain registered.
2. Run `function-demo --image sha256:<id> --output demo-v02`. Explain the independent
   host oracle and exact source/patch/image bindings while it runs.
3. Open `demo-v02/index.html`. Show a real historical failure before its upstream fix,
   matching after observations, both repeats and preserved regressions.
4. Open a noop and regressive control. Explain why plausible changes are rejected.
5. Show both claim files and run `check`. The demo's 2/6 suite count includes controls;
   it does not measure coding-agent effectiveness. Both actual fixes preserve probes.
6. Show new replay IDs in `results.json`; original packages remain unchanged.
7. In a separate provenance venv, run `scripts/function_provenance_smoke.py --subject
   <successful-run> --output signed-demo`. This uses a temporary host key, keeps only
   its public key, and verifies the explicit expected subject. Explain demo trust.
8. Finish with scope: historical upstream function extracts, declared observations,
   externally supplied trust inputs, no arbitrary intake or production claim.

Build the offline distribution with `scripts/release_bundle.py --wheel <wheel>
--demo demo-v02 --output patchreplay-0.2.0-review.zip`. It includes the wheel, demo,
reviewer guide, licenses and a release manifest. Validate with `--verify <zip>`.
The ZIP is prepared locally; publication and completed human trials are separate
recorded actions. Keep keys, passwords and private reviewer information outside it.
