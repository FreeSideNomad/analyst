# analyst — frontend

Self-hosted AI data analyst — React + TypeScript + Zustand, styled with the
SWISS International Typographic design system. Ships with a swappable mock API
layer so it runs standalone today and points at the real FastAPI backend by
flipping one flag.

## Run it (Bun)

```bash
make install     # bun install
make dev         # vite dev server → http://localhost:5173
```

Other targets: `make build`, `make preview`, `make typecheck`, `make clean`,
`make help`. Prefer npm/pnpm? Override the runner: `make dev BUN=npm`.

## Mock vs. real API — the one swap point

`src/api/client.ts`:

```ts
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false'; // default: mocks
export const api = USE_MOCKS ? mockClient : realClient;
```

Every store calls `api.*`. Flip to the real backend with no component changes:

```bash
VITE_USE_MOCKS=false make dev
```

`realClient` calls the endpoints from `docs/wireframe_implementation_plan.md`
(`/api/datasets`, `/api/query`, `/api/query/:id/respond`, `/api/datasets/ingest`, …).

## Structure

```
src/
  api/         types.ts · client.ts (USE_MOCKS swap)
  mocks/       data.ts (datasets, catalog, canned Q&A) · handlers.ts (mockClient)
  stores/      zustand: ui · catalog · ingestion · query
  lib/         format.ts (money, roleBadge, typeLabel)
  components/  ui.tsx (SWISS primitives) · Header.tsx
  pages/       IngestionPage.tsx · WorkspacePage.tsx (catalog tree, detail, Q&A)
  App.tsx · main.tsx · index.css (design tokens)
```

## Surfaces

- **Ingest & profile** — drag/drop upload → live profiling stepper
  (materialize → profile → catalogue) → autopilot column profiles.
- **Catalog & Q&A** — semantic-catalog tree (PK/FK/Metric/Dimension), a
  collapsible table-detail pane with test-validated discovered relationships,
  and workspace-wide Q&A: the **AskQuestion** clarification primitive plus an
  expandable **Trust Trail** (assumptions · lineage · SQL). Answers span all
  tables; joins are automatic.

Styling is inline styles over CSS design tokens (`src/index.css`) — no Tailwind
required, but the token layer is Tailwind/shadcn-ready if you add it later.
