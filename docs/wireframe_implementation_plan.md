# Interactive React Wireframe App — analyst Frontend

Build a clickable, interactive wireframe app using real React components, Zustand state management, Tailwind CSS, and shadcn/ui — serving as both a design validation tool and the foundation for the production frontend.

## User Review Required

> [!IMPORTANT]
> **Location**: The wireframe app will be created at `frontend/` in the project root. This keeps it alongside the Python backend but clearly separated. Confirm this is acceptable vs. a separate repo.

> [!IMPORTANT]
> **Scope**: This wireframe covers Feature 001 (Ingestion & Profiling) and Feature 002 (NL Q&A) screens. Relational DB connections will appear in the catalog sidebar as a data source type, but the connection setup UI is deferred to the federation feature.

> [!WARNING]
> **shadcn/ui version**: The plan uses shadcn/ui (latest) with Tailwind v4. Please confirm or specify a preferred version.

## Open Questions

> [!IMPORTANT]
> **Dashboard wireframe**: Should we include a placeholder dashboard builder screen now, or defer entirely to the "later" horizon?

> [!IMPORTANT]  
> **Auth screens**: The PRD specifies Google/MS OAuth. Should we include login/workspace-selection wireframe screens, or skip since auth is a separate feature?

## Proposed Changes

### Architecture Overview

```
frontend/
├── src/
│   ├── api/                    # API client + TypeScript types
│   │   ├── types.ts            # Shared API response/request types
│   │   └── client.ts           # API client (fetch wrapper, base URL config)
│   │
│   ├── mocks/                  # Mock API layer (isolated, swappable)
│   │   ├── data/               # Static mock datasets
│   │   │   ├── datasets.ts     # Mock dataset profiles, catalog entries
│   │   │   └── queries.ts      # Mock Q&A conversations
│   │   ├── handlers.ts         # Mock API handlers (same interface as real API)
│   │   └── provider.ts         # MSW or simple mock provider toggle
│   │
│   ├── stores/                 # Zustand state stores
│   │   ├── catalog-store.ts    # Datasets, catalog entries, DB connections
│   │   ├── ingestion-store.ts  # Upload state, progress, profiling results
│   │   ├── query-store.ts      # Q&A conversations, AskQuestion state
│   │   └── ui-store.ts         # Sidebar toggle, active view, theme
│   │
│   ├── components/             # Reusable UI components
│   │   ├── layout/
│   │   │   ├── AppShell.tsx        # Top-level grid: header + sidebar + main
│   │   │   ├── Header.tsx          # Logo, status, user menu
│   │   │   └── Sidebar.tsx         # Catalog tree (databases, tables, columns)
│   │   ├── catalog/
│   │   │   ├── CatalogTree.tsx     # Expandable tree: DBs → tables → columns
│   │   │   ├── ColumnBadge.tsx     # Role badges (PK, FK, Metric, Dimension)
│   │   │   └── DatasetCard.tsx     # Summary card for a dataset
│   │   ├── ingestion/
│   │   │   ├── FileDropZone.tsx    # Drag-and-drop upload area
│   │   │   ├── IngestionProgress.tsx  # Step-by-step progress indicator
│   │   │   └── ProfileView.tsx     # Column profile cards with stats
│   │   ├── query/
│   │   │   ├── ChatPanel.tsx       # Scrollable chat message log
│   │   │   ├── ChatInput.tsx       # Text input + send button
│   │   │   ├── UserMessage.tsx     # User's question bubble
│   │   │   ├── AgentMessage.tsx    # Agent response (result, chart, text)
│   │   │   ├── AskQuestion.tsx     # Clarification card with selectable chips
│   │   │   └── TrustTrail.tsx      # Expandable: Assumptions, Lineage, SQL
│   │   └── shared/
│   │       ├── StatusBadge.tsx     # in_progress / complete / failed
│   │       └── CodeBlock.tsx       # Syntax-highlighted SQL display
│   │
│   ├── pages/
│   │   ├── IngestionPage.tsx   # File upload + profiling dashboard
│   │   ├── CatalogPage.tsx     # Full catalog browser
│   │   └── QueryPage.tsx       # Q&A workspace
│   │
│   ├── styles/
│   │   └── swiss-tokens.css    # Design system tokens (colors, spacing, type scale)
│   │
│   ├── App.tsx                 # Router + AppShell
│   └── main.tsx                # Entry point
│
├── index.html
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── vite.config.ts
```

---

### Mock API Layer

The mock layer mirrors the real FastAPI endpoints exactly. The API client calls go through the same `client.ts` interface — the mock provider intercepts them during wireframe mode.

#### API Specification (matches planned FastAPI backend)

| Method | Endpoint | Description | Request | Response |
|--------|----------|-------------|---------|----------|
| `GET` | `/api/datasets` | List all datasets | — | `Dataset[]` |
| `GET` | `/api/datasets/:id` | Get dataset with profile | — | `DatasetDetail` |
| `POST` | `/api/datasets/ingest` | Upload and ingest a file | `FormData(file)` | `IngestionResult` |
| `POST` | `/api/datasets/:id/refresh` | Refresh with new data | `FormData(file)` | `RefreshResult` |
| `DELETE` | `/api/datasets/:id` | Delete dataset | — | `void` |
| `GET` | `/api/catalog` | Get full semantic catalog | — | `CatalogEntry[]` |
| `GET` | `/api/catalog/:datasetId` | Get catalog entry for dataset | — | `CatalogEntry` |
| `POST` | `/api/query` | Submit NL query | `{ question, datasetIds? }` | `QueryResult` |
| `POST` | `/api/query/:id/respond` | Answer an AskQuestion | `{ questionId, selectedOptions }` | `QueryResult` |
| `GET` | `/api/ingestion/:id/status` | Poll ingestion status | — | `IngestionStatus` |
| `GET` | `/api/egress-log` | Governance audit log | — | `EgressEntry[]` |

