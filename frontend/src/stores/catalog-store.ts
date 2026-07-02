import { create } from 'zustand';
import { datasetApi, catalogApi } from '../api/client';
import type {
  DatasetSummary,
  DatasetDetail,
  CatalogEntry,
  DatabaseConnection,
} from '../api/types';

interface CatalogState {
  datasets: DatasetSummary[];
  datasetDetails: Record<string, DatasetDetail>;
  catalogEntries: CatalogEntry[];
  databases: DatabaseConnection[];
  isLoading: boolean;
  error: string | null;

  fetchDatasets: () => Promise<void>;
  fetchDatasetDetail: (id: string) => Promise<void>;
  fetchCatalog: () => Promise<void>;
  deleteDataset: (id: string) => Promise<void>;
}

export const useCatalogStore = create<CatalogState>((set, get) => ({
  datasets: [],
  datasetDetails: {},
  catalogEntries: [],
  databases: [],
  isLoading: false,
  error: null,

  fetchDatasets: async () => {
    set({ isLoading: true, error: null });
    try {
      const datasets = await datasetApi.list();
      set({ datasets, isLoading: false });
    } catch (err) {
      set({ isLoading: false, error: (err as Error).message });
    }
  },

  fetchDatasetDetail: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const detail = await datasetApi.detail(id);
      set({
        datasetDetails: { ...get().datasetDetails, [id]: detail },
        isLoading: false,
      });
    } catch (err) {
      set({ isLoading: false, error: (err as Error).message });
    }
  },

  fetchCatalog: async () => {
    set({ isLoading: true, error: null });
    try {
      const catalogEntries = await catalogApi.list();
      set({ catalogEntries, isLoading: false });
    } catch (err) {
      set({ isLoading: false, error: (err as Error).message });
    }
  },

  deleteDataset: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await datasetApi.remove(id);
      set((s) => ({
        datasets: s.datasets.filter((d) => d.id !== id),
        isLoading: false,
      }));
    } catch (err) {
      set({ isLoading: false, error: (err as Error).message });
    }
  },
}));
