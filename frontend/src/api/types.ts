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

// Feature 009 — a discovered single-column PK/FK relationship.
export interface Relationship {
  childTable: string;
  childColumn: string;
  parentTable: string;
  parentColumn: string;
  origin: 'declared' | 'inferred';
  joinType: 'required' | 'optional';
  coverage: number;
  extraColumns?: string[][];   // [[childCol, parentCol], ...] for composite keys
}

export interface CatalogEntry {
  tableDescription: string;
  columns: ColumnDescription[];
  clarifications: Clarification[];
  relationships: Relationship[];
}

export type CatalogStatus = 'complete' | 'pending' | 'failed';

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
  catalogStatus: CatalogStatus; // feature 009 — async cataloguing lifecycle
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
export interface TableBlock { columns: string[]; rows: unknown[][]; truncated: boolean; }

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
  chartType: 'bar' | 'line' | 'stat' | 'none';
  abstain?: boolean;
  chartTitle?: string;
  highlight?: string;
  niceMax?: number;
  tickStep?: number;
  chartData?: ChartPoint[];
  stat?: StatBlock;
  table?: TableBlock;
  trustTrail?: TrustTrail;
}

export type QueryResult = ClarificationResult | AnswerResult;

// ── chat message union (UI-held) ────────────────────────────────────
export type ChatMessage =
  | { id: string; type: 'user'; text: string }
  | { id: string; type: 'clarification'; payload: ClarificationResult; chosen: string | null }
  | { id: string; type: 'result'; result: AnswerResult };

// ── client interface ────────────────────────────────────────────────
export interface NormalizationVariant { value: string; rows: number }
export interface NormalizationGroup { canonical: string; variants: NormalizationVariant[] }
export interface NormalizationRule {
  ruleId: string;
  column: string;
  description: string;
  groups: NormalizationGroup[];
}
export interface NormalizationState { proposals: NormalizationRule[]; applied: NormalizationRule[] }

export interface SavedChartMeta {
  chartId: string;
  name: string;
  question: string;
  chartType: string;
  title: string;
  datasets: string[];
}

export interface CurationStamp {
  kind: 'answer' | 'correction';
  input: string;
  description: string;
  pending_reconciliation?: boolean;
}
export interface CurationState {
  clarifications: Clarification[];
  columns: Record<string, CurationStamp>;
  table: CurationStamp | null;
}

export interface DashboardWidgetMeta {
  widgetId: string;
  question: string;
  title: string;
  chartType: string;
  source: string;
}
export interface DashboardMeta {
  dashboardId: string;
  name: string;
  filters: { column: string; label: string }[];
  widgets: DashboardWidgetMeta[];
}
export interface DashboardRunEntry {
  answer: AnswerResult | null;
  error: string | null;
  unaffectedBy: string[];
}
export interface DashboardRun {
  dashboard: DashboardMeta;
  widgets: Record<string, DashboardRunEntry>;
}
export interface DashboardCreateResult {
  dashboard?: DashboardMeta | null;
  clarification?: { question: string; options: string[] } | null;
}

export interface Health {
  ok: boolean;
  fixtures: boolean;
  qa: string;
  /** How descriptions are produced: live | replay | canned | off ("off" = no AI, profile-derived text only). */
  catalog: string;
}

export interface ApiClient {
  health(): Promise<Health>;
  getNormalization(name: string): Promise<NormalizationState>;
  getCuration(name: string): Promise<CurationState>;
  answerClarification(name: string, column: string, answer: string): Promise<CurationState>;
  suggestCorrection(name: string, column: string | null, note: string): Promise<CurationState>;
  listCharts(): Promise<{ charts: SavedChartMeta[] }>;
  listDashboards(): Promise<{ dashboards: DashboardMeta[] }>;
  createDashboard(request: string): Promise<DashboardCreateResult>;
  editDashboard(dashboardId: string, request: string): Promise<DashboardCreateResult>;
  runDashboard(dashboardId: string, filters: { column: string; value: string }[]): Promise<DashboardRun>;
  drillDashboard(dashboardId: string, widgetId: string, filters: { column: string; value: string }[]): Promise<AnswerResult>;
  deleteDashboard(dashboardId: string): Promise<void>;
  removeWidget(dashboardId: string, widgetId: string): Promise<void>;
  saveChart(body: { name: string; question?: string; sql: string; chartType: string; title?: string; datasets?: string[]; assumptions?: string[]; lineage?: string[] }): Promise<SavedChartMeta>;
  openChart(chartId: string): Promise<AnswerResult>;
  renameChart(chartId: string, name: string): Promise<void>;
  deleteChart(chartId: string): Promise<void>;
  actOnNormalization(name: string, ruleId: string, action: 'approve' | 'dismiss' | 'revoke'): Promise<NormalizationState>;
  listDatasets(): Promise<Dataset[]>;
  getDataset(name: string): Promise<Dataset>;
  getCatalog(): Promise<Record<string, CatalogEntry>>;
  ingest(file: File): Promise<IngestionResult>;
  ingestionStatus(name: string): Promise<IngestionStatus>;
  deleteDataset(name: string): Promise<void>;
  submitQuery(question: string): Promise<QueryResult>;
  respondQuery(queryId: string, selectedOptions: string[]): Promise<AnswerResult>;
}
