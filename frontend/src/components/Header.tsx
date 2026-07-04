// ── components/Header.tsx ─────────────────────────────────────────────
import { LayoutGrid, Users, Bell, Settings } from 'lucide-react';
import { useUI, useAuth } from '../stores';
import { Icon, IconButton, SegmentedControl } from './ui';
import { WorkspaceControls } from './WorkspaceControls';

export function Header() {
  const view = useUI((s) => s.view);
  const setView = useUI((s) => s.setView);
  const user = useAuth((s) => s.user);
  const initials = user
    ? user.name.split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase()
    : 'IM';
  return (
    <header style={{ height: 60, flex: 'none', display: 'flex', alignItems: 'center', gap: 18, padding: '0 22px',
      borderBottom: '1px solid var(--border-subtle)', background: 'var(--surface-card)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
        <div style={{ width: 28, height: 28, background: 'var(--brand)', borderRadius: 'var(--radius-sm)',
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon as={LayoutGrid} size={15} color="#fff" />
        </div>
        <span style={{ font: '800 20px/1 var(--font-sans)', letterSpacing: '-.03em', color: 'var(--text-strong)' }}>analyst</span>
      </div>
      <div style={{ width: 1, height: 26, background: 'var(--border-subtle)' }} />
      <SegmentedControl size="sm" value={view} onChange={(v) => setView(v as 'ingest' | 'workspace')}
        options={[{ value: 'ingest', label: 'Ingest & profile' }, { value: 'workspace', label: 'Catalog & Q\u0026A' }]} />
      <div style={{ flex: 1 }} />
      <span style={{ font: '400 12px/1 var(--font-mono)', color: 'var(--text-subtle)' }}>self-hosted · local DuckDB</span>
      <WorkspaceControls />
      <IconButton as={Users} label="Members" />
      <IconButton as={Bell} label="Alerts" />
      <IconButton as={Settings} label="Settings" />
      <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--navy-100)', color: 'var(--brand)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', font: '600 12px/1 var(--font-mono)' }}>{initials}</div>
    </header>
  );
}
