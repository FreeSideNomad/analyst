// ── api/client.ts ────────────────────────────────────────────────────
// HTTP-only. There is no TS mock any more — the mock lives in the backend
// (src/analyst/api/fixtures.py) and is served through these same endpoints.
// Dev: Vite proxies /api → http://localhost:8000 (see vite.config.ts).
import type { ApiClient, IngestionResult, QueryResult, AnswerResult } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>);
}

const JSON_HEADERS = { 'content-type': 'application/json' };

export const api: ApiClient = {
  listDatasets: () => j('/api/datasets'),
  getDataset: (name) => j(`/api/datasets/${encodeURIComponent(name)}`),
  getCatalog: () => j('/api/catalog'),
  ingest: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return j<IngestionResult>('/api/datasets/ingest', { method: 'POST', body: fd });
  },
  ingestionStatus: (name) => j(`/api/ingestion/${encodeURIComponent(name)}/status`),
  deleteDataset: (name) => j<void>(`/api/datasets/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  submitQuery: (question) =>
    j<QueryResult>('/api/query', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ question }) }),
  respondQuery: (queryId, selectedOptions) =>
    j<AnswerResult>(`/api/query/${encodeURIComponent(queryId)}/respond`, {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ selectedOptions }),
    }),
};
