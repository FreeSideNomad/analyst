---
layout: default
title: Administration
---

# Administration

[← Manual home](index.html)

## Data governance — what leaves the box, and what never does

analyst is built around one invariant: **raw bulk data never leaves your
machine.**

| Stays local, always | May cross to the LLM (only with `ANTHROPIC_API_KEY`) |
|---|---|
| Your files, the Parquet/DuckDB store | Table/column names and profiles (types, null rates, cardinalities) |
| Connected databases (queried read-only, in place) | A few sample values per column (capped) |
| SQL execution (DuckDB, in the container) | Small final result sets, for summarising an answer |
| Credentials (encrypted at rest) | Catalog descriptions and the relationship graph |

Every model call goes through a single gateway that caps samples and logs
egress. Without an API key the LLM features are simply off — ingestion,
profiling, cataloguing, and relationship discovery are fully local.

## Users & workspaces

Configure Google or Microsoft OAuth ([Getting started](getting-started.html))
and the **first user to sign in becomes the admin**, who creates workspaces
and assigns members. Each workspace is fully isolated — its own datasets,
catalog, connections, and credentials. Without OAuth configured the app runs
open (single-tenant), suitable for a trusted network or a laptop.

## Credential storage

Database credentials are persisted **only** when you supply the operator key
(`ANALYST_SECRET_KEY_FILE`, ideally a Docker secret). They are sealed with
authenticated encryption (Fernet); the key never touches the data volume;
wrong key / tampered records fail safe to re-entry — there is no plaintext
fallback, ever. Rotating the key currently means re-entering connections
(managed-KMS support and rotation are on the roadmap).

## Backups & upgrades

- **Back up** the `/data` volume (and your key file, separately).
- **Upgrade** by pulling the new image and recreating the container — state
  lives in the volume:

```bash
docker pull ghcr.io/freesidenomad/analyst:latest
docker stop analyst && docker rm analyst
docker run -d --name analyst -p 8000:8000 -v analyst-data:/data ... \
  ghcr.io/freesidenomad/analyst:latest
```

- Image tags: `latest` (main), `sha-<commit>` (every build), `vX.Y.Z`
  (releases).

## Health

`GET /api/health` returns `{"ok": true, ...}` — the image ships a Docker
`HEALTHCHECK` wired to it.
