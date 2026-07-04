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
  // Feature 006: the workbench (Ingest & Profile) is the landing surface —
  // add data + browse the source-grouped catalog; Query is the pure chat.
  view: 'ingest',
  detailCollapsed: false,
  setView: (view) => set({ view }),
  toggleDetail: () => set((s) => ({ detailCollapsed: !s.detailCollapsed })),
}));
