import { create } from 'zustand';
import { datasetApi } from '../api/client';
import type { IngestionResult } from '../api/types';

// ─── Upload Job type ────────────────────────────────────────────────────────

export interface UploadJob {
  fileId: string;
  fileName: string;
  fileSize: number;
  status: 'queued' | 'uploading' | 'profiling' | 'ready' | 'error';
  progress: number;
  result?: IngestionResult;
  error?: string;
}

// ─── Progress simulation steps ──────────────────────────────────────────────

const PROGRESS_STEPS: { status: UploadJob['status']; progress: number }[] = [
  { status: 'uploading', progress: 20 },
  { status: 'uploading', progress: 45 },
  { status: 'uploading', progress: 70 },
  { status: 'profiling', progress: 85 },
  { status: 'profiling', progress: 95 },
  { status: 'ready', progress: 100 },
];

// ─── Store ──────────────────────────────────────────────────────────────────

interface IngestionState {
  uploads: Map<string, UploadJob>;

  startIngestion: (file: { name: string; size: number }) => void;
  simulateProgress: (fileId: string) => void;
}

export const useIngestionStore = create<IngestionState>((set, get) => ({
  uploads: new Map(),

  startIngestion: async (file) => {
    const fileId = `file-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    const job: UploadJob = {
      fileId,
      fileName: file.name,
      fileSize: file.size,
      status: 'queued',
      progress: 0,
    };

    set((s) => {
      const next = new Map(s.uploads);
      next.set(fileId, job);
      return { uploads: next };
    });

    // Kick off the API call (which returns quickly with a job ID)
    try {
      const result = await datasetApi.ingest(file);

      // Update the job with the API result
      set((s) => {
        const next = new Map(s.uploads);
        const current = next.get(fileId);
        if (current) {
          next.set(fileId, { ...current, result, status: 'uploading', progress: 10 });
        }
        return { uploads: next };
      });

      // Start simulated progress
      get().simulateProgress(fileId);
    } catch (err) {
      set((s) => {
        const next = new Map(s.uploads);
        const current = next.get(fileId);
        if (current) {
          next.set(fileId, {
            ...current,
            status: 'error',
            error: (err as Error).message,
          });
        }
        return { uploads: next };
      });
    }
  },

  simulateProgress: (fileId) => {
    let stepIndex = 0;

    const interval = setInterval(() => {
      if (stepIndex >= PROGRESS_STEPS.length) {
        clearInterval(interval);
        return;
      }

      const step = PROGRESS_STEPS[stepIndex];
      stepIndex++;

      set((s) => {
        const next = new Map(s.uploads);
        const current = next.get(fileId);
        if (!current) {
          clearInterval(interval);
          return { uploads: next };
        }
        next.set(fileId, {
          ...current,
          status: step.status,
          progress: step.progress,
        });
        return { uploads: next };
      });
    }, 800);
  },
}));
