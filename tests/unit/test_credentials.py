"""Feature 011 — the credential vault: seal/open, fail-safe, key sources."""

from __future__ import annotations

import json

import pytest

from analyst.domain.connection import ConnectionSpec, DatabaseEngine
from analyst.engine.credentials import (
    CredentialVault,
    VaultError,
    VaultStore,
    load_operator_key,
)

SPEC = ConnectionSpec(
    name="crm",
    engine=DatabaseEngine.POSTGRES,
    host="db.internal",
    port=5544,
    database="pagila",
    user="reader",
    password="s3cret-pw",
)


def test_seal_open_round_trip():
    vault = CredentialVault("passphrase-1")
    token = vault.seal(SPEC)
    assert vault.open(token) == SPEC


def test_token_is_not_plaintext():
    token = CredentialVault("passphrase-1").seal(SPEC)
    assert "s3cret-pw" not in token
    assert "reader" not in token


def test_wrong_key_fails_safe():
    token = CredentialVault("passphrase-1").seal(SPEC)
    with pytest.raises(VaultError):
        CredentialVault("passphrase-2").open(token)


def test_tampered_token_is_rejected():
    token = CredentialVault("passphrase-1").seal(SPEC)
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(VaultError):
        CredentialVault("passphrase-1").open(tampered)


def test_garbage_token_is_rejected():
    with pytest.raises(VaultError):
        CredentialVault("passphrase-1").open("not a token at all")


def test_operator_key_from_environment(monkeypatch):
    monkeypatch.delenv("ANALYST_SECRET_KEY_FILE", raising=False)
    monkeypatch.setenv("ANALYST_SECRET_KEY", "from-env")
    assert load_operator_key() == "from-env"


def test_operator_key_from_secret_file(tmp_path, monkeypatch):
    secret = tmp_path / "analyst_secret_key"
    secret.write_text("from-file\n", encoding="utf-8")
    monkeypatch.delenv("ANALYST_SECRET_KEY", raising=False)
    monkeypatch.setenv("ANALYST_SECRET_KEY_FILE", str(secret))
    assert load_operator_key() == "from-file"


def test_no_operator_key_configured(monkeypatch):
    monkeypatch.delenv("ANALYST_SECRET_KEY", raising=False)
    monkeypatch.delenv("ANALYST_SECRET_KEY_FILE", raising=False)
    assert load_operator_key() is None


def test_missing_secret_file_is_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYST_SECRET_KEY", raising=False)
    monkeypatch.setenv("ANALYST_SECRET_KEY_FILE", str(tmp_path / "nope"))
    assert load_operator_key() is None


def test_vault_store_put_remove_roundtrip(tmp_path):
    store = VaultStore(tmp_path)
    vault = CredentialVault("passphrase-1")
    store.put("crm", vault.seal(SPEC))
    assert set(VaultStore(tmp_path).all()) == {"crm"}
    assert vault.open(VaultStore(tmp_path).all()["crm"]) == SPEC
    store.remove("crm")
    assert VaultStore(tmp_path).all() == {}


def test_vault_store_file_has_no_plaintext(tmp_path):
    store = VaultStore(tmp_path)
    store.put("crm", CredentialVault("passphrase-1").seal(SPEC))
    (path,) = tmp_path.glob("*.vault.json")
    raw = path.read_text(encoding="utf-8")
    assert "s3cret-pw" not in raw
    json.loads(raw)  # stays plain JSON, just with sealed values
