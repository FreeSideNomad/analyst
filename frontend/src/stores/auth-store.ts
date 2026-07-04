// ── auth-store ────────────────────────────────────────────────────────
// Owner: feature 004 (auth & workspaces). Session-cookie auth against
// /api/auth/*. Auth is opt-in on the backend: when no login method is
// configured the store reports status 'disabled' and the app behaves
// exactly as before feature 004.
import { create } from 'zustand';

export interface AuthUser { id: string; name: string; email: string; isAdmin: boolean }
export interface WorkspaceRef { id: string; name: string }
export interface AuthProviders { authEnabled: boolean; devLogin: boolean; google: boolean; microsoft: boolean }

interface MePayload { user: AuthUser; workspaces: WorkspaceRef[]; activeWorkspaceId: string | null }

export type AuthStatus = 'loading' | 'disabled' | 'anonymous' | 'authenticated';

interface AuthState {
  status: AuthStatus;
  providers: AuthProviders;
  user: AuthUser | null;
  workspaces: WorkspaceRef[];
  activeWorkspaceId: string | null;
  error: string | null;
  hydrate: () => Promise<void>;
  devLogin: (name: string) => Promise<void>;
  logout: () => Promise<void>;
  switchWorkspace: (workspaceId: string) => Promise<void>;
  createWorkspace: (name: string) => Promise<void>;
  addMember: (workspaceId: string, email: string) => Promise<void>;
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const detail = await res.json().then((b) => b?.detail).catch(() => null);
    throw new Error(detail || `${res.status} ${res.statusText} — ${path}`);
  }
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>);
}

const JSON_HEADERS = { 'content-type': 'application/json' };
const NO_PROVIDERS: AuthProviders = { authEnabled: false, devLogin: false, google: false, microsoft: false };

function applyMe(me: MePayload): Partial<AuthState> {
  return {
    status: 'authenticated',
    user: me.user,
    workspaces: me.workspaces,
    activeWorkspaceId: me.activeWorkspaceId,
    error: null,
  };
}

export const useAuth = create<AuthState>((set, get) => ({
  status: 'loading',
  providers: NO_PROVIDERS,
  user: null,
  workspaces: [],
  activeWorkspaceId: null,
  error: null,

  hydrate: async () => {
    const providers = await j<AuthProviders>('/api/auth/providers');
    if (!providers.authEnabled) {
      set({ providers, status: 'disabled' });
      return;
    }
    try {
      const me = await j<MePayload>('/api/auth/me');
      set({ providers, ...applyMe(me) });
    } catch {
      set({ providers, status: 'anonymous', user: null, workspaces: [], activeWorkspaceId: null });
    }
  },

  devLogin: async (name) => {
    try {
      const me = await j<MePayload>('/api/auth/dev-login', {
        method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ name }),
      });
      set(applyMe(me));
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'Sign-in failed' });
    }
  },

  logout: async () => {
    await j<void>('/api/auth/logout', { method: 'POST' });
    set({ status: 'anonymous', user: null, workspaces: [], activeWorkspaceId: null, error: null });
  },

  switchWorkspace: async (workspaceId) => {
    const me = await j<MePayload>('/api/auth/workspace', {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ workspaceId }),
    });
    set(applyMe(me));
  },

  createWorkspace: async (name) => {
    const ws = await j<WorkspaceRef>('/api/workspaces', {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ name }),
    });
    await get().switchWorkspace(ws.id);
  },

  addMember: async (workspaceId, email) => {
    await j('/api/workspaces/' + encodeURIComponent(workspaceId) + '/members', {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ email }),
    });
  },
}));
