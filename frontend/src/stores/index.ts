// ── stores/index.ts ──────────────────────────────────────────────────
// Zustand stores, one file per area so parallel feature sessions never
// collide. All data comes from the API (api/client); there is no TS mock.
// Call useCatalog.getState().hydrate() once on app start.
export { useUI } from './ui-store';
export { useCatalog } from './catalog-store';
export { useIngestion } from './ingestion-store';
export { useQuery } from './query-store';
