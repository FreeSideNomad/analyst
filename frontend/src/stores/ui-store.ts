// ── ui-store ──────────────────────────────────────────────────────────
// Owner: shared shell (coordinate changes in docs/PARALLEL_PLAN.md).
import { create } from 'zustand';

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
