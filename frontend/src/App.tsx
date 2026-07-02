// ── App.tsx ──────────────────────────────────────────────────────────
import { useEffect } from 'react';
import { useUI, useCatalog } from './stores';
import { Header } from './components/Header';
import { IngestionPage } from './pages/IngestionPage';
import { WorkspacePage } from './pages/WorkspacePage';

function Loading() {
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', font: '500 14px/1 var(--font-mono)' }}>
      loading workspace…
    </div>
  );
}

export default function App() {
  const view = useUI((s) => s.view);
  const hydrate = useCatalog((s) => s.hydrate);
  const loading = useCatalog((s) => s.loading);
  useEffect(() => { hydrate().catch((e) => console.error('hydrate failed', e)); }, [hydrate]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Header />
      {loading ? <Loading /> : view === 'ingest' ? <IngestionPage /> : <WorkspacePage />}
    </div>
  );
}
