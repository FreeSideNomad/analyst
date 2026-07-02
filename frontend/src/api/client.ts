import type {
  Dataset,
  DatasetDetail,
  CatalogEntry,
  DatabaseConnection,
  IngestionResult,
  IngestionStatusResponse,
  RefreshResult,
  QueryRequest,
  QueryRespondRequest,
  QueryResult,
  EgressEntry,
} from './types';

// ── Configuration ───────────────────────────────────────────────────

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false';
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

// ── Real fetch helper ───────────────────────────────────────────────

async function realFetch<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`API ${method} ${path} → ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Mock-aware request dispatcher ───────────────────────────────────

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  if (USE_MOCKS) {
    const { mockRequest } = await import('../mocks/handlers');
    return mockRequest<T>(method, path, body);
  }
  return realFetch<T>(method, path, body);
}

// ── Datasets API ────────────────────────────────────────────────────

export const datasetsApi = {
  list: () => request<Dataset[]>('GET', '/datasets'),

  detail: (id: string) =>
    request<DatasetDetail>('GET', `/datasets/${id}`),

  ingest: (file: File) => {
    if (USE_MOCKS) {
      return request<IngestionResult>('POST', '/datasets/ingest', {
        name: file.name,
        size: file.size,
      });
    }
    const form = new FormData();
    form.append('file', file);
    return fetch(`${BASE_URL}/datasets/ingest`, {
      method: 'POST',
      body: form,
    }).then((r) => {
      if (!r.ok) throw new Error(`Upload failed: ${r.status}`);
      return r.json() as Promise<IngestionResult>;
    });
  },

  ingestionStatus: (jobId: string) =>
    request<IngestionStatusResponse>('GET', `/ingestion/${jobId}/status`),

  refresh: (id: string) =>
    request<RefreshResult>('POST', `/datasets/${id}/refresh`),

  remove: (id: string) => request<void>('DELETE', `/datasets/${id}`),
};

// ── Catalog API ─────────────────────────────────────────────────────

export const catalogApi = {
  list: () => request<CatalogEntry[]>('GET', '/catalog'),

  detail: (datasetId: string) =>
    request<CatalogEntry>('GET', `/catalog/${datasetId}`),

  connections: () =>
    request<DatabaseConnection[]>('GET', '/connections'),
};

// ── Query API ───────────────────────────────────────────────────────

export const queryApi = {
  ask: (payload: QueryRequest) =>
    request<QueryResult>('POST', '/query', payload),

  respond: (payload: QueryRespondRequest) =>
    request<QueryResult>('POST', '/query/respond', payload),
};

// ── Egress API ──────────────────────────────────────────────────────

export const egressApi = {
  list: () => request<EgressEntry[]>('GET', '/egress'),
};
