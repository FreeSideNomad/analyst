---
ac_count: 12
high_priority_count: 7
discovered: 2026-07-05
---

# Acceptance Criteria — Feature 011: Encrypted-at-rest credentials

> Formalized from `feature.md` (design confirmed 2026-07-05) + the human's four
> scoping decisions of 2026-07-05: **rotation deferred to phase 2**, **one
> operator key for the whole app**, **unreachable-at-restart connections stay
> visible and retryable**, **persistence is automatic** for every connection.
> Domain language; crypto/reconnect behaviors bind to unit tests, the
> restart journey to the in-process seam, live DBs via the live marker.

## Seamless reconnect (happy path)

### AC-1: A connection's credentials are remembered automatically
Priority: High · Type: Functional
When the operator key is configured, connecting a database automatically
seals its credentials and persists them — no extra step, consistent with
"autopilot by default". Nothing else about connecting changes.

### AC-2: After a restart the connection is back without re-entering anything
Priority: High · Type: Functional
After the service restarts (key present), a previously connected database is
available in its workspace again — listed, queryable, and showing its
previously derived catalog immediately (reusing the feature-010 persisted
meaning, not re-deriving it). The user never re-enters credentials.

### AC-3: The key is supplied by the operator, outside the stored data
Priority: High · Type: Functional
The sealing key comes from the operator at start-up — a Docker-secret file
path or an environment variable — and is never written into the workspace
store alongside the ciphertext. It is distinct from the session secret.

## Degraded states (edge)

### AC-4: An unreachable database stays visible and retryable
Priority: Medium · Type: Functional
If the key is present but a remembered database cannot be reached when the
service comes back, the connection appears in the workspace marked
unreachable, still showing its persisted catalog; a retry re-attaches it
without re-entering credentials.

### AC-5: Detaching forgets the stored credentials
Priority: Medium · Type: Functional
Detaching a connection removes its persisted credentials; after a restart it
does not reappear.

### AC-6: Without a key, nothing persists — and the app still works
Priority: High · Type: Functional
With no operator key configured, connections behave exactly as today:
usable for the session, credentials never written to disk, gone after a
restart (re-entry required). No error, no degradation of anything else.

## Errors & security

### AC-7: A missing or changed key fails safe to re-entry
Priority: High · Type: Security
If the key is absent, wrong, or has been changed (rotation is phase 2),
previously stored credentials are unusable: the connections simply require
re-entry. There is NEVER a plaintext fallback, and the service starts
normally.

### AC-8: The data at rest yields no secret
Priority: High · Type: Security
What is persisted is authenticated ciphertext: inspecting the disk (or the
workspace store) without the key reveals no password or connection secret.

### AC-9: Tampered ciphertext is rejected, not decrypted
Priority: Medium · Type: Security
A modified/corrupted credential record fails authentication and is treated
as absent (re-entry required) — never partially decrypted, never a crash.

### AC-10: Secrets stay off the wire and out of logs — including the new path
Priority: High · Type: Constraint
The existing invariant extends to persistence and reconnect: no response
carries a password field, reconnect/failure logs are redacted, and the
sealed record is never echoed through the API.

## Cross-cutting

### AC-11: One key, per-workspace data, intact isolation
Priority: Medium · Type: Constraint
A single app-wide operator key seals every workspace's credentials, but the
ciphertext lives with its workspace and reconnect restores each connection
only into its own workspace — workspace isolation is unchanged.

### AC-12: Least-privilege guidance
Priority: Low · Type: Functional
Where credentials are entered, the user is guided to prefer a read-only
database account (the analyst only ever reads).
