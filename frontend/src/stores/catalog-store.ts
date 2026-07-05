// ── catalog-store ─────────────────────────────────────────────────────
// Owner: datasets/catalog surface (features 001/002/005).
import { create } from 'zustand';
import { api } from '../api/client';
import { databasesApi } from '../api/databases';
import type { ConnectDatabaseRequest, DatabaseConnection } from '../api/databases';
import type { Dataset, CatalogEntry } from '../api/types';

// Feature 009: poll while any table is still cataloguing so descriptions refresh
// with no manual reload. Shared by hydrate() (resume on load) and connectDatabase().
let _catalogPoll: ReturnType<typeof setInterval> | null = null;
function startCatalogPoll(set: (partial: Partial<CatalogState>) => void): void {
  if (_catalogPoll) clearInterval(_catalogPoll);
  _catalogPoll = setInterval(async () => {
    try {
      const [ds, cat] = await Promise.all([api.listDatasets(), api.getCatalog()]);
      set({ datasets: ds, catalog: cat });
      if (!ds.some((d) => d.catalogStatus === 'pending')) {
        if (_catalogPoll) clearInterval(_catalogPoll);
        _catalogPoll = null;
      }
    } catch {
      if (_catalogPoll) clearInterval(_catalogPoll);
      _catalogPoll = null;
    }
  }, 600);
}

interface CatalogState {
  datasets: Dataset[];
  catalog: Record<string, CatalogEntry>;
  connections: DatabaseConnection[];   // feature 005: federated databases
  loading: boolean;
  activeProfileId: string | null;   // Ingest view
  detailDatasetId: string | null;   // Workspace view
  selectedColumn: { ds: string; name: string } | null;
  expanded: Record<string, boolean>;
  hydrate: () => Promise<void>;
  refresh: () => Promise<void>;
  remove: (id: string) => Promise<void>;
  connectDatabase: (req: ConnectDatabaseRequest) => Promise<void>;
  detachDatabase: (name: string) => Promise<void>;
  setActiveProfile: (id: string) => void;
  setDetail: (id: string) => void;
  toggleExpand: (id: string) => void;
  selectColumn: (ds: string, name: string) => void;
  clearColumn: () => void;
}
export const useCatalog = create<CatalogState>((set) => ({
  datasets: [],
  catalog: {},
  connections: [],
  loading: true,
  activeProfileId: null,
  detailDatasetId: null,
  selectedColumn: null,
  expanded: {},
  hydrate: async () => {
    const [datasets, catalog, connections] = await Promise.all([
      api.listDatasets(), api.getCatalog(), databasesApi.list().catch(() => []),
    ]);
    set({ connections });
    const first = datasets[0]?.id ?? null;
    set((s) => ({
      datasets, catalog, loading: false,
      activeProfileId: s.activeProfileId ?? first,
      detailDatasetId: s.detailDatasetId ?? first,
      expanded: Object.keys(s.expanded).length ? s.expanded : (first ? { [first]: true } : {}),
    }));
    // Feature 009: if we arrived (or reloaded) mid-cataloguing, resume polling
    // so pending tables refresh to their descriptions with no manual reload.
    if (datasets.some((d) => d.catalogStatus === 'pending')) startCatalogPoll(set);
  },
  refresh: async () => {
    const [datasets, catalog, connections] = await Promise.all([
      api.listDatasets(), api.getCatalog(), databasesApi.list().catch(() => []),
    ]);
    set({ datasets, catalog, connections });
  },
  connectDatabase: async (req) => {
    await databasesApi.connect(req); // throws with the API's reason on failure
    const [datasets, catalog, connections] = await Promise.all([
      api.listDatasets(), api.getCatalog(), databasesApi.list(),
    ]);
    set({ datasets, catalog, connections });
    // Feature 009: cataloguing runs in the background; poll until every table
    // has finished (complete or failed) so descriptions refresh with no reload.
    startCatalogPoll(set);
  },
  detachDatabase: async (name) => {
    await databasesApi.detach(name);
    const [datasets, catalog, connections] = await Promise.all([
      api.listDatasets(), api.getCatalog(), databasesApi.list(),
    ]);
    set((s) => ({
      datasets, catalog, connections,
      detailDatasetId: s.detailDatasetId?.startsWith(`${name}.`) ? (datasets[0]?.id ?? null) : s.detailDatasetId,
      selectedColumn: s.selectedColumn?.ds.startsWith(`${name}.`) ? null : s.selectedColumn,
      expanded: Object.fromEntries(Object.entries(s.expanded).filter(([k]) => !k.startsWith(`${name}.`))),
    }));
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
  clearColumn: () => set({ selectedColumn: null }),
}));

