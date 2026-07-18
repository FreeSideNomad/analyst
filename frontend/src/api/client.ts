// ── api/client.ts ────────────────────────────────────────────────────
// HTTP-only. There is no TS mock any more — the mock lives in the backend
// (src/analyst/api/fixtures.py) and is served through these same endpoints.
// Dev: Vite proxies /api → http://localhost:8000 (see vite.config.ts).
import type { ApiClient, CurationState, IngestionResult, NormalizationState, QueryResult, AnswerResult, SavedChartMeta } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    // Surface the API's friendly `detail` message (domain rejections) so the
    // UI can show WHY something failed, not just that it did (AC-13).
    const detail = await res.json().then((b) => b?.detail).catch(() => null);
    throw new Error(detail || `${res.status} ${res.statusText} — ${path}`);
  }
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>);
}

const JSON_HEADERS = { 'content-type': 'application/json' };

export const api: ApiClient = {
  health: () => j('/api/health'),
  getNormalization: (name) => j<NormalizationState>(`/api/datasets/${encodeURIComponent(name)}/normalization`),
  getCuration: (name) => j<CurationState>(`/api/datasets/${encodeURIComponent(name)}/curation`),
  answerClarification: (name, column, answer) =>
    j<CurationState>(`/api/datasets/${encodeURIComponent(name)}/curation/answer`, {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ column, answer }),
    }),
  suggestCorrection: (name, column, note) =>
    j<CurationState>(`/api/datasets/${encodeURIComponent(name)}/curation/correct`, {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ column, note }),
    }),
  listCharts: () => j('/api/charts'),
  saveChart: (body) => j<SavedChartMeta>('/api/charts', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }),
  openChart: (chartId) => j<AnswerResult>(`/api/charts/${encodeURIComponent(chartId)}`),
  renameChart: (chartId, name) => j<void>(`/api/charts/${encodeURIComponent(chartId)}`, { method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify({ name }) }),
  deleteChart: (chartId) => j<void>(`/api/charts/${encodeURIComponent(chartId)}`, { method: 'DELETE' }),
  actOnNormalization: (name, ruleId, action) =>
    j<NormalizationState>(`/api/datasets/${encodeURIComponent(name)}/normalization/${encodeURIComponent(ruleId)}/${action}`, { method: 'POST' }),
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
