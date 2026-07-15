// ── App.tsx ──────────────────────────────────────────────────────────
import { useEffect } from 'react';
import type { CSSProperties } from 'react';
import { useUI, useCatalog, useAuth } from './stores';
import { Header } from './components/Header';
import { IngestionPage } from './pages/IngestionPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { ChartsPage } from './pages/ChartsPage';
import { LoginPage } from './pages/LoginPage';

const SHELL: CSSProperties = { height: '100%', display: 'flex', flexDirection: 'column' };

function Loading() {
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', font: '500 14px/1 var(--font-mono)' }}>
      loading workspace…
    </div>
  );
}

function NoWorkspace() {
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', font: '500 14px/1.6 var(--font-sans)', textAlign: 'center', padding: 40 }}>
      No workspace has been assigned to you yet.<br />Ask your admin to add you to one.
    </div>
  );
}

export default function App() {
  const view = useUI((s) => s.view);
  const loading = useCatalog((s) => s.loading);
  const status = useAuth((s) => s.status);
  const activeWorkspaceId = useAuth((s) => s.activeWorkspaceId);

  // Auth first: only hydrate the catalog once we know whether a session is
  // needed (auth disabled = pre-004 behavior) and which workspace is active.
  useEffect(() => {
    useAuth.getState().hydrate().catch((e) => console.error('auth hydrate failed', e));
  }, []);

  const ready = status === 'disabled' || (status === 'authenticated' && !!activeWorkspaceId);
  useEffect(() => {
    if (!ready) return;
    // Workspace switch: drop any per-workspace UI state before re-hydrating.
    useCatalog.setState({
      datasets: [], catalog: {}, loading: true,
      activeProfileId: null, detailDatasetId: null, selectedColumn: null, expanded: {},
    });
    useCatalog.getState().hydrate().catch((e) => console.error('hydrate failed', e));
  }, [ready, activeWorkspaceId]);

  if (status === 'loading') return <div style={SHELL}><Loading /></div>;
  if (status === 'anonymous') return <div style={SHELL}><LoginPage /></div>;

  return (
    <div style={SHELL}>
      <Header />
      {status === 'authenticated' && !activeWorkspaceId ? (
        <NoWorkspace />
      ) : loading ? (
        <Loading />
      ) : view === 'ingest' ? (
        <IngestionPage />
      ) : view === 'charts' ? (
        <ChartsPage />
      ) : (
        <WorkspacePage />
      )}
    </div>
  );
}
