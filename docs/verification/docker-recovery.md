# Docker Desktop startup recovery

Date: 2026-11-03 (Asia/Bangkok).

Docker Desktop 4.90.0 failed during Ingest startup with Windows error 1920 while
renaming `sailor-ingest.sock`. Starting Docker directly from the agent shell
reproduced the failure. Native file deletion/reparse queries also failed.

A matching upstream report describes MSIX AppData virtualization affecting
AF_UNIX socket operations in child processes:
[openai/codex#52698](https://github.com/openai/codex/issues/52698).
This is consistent with the observed behavior; no OS-level trace was collected
here to independently establish the precise root cause.

## Successful recovery

With Docker processes stopped, Docker Desktop was launched through Windows
Explorer instead of directly as a child of the agent shell:

```powershell
Start-Process -FilePath 'C:\Windows\explorer.exe' -ArgumentList '"C:\Program Files\Docker\Docker\Docker Desktop.exe"' -WindowStyle Hidden
```

The Linux engine became available and `docker info` returned server 29.7.2.
The existing six images and the `mfg-data-pipeline_pgdata` named volume were
visible. No factory reset, data relocation, image/volume pruning, Docker upgrade,
WSL reset or Windows security-setting change was needed. Earlier attempts to
remove the runtime socket failed; they did not remove it.

A disposable smoke container ran successfully (exit 0) from the existing
`postgres:15-alpine` image, with entrypoint overridden to `/bin/true`, UID/GID
65534, no network, read-only root, dropped capabilities and no-new-privileges.
No database was started and no existing volume was mounted. The container was
automatically removed. The subsequent inventory showed zero containers, six
images and the original named volume. This verifies basic container execution
and cleanup, not the full PatchReplay isolation policy.

For future interactive startup, use the Windows Start menu or Explorer. Direct
agent-shell startup may reproduce the packaging-context failure. This is an
observed launch workaround, not a permanent upstream software fix.

This recovery only establishes Docker availability. PatchReplay's separate
[live acceptance tests](container-acceptance.md) subsequently passed their declared
controls and fixture decisions. That evidence has its own scope and limitations.
