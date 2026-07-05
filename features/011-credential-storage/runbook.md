# Runbook — Feature 011: operator key for credential storage

Credential persistence is OFF until the operator supplies a key. Without it,
the app runs exactly as before (connections are session-only). These steps
are for the deployment host.

## Enable encrypted credential persistence (Docker secret — recommended)

- [ ] human — Generate a strong passphrase (any string; 32+ random chars
      recommended).
      command: `openssl rand -base64 32 > analyst_secret_key.txt`
      evidence: the file exists and is NOT committed anywhere.
- [ ] human — Supply it as a Docker secret / mounted file.
      command: `docker run ... -v $(pwd)/analyst_secret_key.txt:/run/secrets/analyst_secret_key:ro -e ANALYST_SECRET_KEY_FILE=/run/secrets/analyst_secret_key ...`
      evidence: container env has `ANALYST_SECRET_KEY_FILE`; the file is readable in-container.
- [ ] human — (alternative, simpler, weaker) pass the passphrase directly:
      `-e ANALYST_SECRET_KEY=<passphrase>`.

## Notes

- Keep the passphrase OUTSIDE the data volume. Losing it means stored
  connections require re-entry (by design — there is no recovery path).
- Changing the passphrase invalidates stored credentials (rotation /
  re-encryption is phase 2, with the KMS backend); users simply re-enter.
- Use a READ-ONLY database account for connections — the analyst only reads.
- `ANALYST_SECRET_KEY(_FILE)` is distinct from `ANALYST_SESSION_SECRET`
  (web-session signing); set both in production.
