---
slug: credential-storage
checkpoint: 4
plan_status: approved
created: 2026-07-05
---

# Plan — Feature 011: Encrypted-at-rest credentials

> Checkpoint 4. Human pre-approved autonomous CP3-CP5 at AC approval
> (2026-07-05, "Approve — build it").

## Architecture

### The vault (engine layer, new `src/analyst/engine/credentials.py`)

- `load_operator_key() -> str | None` — the operator passphrase from
  `ANALYST_SECRET_KEY` (env) or `ANALYST_SECRET_KEY_FILE` (a path, the Docker
  secret default: `/run/secrets/analyst_secret_key`). Missing/empty → `None`
  (the fail-safe: no key, no persistence). Distinct from
  `ANALYST_SESSION_SECRET` (auth.py precedent for env-supplied secrets).
- `CredentialVault(passphrase)` — derives a Fernet key (urlsafe-b64 SHA-256
  of the passphrase) and offers `seal(ConnectionSpec) -> str` /
  `open(token) -> ConnectionSpec`. Fernet = AES-128-CBC + HMAC (authenticated),
  from the `cryptography` package (now an explicit dependency). A wrong key or
  tampered token raises `VaultError` — callers treat the record as absent,
  NEVER fall back to plaintext (AC-7/AC-9).
- `VaultStore(base_dir)` — one file per workspace,
  `<workspace_dir>/connections.vault.json`, mapping connection name →
  ciphertext token. Put on connect, remove on detach. The key is never
  written anywhere under `base_dir` (AC-3); ciphertext-only at rest (AC-8).

### Persist on connect / forget on detach (manager)

`DatabaseManager` gains an optional `vault: CredentialVault | None` and
resolves the workspace's `VaultStore` from `repo.store.base_dir` (getattr —
`FixtureRepository` has no store, so fixtures never persist, mirroring the
010 hooks). On successful `connect`, seal + put (AC-1); on `detach`, remove
(AC-5). With `vault=None` (no operator key) nothing persists and nothing else
changes (AC-6).

### Reconnect on first workspace access

Managers are created lazily per workspace repo (`get_manager`). Right after
creation, `restore_persisted()` runs: for each stored (name, token) —

1. `vault.open(token)` → on `VaultError` (changed/absent key, tamper) the
   record is *ignored this session* (kept on disk: restoring the right key
   later revives it) and the connection simply requires re-entry (AC-7/AC-9).
2. `connect(spec)` through the normal path — so the feature-010 persisted
   catalog is reused and descriptions appear immediately (AC-2), and the
   feature-007 attach makes tables queryable.
3. A `FederationError` (database down) registers the spec in an in-memory
   `unreachable` map instead: the connection is listed with
   `status: "unreachable"`, its dataset records are restored from the 010
   sidecars (catalog visible), and `reconnect(name)` retries with the
   remembered spec — no re-entry (AC-4).

From the user's view this is "back after restart": the reconnect happens
before the workspace's first listing is answered.

### Wire + frontend (minimal)

- `DatabaseSchema` gains `status: "connected" | "unreachable"`; no password
  field anywhere, as before (AC-10) — reconnect logging goes through the
  existing `_redact_secrets`.
- New route `POST /api/databases/{name}/reconnect` → retry an unreachable
  connection.
- Frontend: the connect form gains the read-only-account guidance (AC-12)
  and the databases list shows an unreachable badge + retry.

### Alternatives considered

- *Encrypt with the session secret* — rejected: different lifecycle and
  rotation story; a web-session key must not unlock data at rest.
- *OS keyring* — rejected: headless Docker target; Docker secrets are the
  native mechanism.
- *Random Fernet key required verbatim* — rejected: forcing operators to
  generate exact 32-byte urlsafe keys invites error; KDF from any passphrase
  is strictly friendlier and no weaker for this threat model.
- *Reconnect eagerly at process boot* — rejected: workspaces (and their
  repos) are lazy; connecting every workspace's databases at boot does work
  nobody may ask for and needs auth context that doesn't exist yet.

## Charter Check

| Charter rule | Status | Note |
|---|---|---|
| Layered architecture | ✅ | Vault in engine; manager wiring in api; ConnectionSpec stays domain. |
| Governance: raw bulk data never leaves the box; secrets never in clear on disk | ✅ | Only credentials are sealed+persisted; ciphertext-only at rest; key outside the store; wire/logs redacted (AC-8/10). |
| Acceptance pipeline; never hand-edit generated | ✅ | 15-scenario board via `acceptance.ctx011`. |
| TDD, unit + acceptance green before merge | ✅ | Slice order below; every test red first. |
| Determinism of offline paths | ✅ | No LLM in this feature; Fernet tokens are non-deterministic but never asserted byte-wise. |
| Autonomy stance + validation method | ✅ | Human delegated CP3-CP5; validation_method (round-trip, fail-safe, at-rest scan, live restart) mapped to tests below. |

No deviations → no amendments.

## Phasing

1. **Vault** (AC-3, 7, 8, 9): key sources, seal/open round-trip, wrong-key /
   tamper fail-safe, VaultStore file.
2. **Persist + reconnect** (AC-1, 2, 5, 6, 10, 11): manager wiring, restore
   on first access, detach-forgets, no-key unchanged, wire/log redaction,
   workspace isolation.
3. **Degraded + guidance** (AC-4, 12): unreachable status + retry route +
   frontend badge/retry + read-only hint.

## Performance budgets

- Vault ops are sub-millisecond; the vault file is tiny JSON.
- Reconnect cost = the same connects the user would have re-typed, paid once
  per workspace activation; 010 catalog reuse avoids re-cataloguing.

## Test strategy

Per `feature.md.validation_method`: unit round-trip seal/open; wrong/absent
key fails safe (no plaintext fallback, connection inert); ciphertext-at-rest
contains no plaintext secret; egress/logs redacted; a **live-marked** test:
connect (Postgres pagila) → restart → auto-reconnect with the key present.
Existing boards stay green. Acceptance: the 15-scenario board in-process
with a password-bearing SQLite spec.

## Collaboration schedule / execution modes

Single local agent through CP5 (delegation recorded); human returns at PR.
Operator steps in `runbook.md` (Docker secret mount) — documentation only,
nothing blocks local validation.
