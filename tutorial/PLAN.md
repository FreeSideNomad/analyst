# Tutorial plan (maintainers)

**Audience**: a new user with **Docker and a browser only** — no git, no
make, no uv. Everything they run is either a UI action or a copy-paste
`docker compose` command; everything they download comes from the Pages
site itself.

**Voice rules** (owner-set, 2026-07-19):

- Guide voice, not tester voice: each step is *action → what you'll see
  → why it matters to you*. Never "Expected:", never "verify".
- No feature numbers, no AC/board/test vocabulary anywhere on Pages.
- Product vocabulary (catalog, receipts/trust trail) introduced plainly
  at first use; engineering vocabulary replaced by its meaning
  ("checked that every purchase's customer exists", "trained on
  scrambled outcomes must score a coin flip").
- Part 1 (no AI key) before Part 2 (key) — value before friction.

## Delivery

- `tutorial/pages/` → copied to Pages at build (with `tutorial/files/`
  and `docker-compose.yml`); single source of truth here.
- `tutorial/files/` — committed sample files, downloaded per-step
  (`make files` regenerates the set).
- `tutorial/docker-compose.yml` — the user stack: app (ghcr latest),
  profiles `databases` (three pre-seeded Postgres images) and `ml`
  (ghcr `:ml` image).
- Pre-seeded DB images built by `.github/workflows/tutorial-images.yml`
  (seed scripts → pg_dump → initdb bake): `analyst-tutorial-berka`,
  `analyst-tutorial-crm`, `analyst-tutorial-billing`.
- `analyst:ml` published by the docker workflow (amd64 — pyg-lib wheel
  matrix).
- The Makefile here is the **contributor** path (build from source,
  local seeds); the published tutorial never references it.

## Chapter ↔ acceptance-criteria map (internal only — never published)

| Page | Features exercised | Happy-path moments |
|---|---|---|
| 01-first-data | 001, 006, 009, 010, 013 | messy ingest+profile; Excel; catalog text (no-AI banner); FK discovered & RI-validated; retroactive workspace awareness; normalization propose→approve→revoke |
| 02-databases | 005, 011, 009 | connect Postgres in place; declared+inferred links; cross-connection link (crm↔billing); encrypted-credential restart survival |
| key | governance | capped-egress explanation (schema/profiles/samples/results only) |
| 03-ask | 003, 017, 016, 014, 015 | answer+trust trail; clarification; abstention; save chart (re-runs live); save as dataset; CSV/Excel export; cross-DB question (150/50 check); curation answer+correction (sticky); dashboard create/filter/cross-filter/drill/edit-by-prompt/print |
| 04-models | 012 | Ames via gallery; teaching+split notes; reasoned features; curate; deterministic train; $-evaluation on holdout; predictions dataset; restart |
| 05-relational | 018, 019 | bundle in one click; framing + hidden outcomes; three tiers honest comparison; connect DB → author from question; adjust+confirm; shuffled-outcome canary; train; story names source + local-copy disclosure |

Tutorial breakage = shipped-behavior breakage: each step lands on an
observable result some board asserts. Keep this table in sync when specs
change.

## Non-goals

- OAuth/workspaces (needs external provider config) — pointed at the
  manual.
- Screenshots: text is label-precise; manual carries imagery.
