// ── stores/index.ts ──────────────────────────────────────────────────
// Zustand stores. All data comes from the API (api/client); there is no TS
// mock. Call useCatalog.getState().hydrate() once on app start.
import { create } from 'zustand';
import { api } from '../api/client';
import type {
  ChatMessage, ClarificationResult, Dataset, CatalogEntry, IngestionStatusValue,
} from '../api/types';

let _mid = 0;
const nid = () => 'm' + ++_mid;

// ── ui-store ─────────────────────────────────────────────────────────
interface UIState {
  view: 'ingest' | 'workspace';
  detailCollapsed: boolean;
  setView: (view: 'ingest' | 'workspace') => void;
  toggleDetail: () => void;
}
export const useUI = create<UIState>((set) => ({
  view: 'workspace',
  detailCollapsed: false,
  setView: (view) => set({ view }),
  toggleDetail: () => set((s) => ({ detailCollapsed: !s.detailCollapsed })),
}));

// ── catalog-store ────────────────────────────────────────────────────
interface CatalogState {
  datasets: Dataset[];
  catalog: Record<string, CatalogEntry>;
  loading: boolean;
  activeProfileId: string | null;   // Ingest view
  detailDatasetId: string | null;   // Workspace view
  selectedColumn: { ds: string; name: string } | null;
  expanded: Record<string, boolean>;
  hydrate: () => Promise<void>;
  refresh: () => Promise<void>;
  remove: (id: string) => Promise<void>;
  setActiveProfile: (id: string) => void;
  setDetail: (id: string) => void;
  toggleExpand: (id: string) => void;
  selectColumn: (ds: string, name: string) => void;
}
export const useCatalog = create<CatalogState>((set) => ({
  datasets: [],
  catalog: {},
  loading: true,
  activeProfileId: null,
  detailDatasetId: null,
  selectedColumn: null,
  expanded: {},
  hydrate: async () => {
    const [datasets, catalog] = await Promise.all([api.listDatasets(), api.getCatalog()]);
    const first = datasets[0]?.id ?? null;
    set((s) => ({
      datasets, catalog, loading: false,
      activeProfileId: s.activeProfileId ?? first,
      detailDatasetId: s.detailDatasetId ?? first,
      expanded: Object.keys(s.expanded).length ? s.expanded : (first ? { [first]: true } : {}),
    }));
  },
  refresh: async () => {
    const [datasets, catalog] = await Promise.all([api.listDatasets(), api.getCatalog()]);
    set({ datasets, catalog });
  },
  remove: async (id) => {
    await api.deleteDataset(id);
    const [datasets, catalog] = await Promise.all([api.listDatasets(), api.getCatalog()]);
    const first = datasets[0]?.id ?? null;
    set((s) => ({
      datasets, catalog,
      detailDatasetId: s.detailDatasetId === id ? first : s.detailDatasetId,
      activeProfileId: s.activeProfileId === id ? first : s.activeProfileId,
      selectedColumn: s.selectedColumn?.ds === id ? null : s.selectedColumn,
      expanded: Object.fromEntries(Object.entries(s.expanded).filter(([k]) => k !== id)),
    }));
  },
  setActiveProfile: (id) => set({ activeProfileId: id }),
  setDetail: (id) => set({ detailDatasetId: id }),
  toggleExpand: (id) => set((s) => ({ expanded: { ...s.expanded, [id]: !s.expanded[id] }, detailDatasetId: id })),
  selectColumn: (ds, name) => set({ selectedColumn: { ds, name }, detailDatasetId: ds }),
}));

// ── ingestion-store ──────────────────────────────────────────────────
interface UploadJob { name: string; fileName: string; status: IngestionStatusValue; phase: string | null; progress: number; error?: string | null; }
interface IngestionState {
  uploads: UploadJob[];
  startIngestion: (file: File) => Promise<void>;
}
export const useIngestion = create<IngestionState>((set) => ({
  uploads: [],
  startIngestion: async (file) => {
    // The REAL picked/dropped file is uploaded. Rejections surface as a failed
    // upload card carrying the API's message (AC-12/AC-13).
    let res;
    try {
      res = await api.ingest(file);
    } catch (e) {
      const error = e instanceof Error ? e.message : String(e);
      set((s) => ({ uploads: [...s.uploads, { name: file.name, fileName: file.name, status: 'failed', phase: null, progress: 0, error }] }));
      return;
    }
    const ds = res.datasets[0];
    if (!ds) return;
    set((s) => ({ uploads: [...s.uploads, { name: ds.name, fileName: ds.fileName, status: ds.status, phase: null, progress: 0 }] }));
    // poll status until complete
    const poll = setInterval(async () => {
      const st = await api.ingestionStatus(ds.name);
      set((s) => ({ uploads: s.uploads.map((u) => u.name === ds.name ? { ...u, status: st.status, phase: st.phase ?? null, progress: st.progress ?? u.progress } : u) }));
      if (st.status !== 'in progress') {
        clearInterval(poll);
        await useCatalog.getState().refresh();
        useCatalog.getState().setActiveProfile(ds.name);
        setTimeout(() => set((s) => ({ uploads: s.uploads.filter((u) => u.name !== ds.name) })), 1500);
      }
    }, 500);
  },
}));

// ── query-store ──────────────────────────────────────────────────────
interface QueryState {
  messages: ChatMessage[];
  pending: ClarificationResult | null;
  thinking: boolean;
  submit: (text: string) => Promise<void>;
  respond: (payload: ClarificationResult, value: string) => Promise<void>;
}
export const useQuery = create<QueryState>((set) => ({
  messages: [],
  pending: null,
  thinking: false,
  submit: async (text) => {
    const q = text.trim();
    if (!q) return;
    set((s) => ({ messages: [...s.messages, { id: nid(), type: 'user', text: q }], thinking: true, pending: null }));
    const res = await api.submitQuery(q);
    if (res.type === 'clarification') {
      set((s) => ({ thinking: false, messages: [...s.messages, { id: nid(), type: 'clarification', payload: res, chosen: null }], pending: res }));
    } else {
      set((s) => ({ thinking: false, messages: [...s.messages, { id: nid(), type: 'result', result: res }] }));
    }
  },
  respond: async (payload, value) => {
    set((s) => ({
      messages: s.messages.map((m) => (m.type === 'clarification' && m.payload.queryId === payload.queryId ? { ...m, chosen: value } : m)),
      pending: null, thinking: true,
    }));
    const res = await api.respondQuery(payload.queryId, [value]);
    set((s) => ({ thinking: false, messages: [...s.messages, { id: nid(), type: 'result', result: res }] }));
  },
}));
