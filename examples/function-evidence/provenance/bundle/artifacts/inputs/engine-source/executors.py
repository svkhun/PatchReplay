"""Execution adapters. Container support remains restricted to approved fixtures."""
from pathlib import Path
import base64
import json
import re
import shutil
import subprocess
import uuid

from .process import execute


class LocalExecutor:
    policy = "controlled-fixtures-v1"

    def prepare(self, folder):
        pass

    def check(self, command, folder, env, timeout, log):
        return execute(command, folder, env, timeout, log)


class DockerExecutor:
    policy = "docker-fixtures-v1"

    def __init__(self, image):
        if not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise ValueError("Docker requires an immutable local image ID (sha256:<64 hex>), not a tag")
        self.image = image
        self.binary = shutil.which("docker") or "docker"

    def identity(self):
        return {"policy": self.policy, "image": self.image}

    def control(self, args):
        result = subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            raise OSError(f"Docker {args[0]} failed: {result.stderr[-1500:]}")
        return result.stdout

    def preflight(self):
        info = json.loads(self.control(["info", "--format", "{{json .}}"] ))
        if info.get("OSType") != "linux" or not all(info.get(k) for k in ("MemoryLimit", "PidsLimit", "CpuCfsQuota")):
            raise OSError("Docker must provide Linux containers with memory, PID and CPU limits")
        # Bind paths must refer to this machine, never an implicit remote daemon.
        context = json.loads(self.control(["context", "inspect"]))[0]
        endpoint = context["Endpoints"]["docker"]["Host"]
        import os
        if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
            raise OSError("Unset DOCKER_HOST/DOCKER_CONTEXT; select an explicit local Docker context")
        if not endpoint.startswith(("unix://", "npipe://")):
            raise OSError("Only local Docker endpoints are supported")
        image = json.loads(self.control(["image", "inspect", self.image]))[0]
        if image.get("Id") != self.image or image.get("Os") != "linux" or image["Config"].get("Volumes"):
            raise OSError("Image identity/platform mismatch or undeclared image volumes")

    def prepare(self, folder):
        shutil.copy2(Path(__file__).with_name("container_bridge.py"), folder / "container_bridge.py")

    def create_args(self, name, folder, selection, attempt):
        if "," in str(folder):
            raise ValueError("Docker bind source paths containing commas are unsupported")
        return ["create", "--name", name, "--pull=never", "--network=none", "--read-only",
                "--user=65534:65534", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
                "--memory=256m", "--memory-swap=256m", "--cpus=1", "--pids-limit=64",
                "--ipc=private", "--log-driver=none", "--ulimit=nofile=256:256", "--ulimit=fsize=2097152:2097152",
                "--tmpfs=/work:rw,noexec,nosuid,nodev,size=67108864,mode=1777",
                "--mount", f"type=bind,source={folder.resolve()},target=/input,readonly",
                "--workdir=/work", "--entrypoint=/usr/local/bin/python",
                "--env=HOME=/work", "--env=TMPDIR=/work", "--env=PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
                "--env=PYTHONDONTWRITEBYTECODE=1", self.image, "-I", "-B", "/input/container_bridge.py", selection, str(attempt)]

    @staticmethod
    def validate_config(config, image, folder):
        host, proc = config["HostConfig"], config["Config"]
        checks = [config["Image"] == image, host["NetworkMode"] == "none", host["ReadonlyRootfs"],
                  proc["User"] == "65534:65534", not host["Privileged"], host["CapDrop"] == ["ALL"],
                  "no-new-privileges:true" in host["SecurityOpt"], host["Memory"] == 268435456,
                  host["MemorySwap"] == 268435456, host["NanoCpus"] == 1000000000,
                  host["PidsLimit"] == 64, not host.get("Devices"), not host.get("Binds"),
                  not host.get("PidMode"), host["IpcMode"] == "private",
                  host["Tmpfs"] == {"/work": "rw,noexec,nosuid,nodev,size=67108864,mode=1777"}]
        mounts = host.get("Mounts", [])
        checks.append(len(mounts) == 1 and mounts[0]["Type"] == "bind" and mounts[0]["ReadOnly"]
                      and mounts[0]["Target"] == "/input" and mounts[0]["Source"] == str(folder.resolve()))
        if not all(checks):
            raise OSError("Container configuration did not preserve the required isolation policy")

    def check(self, command, folder, env, timeout, log):
        name = "patchreplay-" + uuid.uuid4().hex
        created = False
        result = {"command": [], "exit_code": None, "timeout": False, "duration_seconds": 0, "error": None}
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            args = self.create_args(name, folder, command[6], command[8])
            # Mark before create: timeout may occur after the daemon created the container.
            created = True
            self.control(args)
            config = json.loads(self.control(["inspect", name]))[0]
            self.validate_config(config, self.image, folder)
            transport = log.with_suffix(".transport")
            # Docker CLI needs its local context; no host environment values are forwarded into the container.
            import os
            result = execute([self.binary, "start", "--attach", name], folder, dict(os.environ), timeout, transport)
            result["command"] = [self.binary, *args]
            if result["timeout"] or result["error"] or result["exit_code"] != 0:
                log.write_bytes(transport.read_bytes())
                if not result["timeout"]:
                    result["error"] = result["error"] or "Container bridge failed; no trusted pytest observation"
            else:
                raw = transport.read_bytes()
                if len(raw) > 1_000_000:
                    raise ValueError("Oversized container response")
                payload = json.loads(raw)
                if set(payload) != {"exit_code", "records", "junit", "log"} or type(payload["exit_code"]) is not int:
                    raise ValueError("Invalid container response")
                result["exit_code"] = payload["exit_code"]
                destination = Path(command[7])
                for key, path in (("records", destination), ("junit", destination.with_suffix(".xml")), ("log", log)):
                    if payload[key] is not None:
                        path.write_bytes(base64.b64decode(payload[key], validate=True))
            transport.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            result["error"] = str(exc)
            log.write_text(str(exc), encoding="utf-8")
        finally:
            if created:
                try:
                    self.control(["rm", "--force", name])
                except (OSError, subprocess.SubprocessError) as exc:
                    result["error"] = f"Container cleanup failed: {exc}"
                    result["timeout"] = False  # Infrastructure failure takes precedence.
        return result
