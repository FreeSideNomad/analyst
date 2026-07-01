import type { IngestionResult, IngestionStatus, EgressLogEntry } from '../api/types';
import {
  mockDatasets,
  mockDatasetDetails,
  mockCatalogEntries,
  mockDatabases,
} from './data/datasets';
import {
  mockClarificationResult,
  mockAnswerResult,
  mockMultiTableResult,
} from './data/queries';

// ─── Helpers ────────────────────────────────────────────────────────────────

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE';

interface Route {
  method: Method;
  pattern: RegExp;
  handler: (params: Record<string, string>, body?: unknown) => unknown;
}

function extractParams(pattern: RegExp, path: string): Record<string, string> {
  const match = path.match(pattern);
  return match?.groups ?? {};
}

// ─── Sample egress data ─────────────────────────────────────────────────────

const sampleEgressEntries: EgressLogEntry[] = [
  {
    id: 'egr-001',
    timestamp: '2025-12-15T10:30:00Z',
    queryId: 'qry-answer-001',
    direction: 'outbound',
    destination: 'llm-gateway',
    tokenCount: 1240,
    samplePreview: 'SELECT billing_region, SUM(quantity * unit_price)...',
    status: 'allowed',
  },
  {
    id: 'egr-002',
    timestamp: '2025-12-15T10:32:00Z',
    queryId: 'qry-multi-001',
    direction: 'outbound',
    destination: 'llm-gateway',
    tokenCount: 1820,
    samplePreview: 'SELECT c.customer_name, SUM(s.quantity * s.unit_price)...',
    status: 'allowed',
  },
  {
    id: 'egr-003',
    timestamp: '2025-12-15T10:35:00Z',
    queryId: 'qry-blocked-001',
    direction: 'outbound',
    destination: 'llm-gateway',
    tokenCount: 5200,
    samplePreview: 'SELECT email, customer_name, region FROM customers...',
    status: 'blocked',
  },
];

// ─── Route Table ────────────────────────────────────────────────────────────

const routes: Route[] = [
  // ── Datasets ──
  {
    method: 'GET',
    pattern: /^\/datasets$/,
    handler: () => mockDatasets,
  },
  {
    method: 'GET',
    pattern: /^\/datasets\/(?<id>[^/]+)$/,
    handler: ({ id }) => {
      const detail = mockDatasetDetails[id];
      if (!detail) throw new Error(`Dataset not found: ${id}`);
      return detail;
    },
  },
  {
    method: 'POST',
    pattern: /^\/datasets\/ingest$/,
    handler: (_params, body) => {
      const file = body as { name: string; size: number } | undefined;
      const result: IngestionResult = {
        jobId: `job-${Date.now()}`,
        datasetId: `ds-new-${Date.now()}`,
        status: 'queued',
        rowCount: undefined,
        columnCount: undefined,
      };
      console.log('[mock] Ingestion started for', file?.name ?? 'unknown');
      return result;
    },
  },
  {
    method: 'DELETE',
    pattern: /^\/datasets\/(?<id>[^/]+)$/,
    handler: ({ id }) => {
      console.log('[mock] Deleted dataset', id);
      return undefined;
    },
  },

  // ── Ingestion status ──
  {
    method: 'GET',
    pattern: /^\/ingestion\/(?<jobId>[^/]+)\/status$/,
    handler: ({ jobId }) => {
      const status: IngestionStatus = {
        jobId,
        status: 'ready',
        progress: 100,
        datasetId: `ds-new-${jobId}`,
      };
      return status;
    },
  },

  // ── Catalog ──
  {
    method: 'GET',
    pattern: /^\/catalog$/,
    handler: () => mockCatalogEntries,
  },
  {
    method: 'GET',
    pattern: /^\/catalog\/(?<datasetId>[^/]+)$/,
    handler: ({ datasetId }) => {
      const entry = mockCatalogEntries.find((e) => e.datasetId === datasetId);
      if (!entry) throw new Error(`Catalog entry not found: ${datasetId}`);
      return entry;
    },
  },

  // ── Query ──
  {
    method: 'POST',
    pattern: /^\/query$/,
    handler: (_params, body) => {
      const { question } = body as { question: string };
      if (question.toLowerCase().includes('region')) {
        return mockClarificationResult;
      }
      if (question.toLowerCase().includes('customer')) {
        return mockMultiTableResult;
      }
      return mockAnswerResult;
    },
  },
  {
    method: 'POST',
    pattern: /^\/query\/(?<queryId>[^/]+)\/respond$/,
    handler: () => mockAnswerResult,
  },

  // ── Databases ──
  {
    method: 'GET',
    pattern: /^\/databases$/,
    handler: () => mockDatabases,
  },

  // ── Egress log ──
  {
    method: 'GET',
    pattern: /^\/egress-log$/,
    handler: () => sampleEgressEntries,
  },
];

// ─── Public request function ────────────────────────────────────────────────

export async function mockRequest<T>(
  method: Method,
  path: string,
  body?: unknown,
): Promise<T> {
  console.log(`[mock] ${method} ${path}`, body ?? '');

  await delay(300);

  for (const route of routes) {
    if (route.method !== method) continue;
    if (!route.pattern.test(path)) continue;

    const params = extractParams(route.pattern, path);
    const result = route.handler(params, body);
    return result as T;
  }

  throw new Error(`[mock] No handler for ${method} ${path}`);
}
