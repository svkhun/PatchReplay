"""Canonical identities, conservative paths, and anchored artifact verification."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath


class IntegrityError(ValueError):
    pass


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(value: object) -> str:
    return digest(canonical(value))


def read_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    obj = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                     parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid number: {value}")))
    if not isinstance(obj, dict):
        raise ValueError("Expected a JSON object")
    return obj


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise IntegrityError(f"Unsafe artifact path: {relative!r}")
    parts = relative.split("/")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    if PurePosixPath(relative).is_absolute() or any(
        p in ("", ".", "..") or p.endswith((" ", ".")) or p.split(".")[0].lower() in reserved
        or any(ord(c) < 32 or c in '<>"|?*' for c in p) for p in parts
    ):
        raise IntegrityError(f"Unsafe artifact path: {relative!r}")
    target = root.joinpath(*parts)
    for part in [target, *target.parents]:
        if part == root.parent:
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise IntegrityError(f"Links are not allowed: {relative}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise IntegrityError("Path escapes package")
    return target


def tree_files(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        safe_path(root, rel)
        if path.is_file():
            result[rel] = digest(path.read_bytes())
    return result


def tree_hash(root: Path) -> str:
    return identity(tree_files(root))


def fixture_hash(root: Path) -> str:
    """pip may compile package data; caches are neither identity nor copied inputs."""
    return identity({path: value for path, value in tree_files(root).items()
                     if "__pycache__" not in path.split("/")})


def patch_paths(patch: bytes) -> set[str]:
    """Accept a small, auditable subset of Git text diffs; fail closed."""
    try:
        text = patch.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntegrityError("Only UTF-8 text patches are supported") from exc
    if "\x00" in text or len(patch) > 100_000:
        raise IntegrityError("Invalid or oversized patch")
    paths = set()
    for line in text.splitlines():
        if line.startswith("diff --git "):
            match = re.fullmatch(r"diff --git a/([A-Za-z0-9_./-]+) b/([A-Za-z0-9_./-]+)", line)
            if not match or match[1] != match[2]:
                raise IntegrityError("Renames, quoted paths, and unusual paths are unsupported")
            paths.add(match[1])
        elif line.startswith(("--- ", "+++ ")):
            raw = line[4:]
            if raw != "/dev/null":
                if not raw.startswith(("a/", "b/")) or raw[2:] not in paths:
                    raise IntegrityError("Patch headers disagree")
        elif line.startswith(("old mode", "new mode", "new file mode", "deleted file mode", "rename ", "copy ", "GIT binary", "Binary files")):
            raise IntegrityError("File creation/deletion, mode changes, renames, and binary patches are unsupported")
    if not paths:
        raise IntegrityError("No supported diff headers")
    for path in paths:
        safe_path(Path.cwd(), path)
        if any(part.lower() in {".git", ".hg", "__pycache__"} for part in path.split("/")):
            raise IntegrityError("Protected metadata path")
    return paths


def seal_package(root: Path) -> str:
    files = tree_files(root)
    files.pop("manifest.json", None)
    manifest = {"schema_version": 1, "algorithm": "sha256", "files": files}
    write_json(root / "manifest.json", manifest)
    return digest((root / "manifest.json").read_bytes())


def verify_package(root: Path, anchor: str | None = None) -> dict:
    safe_path(root, "manifest.json")
    raw = (root / "manifest.json").read_bytes()
    if anchor is not None and digest(raw) != anchor:
        raise IntegrityError("Manifest differs from the claim's pinned SHA-256")
    manifest = read_json(root / "manifest.json")
    if set(manifest) != {"schema_version", "algorithm", "files"} or manifest["schema_version"] != 1 or manifest["algorithm"] != "sha256":
        raise IntegrityError("Unsupported manifest format")
    if not isinstance(manifest["files"], dict) or "report.json" not in manifest["files"]:
        raise IntegrityError("Manifest lacks report.json")
    actual = tree_files(root)
    actual.pop("manifest.json", None)
    if actual != manifest["files"]:
        raise IntegrityError("Evidence files are missing, added, or changed")
    return read_json(root / "report.json")

