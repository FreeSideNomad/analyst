# Deployment hardening runbook

> Operator checklist for running `analyst` safely. The application-level fixes
> from the 2026-07-04 security review are in the code; this covers the
> **deployment posture** that the app can't enforce itself, plus the items that
> are inherently deployment concerns.

## Required for any real (multi-user / networked) deployment

- [ ] **Set `ANALYST_SESSION_SECRET`** to a long random value (M2). Without it,
      sessions use a per-process random key — they break across multiple workers
      and reset on restart. The app logs a warning when this is missing.
- [ ] **Serve over TLS** and do **not** set `ANALYST_INSECURE_COOKIES=1` (H1) —
      the session cookie is `Secure` by default; the opt-out is for local http
      dev/e2e only.
- [ ] **Set `ANALYST_PUBLIC_URL`** to the deployment origin — pins CORS to it
      (low: credentials aren't enabled, but pin anyway) and fixes the OAuth
      redirect URI instead of deriving it from the `Host` header.
- [ ] **Run a single worker**, or share `ANALYST_SESSION_SECRET` across workers
      (the app SQLite state is shared; the admin-race is DB-guarded, M2).
- [ ] **OAuth credentials** (if used): see `features/004-auth-workspaces/runbook.md`.

## Container hardening — the OS sandbox (defense-in-depth for M5/M6 + C2)

The SQL guard (C2) already blocks the app from reading arbitrary files via SQL,
and connections attach read-only. The **OS sandbox is the belt-and-suspenders**:
even a hypothetical future bypass can then only touch the workspace data dir.

- [ ] Run the process as a **non-root user**.
- [ ] Mount the root filesystem **read-only**; make **only `ANALYST_DATA_DIR`
      writable** (a dedicated volume).
- [ ] `--cap-drop=ALL` (no Linux capabilities needed).
- [ ] Keep secrets (`ANALYST_SESSION_SECRET`, OAuth secrets, DB passwords) out of
      the image — inject via env / a secrets store, never bake them in.
- [ ] Do **not** co-locate sensitive files (e.g. cloud creds) on the same
      filesystem the process can read.

### Connection egress (M5/M6 — inherent to "connect any database")
Connecting a database means the app opens an outbound connection to a
user-supplied `host:port` (or a SQLite `path`). This is an SSRF / internal
port-scan / arbitrary-local-file surface **by design** — the real mitigation is
network policy, not a code block-list:

- [ ] Put the container on a **network with egress rules** that only allow the
      database hosts it should reach (deny link-local/metadata endpoints,
      internal services).
- [ ] For SQLite-by-path connections, the read-only FS above bounds which files
      can be opened. Consider disabling the SQLite-path connector entirely in
      multi-tenant deployments (`ANALYST_ALLOW_SQLITE_PATH=0` — future flag).

## Data-source licensing (feature 005)

- **PostgreSQL / SQL Server** — connectable with fully open-source drivers.
- **IBM DB2** — `ibm_db` (Apache-2.0 wrapper) over IBM's proprietary-but-free CLI
  driver. **Free for Db2 LUW**; **licensed (not free) for Db2 z/OS and Db2 for i
  (AS/400)** — those need a Db2 Connect license. See
  `features/003-nl-qa/DESIGN.md` §2.

## Known limitations (documented, not defects)

- **NL Q&A over connected-DB tables is not implemented yet.** Connected databases
  are profiled and catalogued, but asking questions *about* their tables is the
  phased federation work — features **007** (within-DB) and **008** (files×DB),
  designed in `features/003-nl-qa/DESIGN.md`. (The earlier "overlay" approach was
  dropped in favor of the safer "always remotely" template design.)
- **Concurrency**: the store serializes its DuckDB connection (M4); this is a
  single-node team tool, not a high-concurrency service.
