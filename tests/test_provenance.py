"""Detached trust inputs, content binding and failure-closed authentication."""
import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

pytest.importorskip("cryptography", reason="Install requirements-provenance.lock for host provenance tests")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from patchreplay.integrity import canonical, digest
from patchreplay_provenance import core
from patchreplay_provenance.cli import main

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = b"test-only-password-not-a-real-credential"


@pytest.fixture(scope="session")
def signing_keys(tmp_path_factory):
    directory = tmp_path_factory.mktemp("signing-keys")
    private, public = directory / "private.pem", directory / "public.pem"
    core.keygen(private, public, PASSWORD)
    return private, public


@pytest.fixture
def signed(tmp_path, signing_keys):
    subject = tmp_path / "subject"
    shutil.copytree(ROOT / "examples/observer-evidence", subject)
    expected = tmp_path / "trust" / "expected.json"
    core.prepare(subject, "observer-v1", expected)
    bundle = tmp_path / "bundle"
    private, public = signing_keys
    core.sign(subject, expected, private, PASSWORD, bundle)
    return subject, expected, bundle, private, public


def rewrite(path, value):
    path.write_bytes(json.dumps(value, sort_keys=True).encode())


def test_observer_signature_roundtrip_and_detached_key(signed):
    subject, expected, bundle, private, public = signed
    result = core.verify(bundle, public, expected)
    assert result["status"] == "AUTHENTICATED_FOR_EXPECTED_SUBJECT"
    statement = core.load(bundle / "attestation.json")["statement"]
    bindings = statement["subject"]["bindings"]
    assert bindings["patch_sha256"] is None and bindings["image"].startswith("sha256:")
    assert "private.pem" not in statement["subject"]["artifacts"]
    assert set(p.name for p in bundle.iterdir()) == {"artifacts", "attestation.json"}
    assert core.read(private).startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----")
    if os.name != "nt":
        assert private.stat().st_mode & 0o077 == 0
    # Verification uses the immutable copy, not the original mutable source path.
    (subject / "results.json").write_text("changed")
    assert core.verify(bundle, public, expected)["run_id"] == result["run_id"]


@pytest.mark.parametrize("case", ["good-88d4b8780666", "regression-657db9dc5f0e", "timeout-4f515ea83d60"])
def test_signed_patchreplay_subject_does_not_mean_test_success(tmp_path, signing_keys, case):
    subject = ROOT / "examples/container-evidence" / case
    expected, bundle = tmp_path / "expected.json", tmp_path / "bundle"
    data = core.prepare(subject, "patchreplay-v1", expected)
    assert data["bindings"]["patch_sha256"] and data["bindings"]["source_revision"]
    private, public = signing_keys
    core.sign(subject, expected, private, PASSWORD, bundle)
    result = core.verify(bundle, public, expected)
    assert result["status"] == "AUTHENTICATED_FOR_EXPECTED_SUBJECT"
    assert json.loads((bundle / "artifacts/report.json").read_text())["status"] != result["status"]


@pytest.mark.parametrize("change", ["edit", "remove", "add", "raw-reformat", "extra-root"])
def test_artifact_changes_are_rejected(signed, change):
    _, expected, bundle, _, public = signed
    artifact = bundle / "artifacts/results.json"
    if change == "edit":
        artifact.write_text("{}")
    elif change == "remove":
        artifact.unlink()
    elif change == "add":
        (bundle / "artifacts/extra").write_text("extra")
    elif change == "raw-reformat":
        artifact.write_bytes(artifact.read_bytes() + b"\n")
    else:
        (bundle / "trusted-key.pem").write_bytes(public.read_bytes())
    with pytest.raises((ValueError, OSError, KeyError)):
        core.verify(bundle, public, expected)


@pytest.mark.parametrize("change", ["signature", "algorithm", "key_id", "signed_at", "extra", "missing", "run", "engine"])
def test_envelope_changes_are_rejected(signed, change):
    _, expected, bundle, _, public = signed
    path = bundle / "attestation.json"
    data = core.load(path)
    statement = data["statement"]
    if change == "signature":
        raw = bytearray(base64.b64decode(data["signature"]))
        raw[0] ^= 1
        data["signature"] = base64.b64encode(raw).decode()
    elif change == "algorithm":
        statement["algorithm"] = "none"
    elif change == "key_id":
        statement["key_id"] = "sha256:" + "0" * 64
    elif change == "signed_at":
        statement["signed_at"] = "2000-01-01T00:00:00Z"
    elif change == "extra":
        data["public_key"] = public.read_text()
    elif change == "missing":
        del statement["subject"]["bindings"]["image"]
    elif change == "run":
        statement["subject"]["run_id"] = "another-run"
    else:
        statement["subject"]["bindings"]["engine_sha256"] = "0" * 64
    rewrite(path, data)
    with pytest.raises(ValueError):
        core.verify(bundle, public, expected)


