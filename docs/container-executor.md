# Experimental container executor

Status: live policy checks, three synthetic evaluation cases and replay passed on
this Windows host's Docker Desktop Linux engine and on GitHub's Ubuntu runner.
See [verification](verification/container-acceptance.md).
This is validation of the declared checks, not a sandbox certification. External
repository/patch admission remains disabled. The local executor remains the default.

## Run

Use a local Linux Docker daemon with memory, CPU and PID limit support. Build
the evaluator from a reviewed Python image digest, then use its immutable local
image ID. Building may access the registry; evaluation uses `--pull=never` and
no network. The base digest and final image ID must be retained with build evidence.

```sh
docker build --build-arg BASE_IMAGE=python@sha256:<reviewed-digest> -f containers/Dockerfile -t patchreplay-evaluator .
docker image inspect patchreplay-evaluator --format '{{.Id}}'
python -m patchreplay run good --executor docker --image sha256:<image-id> --output container-runs
```

`--image` rejects tags. Image ID and policy are included in the environment
fingerprint, so a local observation cannot be reused as container evidence.
Replay reconstructs the recorded executor and rechecks admission and preflight.
Unavailable Docker produces a sealed `INFRA_ERROR` package without falling back
to local execution.

## Declared controls

- Linux-only local daemon; unsupported resource controls fail preflight.
- One read-only bind mount containing only the per-check approved source,
  evaluator and transport scripts. No host home, credentials, Docker socket or
  writable host output directory is mounted.
- UID/GID 65534, read-only root, no network, dropped capabilities, no-new-privileges,
  private IPC and the Docker default seccomp profile.
- 256 MiB memory (no additional swap), one CPU, 64 PIDs, 64 MiB tmpfs,
  bounded file size and open-file count. tmpfs is noexec/nosuid/nodev.
- The created configuration is inspected before start. Execution timeout is
  followed by daemon-side forced container removal, including descendants;
  cleanup failure is an infrastructure error.
- Results travel through a bounded JSON/base64 envelope into fixed host artifact
  paths. Container data cannot supply a host filename. A malformed response
  cannot count as a passing test.

`LocalExecutor` and `DockerExecutor` share the check adapter interface; Git patch
application and input admission remain trusted host operations. Docker's control
plane uses the operator's Docker context. That environment is not forwarded into
the evaluation container.

## Acceptance and remaining boundary

Set `PATCHREPLAY_TEST_IMAGE` to the built immutable image ID and run
`python -m pytest tests/test_container_live.py -q`. Four tests cover actual UID,
network interfaces, read-only filesystem, absent host-secret environment variable,
capabilities, no-new-privileges, cgroup limits, correct/regressive patches and
timeout cleanup. The new manual/PR GitHub workflow builds and records its image
before running these checks; relevant pushes to `main` also trigger it. A skipped
test is not evidence that a control works.

The container bridge and evaluated Python share a container and user. Hostile
source could forge pytest records or interfere with the observer. Existing
EvidenceCI checks detect mismatched artifacts and contradictory records, but
cannot authenticate a fully forged observation from a compromised producer.
Independent observation capture/attestation remains an unresolved gate for
external patches. Containers share their daemon host kernel and have not received
an escape assessment. These controls are not a security certification.

The image ID pins installed dependencies, but Docker/kernel versions are not yet
part of the replay fingerprint. OS scheduling and host load remain uncontrolled.
The tests inspect enforced cgroup values; they are not an exhaustive denial-of-
service or exploit suite. Docker startup/inspection overhead is separate from
the per-check attach timeout. Per-operation control commands are bounded at 15s.

References: [Docker run controls](https://docs.docker.com/engine/containers/run/),
[tmpfs](https://docs.docker.com/engine/storage/tmpfs/),
[Docker security boundary](https://docs.docker.com/engine/security/).
