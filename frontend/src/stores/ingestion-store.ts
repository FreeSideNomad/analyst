// ── ingestion-store ───────────────────────────────────────────────────
// Owner: ingestion surface (features 001/002/005).
import { create } from 'zustand';
import { api } from '../api/client';
import type { IngestionStatusValue } from '../api/types';
import { useCatalog } from './catalog-store';

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
    // poll status until complete — a transient error must not leak the
    // interval or throw an unhandled rejection (frontend hardening).
    const poll = setInterval(async () => {
      try {
        const st = await api.ingestionStatus(ds.name);
        set((s) => ({ uploads: s.uploads.map((u) => u.name === ds.name ? { ...u, status: st.status, phase: st.phase ?? null, progress: st.progress ?? u.progress } : u) }));
        if (st.status !== 'in progress') {
          clearInterval(poll);
          await useCatalog.getState().refresh();
          useCatalog.getState().setActiveProfile(ds.name);
          setTimeout(() => set((s) => ({ uploads: s.uploads.filter((u) => u.name !== ds.name) })), 1500);
        }
      } catch {
        clearInterval(poll);
        set((s) => ({ uploads: s.uploads.map((u) => u.name === ds.name ? { ...u, status: 'failed', error: 'Lost contact while profiling.' } : u) }));
      }
    }, 500);
  },
}));