def test_unknown_signer_cannot_replace_key_or_claim_trusted_key_id(signed, tmp_path):
    subject, expected, _, _, public = signed
    attacker_private, attacker_public = tmp_path / "other-private.pem", tmp_path / "other-public.pem"
    core.keygen(attacker_private, attacker_public, PASSWORD)
    attacker_bundle = tmp_path / "attacker-bundle"
    core.sign(subject, expected, attacker_private, PASSWORD, attacker_bundle)
    with pytest.raises(ValueError, match="trusted"):
        core.verify(attacker_bundle, public, expected)
    data = core.load(attacker_bundle / "attestation.json")
    data["statement"]["key_id"] = core.key_id(serialization.load_pem_public_key(public.read_bytes()))
    key = serialization.load_pem_private_key(attacker_private.read_bytes(), PASSWORD)
    data["signature"] = base64.b64encode(key.sign(core.DOMAIN + canonical(data["statement"]))).decode()
    rewrite(attacker_bundle / "attestation.json", data)
    with pytest.raises(ValueError, match="Invalid signature"):
        core.verify(attacker_bundle, public, expected)


def test_valid_signed_other_round_is_rejected(tmp_path, signing_keys):
    private, public = signing_keys
    roots = [ROOT / "examples/container-evidence" / case for case in ("good-88d4b8780666", "regression-657db9dc5f0e")]
    expected = [tmp_path / f"expected-{i}.json" for i in range(2)]
    for root, path in zip(roots, expected):
        core.prepare(root, "patchreplay-v1", path)
    bundle = tmp_path / "round-two"
    core.sign(roots[1], expected[1], private, PASSWORD, bundle)
    assert core.verify(bundle, public, expected[1])["status"] == "AUTHENTICATED_FOR_EXPECTED_SUBJECT"
    with pytest.raises(ValueError, match="externally expected"):
        core.verify(bundle, public, expected[0])


def test_rehashed_artifact_and_resigned_bundle_still_need_external_expectation(signed):
    _, expected, bundle, private, public = signed
    artifact = bundle / "artifacts/README.md"
    artifact.write_text("Replacement prose")
    envelope = core.load(bundle / "attestation.json")
    envelope["statement"]["subject"]["artifacts"]["README.md"] = digest(artifact.read_bytes())
    key = serialization.load_pem_private_key(private.read_bytes(), PASSWORD)
    envelope["signature"] = base64.b64encode(key.sign(core.DOMAIN + canonical(envelope["statement"]))).decode()
    rewrite(bundle / "attestation.json", envelope)
    with pytest.raises(ValueError, match="externally expected"):
        core.verify(bundle, public, expected)


@pytest.mark.parametrize("trust_input", ["key", "expectation"])
def test_bundle_cannot_supply_its_own_trust(signed, trust_input):
    _, expected, bundle, _, public = signed
    path = bundle / "artifacts" / ("key.pem" if trust_input == "key" else "expected.json")
    shutil.copyfile(public if trust_input == "key" else expected, path)
    with pytest.raises(ValueError, match="outside"):
        core.verify(bundle, path if trust_input == "key" else public, path if trust_input == "expectation" else expected)


def test_sign_refuses_input_drift_and_keeps_partial_output_unsigned(signed, tmp_path):
    subject, expected, _, private, public = signed
    (subject / "README.md").write_text("changed since review")
    out = tmp_path / "changed"
    with pytest.raises(ValueError, match="externally expected"):
        core.sign(subject, expected, private, PASSWORD, out)
    assert not (out / "attestation.json").exists()
    with pytest.raises(ValueError):
        core.verify(out, public, expected)


def test_key_material_cannot_be_bundled(signed, tmp_path):
    subject, expected, _, private, _ = signed
    inside = subject / "private.pem"
    shutil.copyfile(private, inside)
    with pytest.raises(ValueError, match="outside"):
        core.sign(subject, expected, inside, PASSWORD, tmp_path / "bad")
    with pytest.raises(ValueError, match="Private key"):
        core.prepare(subject, "observer-v1", tmp_path / "leaked-expectation.json")