#### Mock Toggle

```typescript
// api/client.ts
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false'; // default: true

export const api = USE_MOCKS ? mockClient : realClient;
```

When the real FastAPI backend is ready, flipping `VITE_USE_MOCKS=false` routes all calls to the live server with zero code changes.

---

### Zustand Stores

#### `catalog-store.ts`
```typescript
interface CatalogState {
  datasets: Dataset[];
  catalogEntries: Map<string, CatalogEntry>;
  databases: DatabaseConnection[];
  activeDatasetId: string | null;
  // actions
  fetchDatasets: () => Promise<void>;
  fetchCatalogEntry: (datasetId: string) => Promise<void>;
  setActiveDataset: (id: string) => void;
  deleteDataset: (id: string) => Promise<void>;
}
```

#### `ingestion-store.ts`
```typescript
interface IngestionState {
  uploads: Map<string, UploadJob>;  // fileId -> job
  // actions
  startIngestion: (file: File) => Promise<void>;
  pollStatus: (jobId: string) => Promise<void>;
}

interface UploadJob {
  fileId: string;
  fileName: string;
  status: 'uploading' | 'materializing' | 'profiling' | 'cataloguing' | 'complete' | 'failed';
  progress: number;       // 0-100
  result?: IngestionResult;
  error?: string;
}
```

#### `query-store.ts`
```typescript
interface QueryState {
  conversations: ChatMessage[];
  pendingQuestion: AskQuestionPayload | null;
  isQuerying: boolean;
  // actions
  submitQuery: (question: string) => Promise<void>;
  respondToQuestion: (questionId: string, selected: string[]) => Promise<void>;
}

type ChatMessage =
  | { type: 'user'; text: string }
  | { type: 'clarification'; payload: AskQuestionPayload }
  | { type: 'result'; answer: string; chart?: ChartSpec; trustTrail: TrustTrail }
  | { type: 'error'; message: string };
```

---

### Swiss International Design System Tokens

```css
/* styles/swiss-tokens.css */
:root {
  /* Typography — Helvetica stack */
  --font-primary: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  /* Restrained palette */
  --color-bg: #FFFFFF;
  --color-surface: #FAFAFA;
  --color-border: #E5E5E5;
  --color-text-primary: #1A1A1A;
  --color-text-secondary: #6B6B6B;
  --color-accent: #FF4500;          /* Single accent: orange-red */
  --color-accent-light: #FFF5EE;
  --color-success: #2D8A4E;
  --color-warning: #D4A017;
  --color-error: #C0392B;

  /* Grid */
  --grid-columns: 12;
  --sidebar-span: 3;
  --main-span: 9;
  --spacing-unit: 8px;
  --border-radius: 4px;
}
```

---

### Key Components

#### [NEW] `AskQuestion.tsx`
The cross-cutting clarification primitive (FR-11a). Renders a question with selectable chip options. Single-select by default, multi-select when specified. Orange accent highlight on hover/selection.

#### [NEW] `TrustTrail.tsx`
Collapsible accordion with three sections: **Assumptions** (plain-English bullet list), **Lineage** (source → column flow), **Generated SQL** (syntax-highlighted code block). Collapsed by default for business users; expandable for power users.

#### [NEW] `CatalogTree.tsx`
Recursive tree component. Top level: databases (with connection status icon) and file-based datasets. Expanding a table shows columns with inline role badges (`PK`, `FK`, `Metric`, `Dimension`) and one-line descriptions. Clicking a column opens the profile detail panel.

#### [NEW] `FileDropZone.tsx`
Drag-and-drop area with file type validation (CSV, XLSX, TSV, JSON). On drop, triggers `ingestion-store.startIngestion()` and renders an `IngestionProgress` stepper.

#### [NEW] `ProfileView.tsx`
Grid of column profile cards. Each card shows: column name, inferred type badge, null rate bar, cardinality count, sample values chip list, and (for numeric columns) min/max/quantile sparkline.

---

### Pages

| Page | Route | Description |
|------|-------|-------------|
| `IngestionPage` | `/ingest` | File upload zone + active ingestion progress + completed dataset profiles |
| `CatalogPage` | `/catalog` | Full catalog browser with dataset detail panel |
| `QueryPage` | `/query` | Chat-based Q&A with AskQuestion + Trust Trail |

All pages share the `AppShell` layout (Header + Sidebar + Main content area).

---

## Verification Plan

### Automated Tests
- `npm run build` — TypeScript compilation passes with zero errors
- `npm run lint` — ESLint clean
- `npm run dev` — Dev server starts and renders all three pages

### Manual Verification
- Navigate between Ingestion → Catalog → Query pages via sidebar
- Drop a file in the ingestion zone → see progress stepper animate through states
- Click a dataset in the catalog → see column profiles with stats
- Type a question in Q&A → see AskQuestion card appear → select an option → see result with Trust Trail
- Expand Trust Trail → verify Assumptions, Lineage, and SQL sections render
- Verify mock API responses match the documented API spec types
- Confirm `VITE_USE_MOCKS=false` cleanly switches to real API calls (404s expected, but no type errors)
