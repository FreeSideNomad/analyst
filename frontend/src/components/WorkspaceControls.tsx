// ── components/WorkspaceControls.tsx ──────────────────────────────────
// Owner: feature 004. Header controls for the signed-in user: workspace
// switcher, admin "New workspace" creation, and sign-out. Rendered only
// when a session exists (auth enabled + signed in).
import { useState } from 'react';
import type { CSSProperties } from 'react';
import { LogOut, Plus } from 'lucide-react';
import { useAuth } from '../stores';
import { IconButton } from './ui';

const SELECT: CSSProperties = {
  height: 34, padding: '0 9px', border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-md)', background: 'var(--surface-card)',
  color: 'var(--text-strong)', font: '600 13px/1 var(--font-sans)', cursor: 'pointer',
};

export function WorkspaceControls() {
  const user = useAuth((s) => s.user);
  const workspaces = useAuth((s) => s.workspaces);
  const activeWorkspaceId = useAuth((s) => s.activeWorkspaceId);
  const switchWorkspace = useAuth((s) => s.switchWorkspace);
  const createWorkspace = useAuth((s) => s.createWorkspace);
  const logout = useAuth((s) => s.logout);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');

  if (!user) return null;

  const create = () => {
    if (!name.trim()) return;
    void createWorkspace(name.trim()).then(() => { setCreating(false); setName(''); });
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {workspaces.length > 0 && (
        <select aria-label="Switch workspace" style={SELECT} value={activeWorkspaceId ?? ''}
          onChange={(e) => void switchWorkspace(e.target.value)}>
          {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
      )}
      {user.isAdmin && (creating ? (
        <form style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          onSubmit={(e) => { e.preventDefault(); create(); }}>
          <input aria-label="New workspace name" autoFocus value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Workspace name" style={{ ...SELECT, cursor: 'text', width: 150 }} />
          <button type="submit" disabled={!name.trim()} style={{ ...SELECT, background: 'var(--brand)', color: 'var(--on-brand)',
            border: '1px solid transparent', cursor: name.trim() ? 'pointer' : 'not-allowed' }}>
            Create workspace
          </button>
        </form>
      ) : (
        <IconButton as={Plus} label="New workspace" onClick={() => setCreating(true)} />
      ))}
      <span style={{ font: '600 13px/1 var(--font-sans)', color: 'var(--text-strong)' }}>{user.name}</span>
      <IconButton as={LogOut} label="Sign out" onClick={() => void logout()} />
    </div>
  );
}
