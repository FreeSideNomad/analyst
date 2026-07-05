"""Credential vault (feature 011) — encrypted-at-rest connection secrets.

Seals a ``ConnectionSpec`` with authenticated encryption (Fernet:
AES-128-CBC + HMAC) under an OPERATOR-SUPPLIED passphrase that lives outside
the workspace store — ``ANALYST_SECRET_KEY`` (env) or
``ANALYST_SECRET_KEY_FILE`` (a mounted Docker secret). No key → no
persistence; a wrong key or tampered token raises ``VaultError`` and the
caller treats the record as absent. There is NEVER a plaintext fallback.

Ciphertext lives per workspace in ``connections.vault.json`` (name → token).
The key is never written under the store.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from analyst.domain.connection import ConnectionSpec, DatabaseEngine

_VAULT_FILE = "connections.vault.json"


class VaultError(RuntimeError):
    """A sealed record could not be opened (wrong key, tampered, garbage)."""


def load_operator_key() -> str | None:
    """The operator passphrase, or None (fail-safe: no key, no persistence).

    ``ANALYST_SECRET_KEY`` wins; else ``ANALYST_SECRET_KEY_FILE`` names a file
    (the Docker-secret mount). A missing/unreadable file is treated as no key
    — the service must start normally either way.
    """
    direct = os.environ.get("ANALYST_SECRET_KEY", "").strip()
    if direct:
        return direct
    path = os.environ.get("ANALYST_SECRET_KEY_FILE", "").strip()
    if not path:
        return None
    try:
        content = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return content or None


class CredentialVault:
    """Seal/open ConnectionSpecs under a passphrase-derived Fernet key."""

    def __init__(self, passphrase: str):
        digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def seal(self, spec: ConnectionSpec) -> str:
        payload = dataclasses.asdict(spec)
        payload["engine"] = spec.engine.value
        return self._fernet.encrypt(json.dumps(payload).encode("utf-8")).decode("ascii")

    def open(self, token: str) -> ConnectionSpec:
        try:
            raw = self._fernet.decrypt(token.encode("ascii"))
        except (InvalidToken, ValueError, TypeError) as exc:
            raise VaultError(
                "The stored credentials could not be opened with the configured "
                "key — re-enter the connection's credentials."
            ) from exc
        data = json.loads(raw.decode("utf-8"))
        data["engine"] = DatabaseEngine(data["engine"])
        return ConnectionSpec(**data)


class VaultStore:
    """The per-workspace ciphertext file: connection name → sealed token."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self._path = Path(str(base_dir)) / _VAULT_FILE

    def all(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            return {}
        return {str(k): str(v) for k, v in data.items()}

    def put(self, name: str, token: str) -> None:
        data = self.all()
        data[name] = token
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data), encoding="utf-8")

    def remove(self, name: str) -> None:
        data = self.all()
        if data.pop(name, None) is not None:
            self._path.write_text(json.dumps(data), encoding="utf-8")
