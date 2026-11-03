# Two-minute demo storyboard

| Time | Screen | Narration / action |
| --- | --- | --- |
| 0:00–0:15 | README product statement, then demo index | “A coding-agent patch is a proposal. PatchReplay turns it into evidence a maintainer can inspect and rerun.” |
| 0:15–0:30 | `patchreplay run good`, open printed HTML | “This MVP uses reviewed synthetic Python fixtures. No model or API key is involved.” |
| 0:30–0:50 | Good report: before/after rows, declared nodes | “Both approved bug examples fail with assertions before the patch. They pass afterward. Regression checks already passed on the baseline and still pass.” |
| 0:50–1:05 | Narrow and regression reports side by side | “Passing one example is insufficient. This patch misses a second example; another fixes the bug but breaks an existing checked behavior.” |
| 1:05–1:20 | Protected, environment-error and unstable reports | “An edited protected test fails integrity. Environment errors stay separate. Timeout or inconsistent observations produce uncertainty.” |
| 1:20–1:40 | `patchreplay check ...claim-wrong-number.json`, then supported claim | “EvidenceCI checks explicit scope and arithmetic. It rejects eight out of ten when the evidence says one out of ten. Errors and timeouts remain in the denominator.” |
| 1:40–1:55 | Patch hash, manifest, replay command and CLI output | “The package records source, patch, evaluator, dependencies and commands. Replay checks identities and creates another observation.” |
| 1:55–2:00 | Security boundary notice | “This demonstrates an evaluation workflow, not agent performance. External code needs a hardened executor next.” |

Prepare the full demo before recording to keep the video within two minutes.
Use `python -m patchreplay demo --output demo-output`, then keep the index and
chosen reports open. Do not edit failures out of the evidence. Label accelerated
terminal playback if used. Show the actual observed results and avoid implying
that the fixture count is a real-world success rate.
