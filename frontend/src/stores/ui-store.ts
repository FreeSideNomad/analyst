import { create } from 'zustand';

export type ActiveView = 'ingest' | 'catalog' | 'query';

interface UiState {
  activeView: ActiveView;
  sidebarOpen: boolean;
  activeDatasetId: string | null;

  setActiveView: (view: ActiveView) => void;
  toggleSidebar: () => void;
  setActiveDataset: (id: string | null) => void;
}

export const useUiStore = create<UiState>((set) => ({
  activeView: 'ingest',
  sidebarOpen: true,
  activeDatasetId: null,

  setActiveView: (view) => set({ activeView: view }),

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  setActiveDataset: (id) => set({ activeDatasetId: id }),
}));
