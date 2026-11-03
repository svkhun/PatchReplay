"""Bounded subprocess lifecycle and an allowlisted environment."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time


def clean_environment(home: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    env = {"HOME": str(home), "USERPROFILE": str(home), "TMP": str(home), "TEMP": str(home),
           "TMPDIR": str(home), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONHASHSEED": "0",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_TERMINAL_PROMPT": "0", "GIT_ATTR_NOSYSTEM": "1"}
    if os.name == "nt":
        env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
        env["WINDIR"] = env["SystemRoot"]
    return env


def execute(command: list[str], cwd: Path, env: dict[str, str], timeout: float, log: Path) -> dict:
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    timed_out = False
    error = None
    code = None
    job = None
    proc = None
    with log.open("wb") as stream:
        try:
            if os.name == "nt":
                from .windows_job import WindowsJob
                job = WindowsJob()
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, shell=False,
                                    start_new_session=os.name != "nt",
                                    creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004) if os.name == "nt" else 0)
            if job:
                job.assign_and_resume(proc.pid)
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                if job:
                    job.terminate()
                else:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if proc.poll() is None:
                    proc.kill()
                code = proc.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = f"{type(exc).__name__}: {exc}"
            stream.write(error.encode("utf-8", errors="replace"))
        finally:
            if job:
                job.close()
            elif proc is not None and os.name != "nt":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
    # These are controlled fixtures. This retention limit is not a disk quota.
    if log.stat().st_size > 1_000_000:
        with log.open("rb") as stream:
            head = stream.read(1_000_000)
        log.write_bytes(head + b"\n[Log truncated to 1 MB]\n")
    return {"command": command, "exit_code": code, "timeout": timed_out,
            "duration_seconds": round(time.monotonic() - started, 6), "error": error}
