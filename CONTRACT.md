# analyst — API contract & alignment plan

The frontend and backend now share **one contract, sourced from the backend
domain** (`src/analyst/domain/*`). The mock moved out of the TypeScript app and
into Python, served through the real FastAPI layer, so the UI only ever talks to
`/api/*` — fixtures in dev, DuckDB in prod, same shapes either way.

## What changed and why

Previously the frontend carried its own TS mock whose shapes were invented from
the wireframes. They drifted from the implemented feature-001 domain. This plan
aligns them:

| Concern | Was (TS mock) | Now (domain-truth) |
|---|---|---|
| Column type | `dtype: 'VARCHAR'` (DuckDB storage) | `inferredType: 'text'\|'integer'\|'decimal'\|'boolean'\|'date'\|'datetime'` (domain `ColumnType`) |
| Nulls | `nullPercent` 0–100 | `nullCount` + `nullRate` 0–1 (`DatasetProfile.null_rate`) |
| Distinct | `uniqueCount` | `distinctCount` |
| Samples | `sample` | `samples` |
| Range | `min`/`max`/`q25`/`median`/`q75` | `minimum`/`maximum`/`quantiles: []` |
| Column role | `key/dimension/text` | `identifier/measure/category/timestamp/text/other` (cataloguer vocab) |
| Relationships | invented PK/FK cards | **removed** — not in the backend (later phase) |
| Clarifications | (absent) | **surfaced** — `CatalogEntry.clarifications` (the AskQuestion primitive) |
| Profiling facts | (absent) | `isMixed`/`dominantType`/`offTypeExamples`, `isNested`, `encoding`/`synthesizedHeaders`/`hadDuplicateColumns` |
| Ingestion status | 6 UI phases | domain 3-state `in progress\|complete\|failed` (+ optional UI `phase`/`progress` hints) |
| Mock location | `frontend/src/mocks/*` | `src/analyst/api/fixtures.py` (real domain objects) |

Wire format is **camelCase JSON** (pydantic `alias_generator=to_camel`), so the
JS side needs no case-munging; Python stays snake_case.

## Endpoints (feature 001 — implemented domain)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/datasets` | `Dataset[]` (envelope: id,name,fileName,status,rowCount,columnCount,profile,catalog) |
| GET | `/api/datasets/{name}` | `Dataset` |
| POST | `/api/datasets/ingest` | `IngestionResult { datasets: Dataset[] }` (multipart file) |
| GET | `/api/ingestion/{name}/status` | `IngestionStatus { dataset, status, phase?, progress? }` |
| DELETE | `/api/datasets/{name}` | 204 |
| POST | `/api/datasets/{name}/refresh` | `RefreshResult` |
| GET | `/api/catalog` | `Record<name, CatalogEntry>` |
| GET | `/api/health` | `{ ok: true, fixtures: boolean, qa: "real"\|"canned" }` |

`Dataset.id === name` — the backend keys datasets by their sanitized slug
(`_sanitize` in `service/ingestion.py`); there is no separate id.

`Dataset.profile` is the **pure** domain `DatasetProfile`; the envelope fields
(`id/fileName/status/ingestedAt/rowCount/columnCount`) are API conveniences the
repository supplies. `rowCount = profile.rowCount`, `columnCount = len(columns)`.

## Endpoints (feature 002 — Q&A, PROVISIONAL)

Q&A has **no domain model yet**. These live in the API schema layer, marked
provisional, and are built on the one primitive the domain does define —
`Clarification { question, options: string[], column? }`:

| Method | Path | Returns |
|---|---|---|
| POST | `/api/query` | `ClarificationResult \| AnswerResult` |
| POST | `/api/query/{queryId}/respond` | `AnswerResult` |

`ClarificationResult` mirrors the domain `Clarification` (bare-string options —
the UI adapts to that). `AnswerResult`/`TrustTrail` are UI-forward shapes; when
feature 002 lands they become domain objects and these schemas wrap them.

## Mock lives in Python

`api/repository.py` defines `DatasetRepository`. Two implementations:

- **`FixtureRepository`** (opt-in mock; `ANALYST_FIXTURES=1`) — seeds sales /
  customers / products as **real `DatasetSummary` domain objects** from
  `api/fixtures.py`, plus canned Q&A. Ingest simulates the 3-state lifecycle.
- **`StoreRepository`** (**default**) — wraps the real
  `IngestionService` + `DatasetStore` (DuckDB/Parquet).

Because fixtures are built from the domain dataclasses, they can't drift from the
contract — if the domain changes, the fixtures stop type-checking.

## Frontend

- `api/types.ts` mirrors the camelCase wire.
- `api/client.ts` is HTTP-only (no TS mock); base URL via Vite proxy `/api → :8000`.
- `lib/adapt.ts` maps wire `DatasetProfile` → the profile-card view-model
  (`nullRate×100`, `distinctCount`, `quantiles → 25/50/75`, `minimum/maximum`).
- `mocks/*` deleted.

## Run

```bash
make run     # the whole app in Docker (+ demo DBs)
# dev servers:
uv run uvicorn analyst.api.app:app --reload --port 8000              # real store (default)
ANALYST_FIXTURES=1 uv run uvicorn analyst.api.app:app --port 8000    # in-memory fixtures (demos / e2e)
cd frontend && bun run dev                                           # vite :5173, proxies /api → :8000
```

The mock is opt-in (`ANALYST_FIXTURES=1`), never the default.
