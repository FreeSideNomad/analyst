---
slug: credential-storage
title: Encrypted-at-rest database credentials with seamless reconnect
outcome: A connected database's credentials can be persisted ENCRYPTED AT REST so the app reconnects automatically after a restart — without weakening the "raw data never leaves the box, secrets never hit disk in the clear" posture. Credentials are sealed with authenticated encryption under an OPERATOR-SUPPLIED key that lives outside the store (a Docker secret by default); if the key is absent the connections stay inert and the user re-enters. Read-only DB accounts are encouraged (the app only ever runs SELECT). A pluggable backend allows a real secrets manager (Vault / cloud KMS) later; the env/Docker-secret key is the default.
status: done
autonomy_level: high
assignee: local
owner: igormusic
area: security
tracker_ref: local://credential-storage
branch: credential-storage
validation_method: "Unit tests: round-trip seal/open; wrong/absent key fails safe (no plaintext fallback, connection inert); ciphertext-at-rest contains no plaintext secret; egress/logs still redacted. A live-marked test: connect → restart → auto-reconnect with the key present. Existing boards stay green."
size: M
created: 2026-07-05
---

# Feature 011 — Encrypted-at-rest credentials (seamless reconnect)

> From the design discussion of 2026-07-05. Today connection secrets live only
> in the in-process `ConnectionSpec` and are NEVER written to disk — the most
> secure option, but a restart loses the connection (re-enter credentials).
> Feature 010 persists a connected DB's *catalog* (metadata); this persists the
> *credentials* — encrypted — so reconnect is automatic. Human decision:
> **Docker-secret env key as the default**, KMS-pluggable later.

## Design (confirmed)
- **Authenticated encryption at rest** — seal the `ConnectionSpec` secret with a
  vetted AEAD (Fernet: AES-128-CBC + HMAC). Ciphertext stored per-workspace in
  the app store; **the key is never stored with it**.
- **Operator-supplied key, outside the store** — default: a **Docker secret**
  mounted at `/run/secrets/…` (or a file path / `ANALYST_SECRET_KEY` env),
  supplied at container start. Distinct from `ANALYST_SESSION_SECRET`.
- **Fail safe** — no key (or wrong key) → connections stay inert and require
  re-entry; NEVER a silent plaintext fallback.
- **Auto-reconnect on boot** — with the key present, persisted connections are
  decrypted and re-attached (data path via feature 007); their catalog (010) is
  reused, so meaning is not re-derived.
- **Least privilege** — surface guidance/expectation of read-only DB accounts
  (the engine only issues SELECT).
- **Never logged, never returned** — the existing `_redact_secrets` bound holds;
  the wire has no password field (feature 005 invariant).
- **Pluggable backend** — a seam so Vault / AWS Secrets Manager / cloud KMS can
  supply/wrap the key (envelope encryption) for teams that have one; the
  env/Docker-secret key is the default and needs no infra.

## Governance
- Only credentials are sealed and persisted; **no bulk data** is persisted (the
  standing invariant). Disk-without-key must not yield the secret.

## Dependencies / phasing
- Builds on 005 (`ConnectionSpec`/federation), 007 (attach-for-query on
  reconnect), 010 (reuse the persisted DB catalog on reconnect).
- Phase 1: Fernet + Docker-secret/env key + fail-safe + auto-reconnect.
- Phase 2 (separate): pluggable KMS/Vault backend + key rotation.

## Open questions (resolve in discover-acs)
- Key rotation / re-encryption flow in v1, or phase 2?
- Per-workspace key vs. one app key for all workspaces?
