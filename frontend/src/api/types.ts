// ── api/types.ts ─────────────────────────────────────────────────────
// Mirrors the camelCase wire contract served by src/analyst/api (see
// ../../CONTRACT.md). Feature-001 shapes mirror analyst.domain.* exactly;
// the Q&A block is provisional (feature 002).

export type ColumnType = 'text' | 'integer' | 'decimal' | 'boolean' | 'date' | 'datetime';
export type ColumnRole = 'identifier' | 'measure' | 'category' | 'timestamp' | 'text' | 'other';
export type IngestionStatusValue = 'in progress' | 'complete' | 'failed';

export interface ColumnProfile {
  name: string;
  inferredType: ColumnType;
  nullCount: number;
  nullRate: number;            // 0..1 (domain DatasetProfile.null_rate)
  distinctCount: number;
  samples: unknown[];
  minimum?: unknown;
  maximum?: unknown;
  quantiles: unknown[];        // [q25, q50, q75] for numeric columns
  isMixed: boolean;
  dominantType?: ColumnType | null;
  offTypeExamples: unknown[];
  isNested: boolean;
  distribution: { label: string; count: number }[];  // real histogram / top-K
}

export interface DatasetProfile {
  rowCount: number;
  columns: ColumnProfile[];
  encoding?: string | null;
  synthesizedHeaders: boolean;
  hadDuplicateColumns: boolean;
}

export interface ColumnDescription {
  name: string;
  description: string;
  role: ColumnRole;
}

export interface Clarification {
  question: string;
  options: string[];
  column?: string | null;
}

export interface CatalogEntry {
  tableDescription: string;
  columns: ColumnDescription[];
  clarifications: Clarification[];
}

export interface Dataset {
  id: string;                  // === name (source.entity.ext id)
  name: string;
  fileName: string;
  status: IngestionStatusValue;
  ingestedAt?: string | null;
  rowCount: number;
  columnCount: number;
  profile: DatasetProfile;
  catalog: CatalogEntry | null;
  // Feature 006 — source-grouped workbench (file/connection → table → columns):
  group: string;               // the FILE with extension ("company.xlsx") or connection ("sales_db")
  entity: string;              // the sheet/table/stem shown as the table node ("employees", "orders")
  sourceKind: 'file' | 'database';
  queryable: boolean;          // false for connected-DB tables (not yet Q&A-able)
}

export interface IngestionResult { datasets: Dataset[]; }

export interface IngestionStatus {
  dataset: string;
  status: IngestionStatusValue;
  phase?: string | null;       // UI hint, not domain-authoritative
  progress?: number | null;    // 0..100 UI hint
}

// ── Q&A (PROVISIONAL — feature 002) ─────────────────────────────────
export interface ChartPoint { label: string; value: number; }
export interface TrustTrail { assumptions: string[]; lineage: string[]; sql: string; }
export interface StatBlock { value: string; label: string; sub: string; }

export interface ClarificationResult {
  type: 'clarification';
  queryId: string;
  question: string;
  options: string[];
  column?: string | null;
}

export interface AnswerResult {
  type: 'answer';
  queryId: string;
  summary: string;
  chartType: 'bar' | 'stat' | 'none';
  abstain?: boolean;
  chartTitle?: string;
  highlight?: string;
  niceMax?: number;
  tickStep?: number;
  chartData?: ChartPoint[];
  stat?: StatBlock;
  trustTrail?: TrustTrail;
}

export type QueryResult = ClarificationResult | AnswerResult;

// ── chat message union (UI-held) ────────────────────────────────────
export type ChatMessage =
  | { id: string; type: 'user'; text: string }
  | { id: string; type: 'clarification'; payload: ClarificationResult; chosen: string | null }
  | { id: string; type: 'result'; result: AnswerResult };

// ── client interface ────────────────────────────────────────────────
export interface ApiClient {
  listDatasets(): Promise<Dataset[]>;
  getDataset(name: string): Promise<Dataset>;
  getCatalog(): Promise<Record<string, CatalogEntry>>;
  ingest(file: File): Promise<IngestionResult>;
  ingestionStatus(name: string): Promise<IngestionStatus>;
  deleteDataset(name: string): Promise<void>;
  submitQuery(question: string): Promise<QueryResult>;
  respondQuery(queryId: string, selectedOptions: string[]): Promise<AnswerResult>;
}
