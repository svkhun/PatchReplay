"""Domain-separated Ed25519 attestations with externally supplied trust inputs."""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from patchreplay.integrity import canonical, digest, safe_path
from .subjects import describe, sha

DOMAIN = b"PatchReplay provenance v1\x00"
TYPE = "patchreplay.provenance.v1"
EXPECTED_TYPE = "patchreplay.expected-subject.v1"
MAX_FILE = 2_000_000
MAX_TOTAL = 32_000_000
MAX_FILES = 512


def ordinary(path, directory=False):
    info = path.lstat()
    if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 1024:
        raise ValueError("Symlinks and reparse points are not accepted")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError("Expected an ordinary directory" if directory else "Expected an ordinary file")


def read(path, limit=MAX_FILE):
    path = Path(path)
    ordinary(path)
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Input exceeds size limit")
    return data


def parse(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    result = json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
    if not isinstance(result, dict):
        raise ValueError("Expected JSON object")
    return result


def load(path):
    return parse(read(path, 512_000))


def exclusive(path, data, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def dump_new(path, value):
    exclusive(path, json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False).encode() + b"\n")


def inventory(root):
    root = Path(root).absolute()
    ordinary(root, directory=True)
    result, total, entries = {}, 0, 0
    pending = [root]
    while pending:
        # Stream entries so an oversized directory is rejected before allocating
        # an unbounded list of names. Errors must not silently omit a subtree.
        with os.scandir(pending.pop()) as children:
            for child in children:
                entries += 1
                if entries > 2048:
                    raise ValueError("Too many artifact entries")
                path = Path(child.path)
                relative = path.relative_to(root).as_posix()
                if len(relative) > 240:
                    raise ValueError("Artifact path too long")
                safe_path(root, relative)
                directory = child.is_dir(follow_symlinks=False)
                ordinary(path, directory=directory)
                if directory:
                    pending.append(path)
                    continue
                data = read(path)
                total += len(data)
                if total > MAX_TOTAL or len(result) >= MAX_FILES:
                    raise ValueError("Artifact budget exceeded")
                if re.search(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----", data):
                    raise ValueError("Private key material cannot be bundled")
                result[relative] = data
    if not result:
        raise ValueError("Empty artifact set")
    return result


def expectation(root, kind):
    files = inventory(root)
    run_id, bindings = describe(Path(root), kind)
    value = {"type": EXPECTED_TYPE, "kind": kind, "run_id": run_id, "bindings": bindings,
             "artifacts": {name: digest(data) for name, data in sorted(files.items())}}
    validate_expected(value)
    return value


def validate_expected(value):
    if not isinstance(value, dict) or set(value) != {"type", "kind", "run_id", "bindings", "artifacts"}:
        raise ValueError("Invalid expected-subject fields")
    if value["type"] != EXPECTED_TYPE or value["kind"] not in {"observer-v1", "patchreplay-v1"}:
        raise ValueError("Unsupported expected-subject type")
    if not isinstance(value["run_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value["run_id"]):
        raise ValueError("Invalid run ID")
    bindings = value["bindings"]
    if not isinstance(bindings, dict):
        raise ValueError("Invalid bindings")
    common = {"policy", "image", "engine_sha256", "evaluator_sha256", "patch_sha256"}
    expected_keys = common | ({"sources", "request_ids_sha256"} if value["kind"] == "observer-v1" else {
        "source_revision", "suite_sha256", "environment_sha256", "case_sha256", "inputs_sha256"})
    if set(bindings) != expected_keys or not isinstance(bindings["policy"], str):
        raise ValueError("Invalid binding fields")
    for name, item in bindings.items():
        if name.endswith("_sha256") and not (name == "patch_sha256" and value["kind"] == "observer-v1" and item is None):
            if not sha(item):
                raise ValueError("Invalid binding digest")
    if value["kind"] == "observer-v1":
        sources = bindings["sources"]
        if not isinstance(sources, dict) or not sources or not all(isinstance(k, str) and sha(v) for k, v in sources.items()):
            raise ValueError("Invalid source bindings")
        if bindings["patch_sha256"] is not None:
            raise ValueError("Observer experiment has no patch input")
    elif not isinstance(bindings["source_revision"], str) or not bindings["source_revision"].startswith("sha256:") or not sha(bindings["source_revision"][7:]):
        raise ValueError("Invalid source revision")
    image = bindings["image"]
    if image is not None and (not isinstance(image, str) or not image.startswith("sha256:") or not sha(image[7:])):
        raise ValueError("Invalid image identity")
    files = value["artifacts"]
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError("Invalid artifact list")
    for name, hashed in files.items():
        safe_path(Path.cwd() / ".provenance-validation", name)
        if not sha(hashed):
            raise ValueError("Invalid artifact digest")


def external(path, root):
    if Path(path).resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("Trust inputs and private keys must be outside the subject/bundle")


def key_id(public):
    return "sha256:" + digest(public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def keygen(private_path, public_path, password):
    if not isinstance(password, bytes) or len(password) < 16:
        raise ValueError("Key password must contain at least 16 bytes")
    if Path(private_path).exists() or Path(public_path).exists() or Path(private_path).resolve() == Path(public_path).resolve():
        raise ValueError("Key files must be distinct new paths")
    private = Ed25519PrivateKey.generate()
    exclusive(private_path, private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                  serialization.BestAvailableEncryption(password)), private=True)
    exclusive(public_path, private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    return key_id(private.public_key())


def prepare(subject, kind, output):
    external(output, subject)
    value = expectation(subject, kind)
    dump_new(output, value)
    return value


def sign(subject, expected_path, private_path, password, output):
    subject, output = Path(subject), Path(output)
    for path in (expected_path, private_path):
        external(path, subject)
        external(path, output)
    external(output, subject)
    if subject.resolve().is_relative_to(output.resolve()):
        raise ValueError("Subject and output must not overlap")
    expected = load(expected_path)
    validate_expected(expected)
    if not isinstance(password, bytes) or len(password) < 16:
        raise ValueError("Key password must contain at least 16 bytes")
    private_bytes = read(private_path, 16_384)
    if not private_bytes.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"):
        raise ValueError("An encrypted PKCS8 private key is required")
    private = serialization.load_pem_private_key(private_bytes, password=password)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("Only encrypted Ed25519 private keys are supported")
    # Snapshot bytes once; validate and sign the copy, never host paths in a manifest.
    files = inventory(subject)
    output.mkdir(parents=True, exist_ok=False)
    artifacts = output / "artifacts"
    artifacts.mkdir()
    for name, data in files.items():
        exclusive(safe_path(artifacts, name), data)
    if canonical(expectation(artifacts, expected["kind"])) != canonical(expected):
        raise ValueError("Subject differs from the externally expected run, inputs or artifacts")
    statement = {"type": TYPE, "algorithm": "Ed25519", "key_id": key_id(private.public_key()),
                 "signed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "subject": expected}
    signature = private.sign(DOMAIN + canonical(statement))
    envelope = {"statement": statement, "signature": base64.b64encode(signature).decode("ascii")}
    dump_new(output / "attestation.json", envelope)
    return statement


def verify(bundle, public_path, expected_path):
    bundle = Path(bundle)
    external(public_path, bundle)
    external(expected_path, bundle)
    ordinary(bundle, directory=True)
    if {p.name for p in bundle.iterdir()} != {"artifacts", "attestation.json"}:
        raise ValueError("Bundle must contain only artifacts and attestation.json")
    expected = load(expected_path)
    validate_expected(expected)
    envelope = load(bundle / "attestation.json")
    if set(envelope) != {"statement", "signature"}:
        raise ValueError("Invalid envelope fields")
    statement = envelope["statement"]
    if not isinstance(statement, dict) or set(statement) != {"type", "algorithm", "key_id", "signed_at", "subject"}:
        raise ValueError("Invalid statement fields")
    if statement["type"] != TYPE or statement["algorithm"] != "Ed25519":
        raise ValueError("Unsupported signature type or algorithm")
    if not isinstance(statement["signed_at"], str):
        raise ValueError("Invalid signed time")
    datetime.strptime(statement["signed_at"], "%Y-%m-%dT%H:%M:%SZ")
    # Canonical comparison distinguishes true from 1, unlike Python dict equality.
    if canonical(statement["subject"]) != canonical(expected):
        raise ValueError("Attested subject differs from the externally expected run or inputs")
    public = serialization.load_pem_public_key(read(public_path, 16_384))
    if not isinstance(public, Ed25519PublicKey) or statement["key_id"] != key_id(public):
        raise ValueError("Signer is not the externally trusted Ed25519 key")
    if not isinstance(envelope["signature"], str):
        raise ValueError("Invalid signature encoding")
    signature = base64.b64decode(envelope["signature"], validate=True)
    if len(signature) != 64:
        raise ValueError("Invalid signature length")
    try:
        public.verify(signature, DOMAIN + canonical(statement))
    except InvalidSignature as exc:
        raise ValueError("Invalid signature") from exc
    if canonical(expectation(bundle / "artifacts", expected["kind"])) != canonical(expected):
        raise ValueError("Artifact content or bindings do not match the signed subject")
    return {"status": "AUTHENTICATED_FOR_EXPECTED_SUBJECT", "key_id": statement["key_id"],
            "run_id": expected["run_id"], "kind": expected["kind"], "artifact_count": len(expected["artifacts"]),
            "scope": "Signature, expected-subject binding and artifact integrity; not correctness, freshness or real-world signer identity."}
