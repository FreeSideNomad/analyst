// ── Column & Dataset enums ──────────────────────────────────────────

export type ColumnType =
  | 'text'
  | 'integer'
  | 'decimal'
  | 'boolean'
  | 'date'
  | 'datetime';

export type ColumnRole =
  | 'primary_key'
  | 'foreign_key'
  | 'metric'
  | 'dimension'
  | 'attribute';

export type IngestionStatus =
  | 'uploading'
  | 'materializing'
  | 'profiling'
  | 'cataloguing'
  | 'complete'
  | 'failed';

export type DataSourceType =
  | 'csv'
  | 'tsv'
  | 'xlsx'
  | 'json'
  | 'postgres'
  | 'mysql';

// ── Profiling ───────────────────────────────────────────────────────

export interface ColumnProfile {
  name: string;
  inferredType: ColumnType;
  nullCount: number;
  nullRate: number;
  distinctCount: number;
  samples: unknown[];
  minimum?: number;
  maximum?: number;
  quantiles?: [number, number, number];
  isMixed?: boolean;
  dominantType?: ColumnType;
  offTypeExamples?: unknown[];
  wasSynthesized?: boolean;
}

export interface DatasetProfile {
  rowCount: number;
  columns: ColumnProfile[];
}

// ── Datasets ────────────────────────────────────────────────────────

export interface Dataset {
  id: string;
  name: string;
  sourceType: DataSourceType;
  fileName?: string;
  rowCount: number;
  columnCount: number;
  status: IngestionStatus;
  createdAt: string;
  updatedAt: string;
}

export interface DatasetVersion {
  version: number;
  createdAt: string;
  rowCount: number;
}

export interface DatasetDetail extends Dataset {
  profile: DatasetProfile;
  versions: DatasetVersion[];
}

// ── Catalog ─────────────────────────────────────────────────────────

export interface ColumnDescription {
  name: string;
  description: string;
  role: ColumnRole;
  inferredType: ColumnType;
}

export interface Relationship {
  fromDataset: string;
  fromColumn: string;
  toDataset: string;
  toColumn: string;
  confidence: number;
  validated: boolean;
}

export interface CatalogEntry {
  datasetId: string;
  datasetName: string;
  tableDescription: string;
  columns: ColumnDescription[];
  discoveredRelationships: Relationship[];
}

// ── Database connections ────────────────────────────────────────────

export interface DatabaseTable {
  name: string;
  schema: string;
  rowCount?: number;
  columns: ColumnDescription[];
}

export interface DatabaseConnection {
  id: string;
  name: string;
  type: DataSourceType;
  host: string;
  database: string;
  status: string;
  tables: DatabaseTable[];
}

// ── Ingestion ───────────────────────────────────────────────────────

export interface IngestionResult {
  datasetId: string;
  datasetName: string;
  profile: DatasetProfile;
}

export interface IngestionStatusResponse {
  jobId: string;
  status: IngestionStatus;
  progress: number;
  result?: IngestionResult;
  error?: string;
}

// ── Refresh ─────────────────────────────────────────────────────────

export interface SchemaConflict {
  column: string;
  expected: string;
  actual: string;
}

export interface RefreshResult {
  datasetId: string;
  newVersion: number;
  schemaConforms: boolean;
  conflicts?: SchemaConflict[];
}

// ── Query / Chat ────────────────────────────────────────────────────

export interface QueryRequest {
  question: string;
  datasetIds?: string[];
}

export interface QueryRespondRequest {
  questionId: string;
  selectedOptions: string[];
}

export interface AskQuestionOption {
  label: string;
  value: string;
  description?: string;
  preview?: string;
}

export interface AskQuestionPayload {
  questionId: string;
  question: string;
  options: AskQuestionOption[];
  selection: 'single' | 'multi';
}

// ── Trust trail ─────────────────────────────────────────────────────

export interface LineageNode {
  source: string;
  columns: string[];
}

export interface TrustTrail {
  assumptions: string[];
  lineage: LineageNode[];
  sql: string;
}

// ── Chart ───────────────────────────────────────────────────────────

export interface ChartDataPoint {
  label: string;
  value: number;
  group?: string;
}

export interface ChartSpec {
  type: 'bar' | 'line' | 'pie' | 'table';
  title: string;
  data: ChartDataPoint[];
  xLabel?: string;
  yLabel?: string;
}

// ── Query result ────────────────────────────────────────────────────

export interface QueryResult {
  queryId: string;
  answer: string;
  clarification?: AskQuestionPayload;
  chart?: ChartSpec;
  trustTrail?: TrustTrail;
}

// ── Chat messages (discriminated union) ─────────────────────────────

export interface UserMessage {
  type: 'user';
  timestamp: string;
  text: string;
}

export interface ClarificationMessage {
  type: 'clarification';
  timestamp: string;
  payload: AskQuestionPayload;
}

export interface ResultMessage {
  type: 'result';
  timestamp: string;
  result: QueryResult;
}

export interface ErrorMessage {
  type: 'error';
  timestamp: string;
  error: string;
}

export type ChatMessage =
  | UserMessage
  | ClarificationMessage
  | ResultMessage
  | ErrorMessage;

// ── Egress ──────────────────────────────────────────────────────────

export interface EgressEntry {
  id: string;
  timestamp: string;
  datasetId: string;
  payloadType: string;
  tokenCount: number;
  sampleCount?: number;
}