def test_wrong_password_and_unencrypted_key_rejected(signed, tmp_path):
    subject, expected, _, private, _ = signed
    with pytest.raises(ValueError):
        core.sign(subject, expected, private, b"wrong-password-long-enough", tmp_path / "wrong")
    unencrypted = tmp_path / "unencrypted.pem"
    unencrypted.write_bytes(Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    with pytest.raises(ValueError, match="encrypted PKCS8"):
        core.sign(subject, expected, unencrypted, PASSWORD, tmp_path / "unsafe")


def test_keygen_never_overwrites(signing_keys, tmp_path):
    private, public = signing_keys
    before = private.read_bytes()
    with pytest.raises(ValueError):
        core.keygen(private, public, PASSWORD)
    assert private.read_bytes() == before
    with pytest.raises(ValueError):
        core.keygen(tmp_path / "one", tmp_path / "two", b"short")


def test_offline_verify_never_executes_artifact_or_network(signed, monkeypatch):
    _, expected, bundle, _, public = signed
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline verification must not launch a process or use a socket")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    assert core.verify(bundle, public, expected)["status"] == "AUTHENTICATED_FOR_EXPECTED_SUBJECT"


def test_signature_from_another_protocol_is_rejected(signed):
    _, expected, bundle, private, public = signed
    envelope = core.load(bundle / "attestation.json")
    key = serialization.load_pem_private_key(private.read_bytes(), PASSWORD)
    envelope["signature"] = base64.b64encode(key.sign(canonical(envelope["statement"]))).decode()
    rewrite(bundle / "attestation.json", envelope)
    with pytest.raises(ValueError, match="Invalid signature"):
        core.verify(bundle, public, expected)


@pytest.mark.parametrize("value", [b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b'\xff'])
def test_ambiguous_metadata_rejected(value):
    with pytest.raises(ValueError):
        core.parse(value)


def test_traversal_and_symlinks_rejected(signed, tmp_path):
    _, expected, bundle, _, public = signed
    value = core.load(expected)
    value["artifacts"]["../outside"] = "0" * 64
    with pytest.raises(ValueError):
        core.validate_expected(value)
    link = bundle / "artifacts" / "link"
    try:
        link.symlink_to(public)
    except OSError:
        pytest.skip("Creating symlinks requires privileges")
    with pytest.raises(ValueError):
        core.verify(bundle, public, expected)


def test_oversized_file_rejected(tmp_path):
    path = tmp_path / "large"
    path.write_bytes(b"x" * (core.MAX_FILE + 1))
    with pytest.raises(ValueError, match="size"):
        core.inventory(tmp_path)


def test_artifact_count_budget_rejected(tmp_path):
    for i in range(core.MAX_FILES + 1):
        (tmp_path / str(i)).write_bytes(b"")
    with pytest.raises(ValueError, match="budget"):
        core.inventory(tmp_path)


def test_duplicate_observer_round_is_not_signable(signed, tmp_path):
    subject, _, _, _, _ = signed
    report = core.load(subject / "results.json")
    report["observations"][1]["request"]["request_id"] = report["observations"][0]["request"]["request_id"]
    rewrite(subject / "results.json", report)
    with pytest.raises(ValueError, match="duplicated"):
        core.prepare(subject, "observer-v1", tmp_path / "bad-expectation.json")


def test_cli_end_to_end_and_failure_exit_codes(tmp_path, monkeypatch, capsys):
    private, public = tmp_path / "secret.pem", tmp_path / "public.pem"
    expected, bundle = tmp_path / "expected.json", tmp_path / "bundle"
    monkeypatch.setenv("PATCHREPLAY_TEST_PASSWORD", PASSWORD.decode())
    assert main(["keygen", "--private-key", str(private), "--public-key", str(public),
                 "--password-env", "PATCHREPLAY_TEST_PASSWORD"]) == 0
    assert main(["prepare", "--subject", str(ROOT / "examples/observer-evidence"), "--kind", "observer-v1",
                 "--output", str(expected)]) == 0
    assert main(["sign", "--subject", str(ROOT / "examples/observer-evidence"), "--expectation", str(expected),
                 "--private-key", str(private), "--password-env", "PATCHREPLAY_TEST_PASSWORD", "--output", str(bundle)]) == 0
    verify_args = ["verify", "--bundle", str(bundle), "--trusted-key", str(public), "--expectation", str(expected)]
    assert main(verify_args) == 0
    (bundle / "artifacts/README.md").write_text("changed")
    assert main(verify_args) == 1
    assert PASSWORD.decode() not in capsys.readouterr().out
