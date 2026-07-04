// ── pages/LoginPage.tsx ───────────────────────────────────────────────
// Owner: feature 004. Shown only when auth is enabled and no session
// exists. Offers the configured sign-in methods; unconfigured OAuth
// providers are stated as such (real credentials are a runbook item).
import { useState } from 'react';
import type { CSSProperties } from 'react';
import { LayoutGrid } from 'lucide-react';
import { useAuth } from '../stores';
import { Button, Icon } from '../components/ui';

const OAUTH_LINK: CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', height: 42,
  border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)',
  background: 'var(--surface-card)', color: 'var(--text-strong)',
  font: '600 15px/1 var(--font-sans)', textDecoration: 'none',
};

const NOT_CONFIGURED: CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', height: 42,
  border: '1px dashed var(--border-default)', borderRadius: 'var(--radius-md)',
  color: 'var(--text-muted)', font: '500 13px/1 var(--font-sans)',
};

function OAuthMethod({ provider, label, configured }: { provider: string; label: string; configured: boolean }) {
  if (!configured) return <div style={NOT_CONFIGURED}>{label} sign-in is not configured</div>;
  return <a href={`/api/auth/login/${provider}`} style={OAUTH_LINK}>Continue with {label}</a>;
}

export function LoginPage() {
  const providers = useAuth((s) => s.providers);
  const devLogin = useAuth((s) => s.devLogin);
  const error = useAuth((s) => s.error);
  const [name, setName] = useState('');

  const submit = () => { if (name.trim()) void devLogin(name.trim()); };

  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--surface-sunken)' }}>
      <div style={{ width: 380, padding: 36, background: 'var(--surface-card)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-md)', display: 'flex', flexDirection: 'column', gap: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
          <div style={{ width: 28, height: 28, background: 'var(--brand)', borderRadius: 'var(--radius-sm)',
            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon as={LayoutGrid} size={15} color="#fff" />
          </div>
          <h1 style={{ font: '800 20px/1 var(--font-sans)', letterSpacing: '-.03em', color: 'var(--text-strong)', margin: 0 }}>
            Sign in to analyst
          </h1>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <OAuthMethod provider="google" label="Google" configured={providers.google} />
          <OAuthMethod provider="microsoft" label="Microsoft" configured={providers.microsoft} />
        </div>

        {providers.devLogin && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-muted)', font: '500 12px/1 var(--font-mono)' }}>
              <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
              dev sign-in
              <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
            </div>
            <form style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
              onSubmit={(e) => { e.preventDefault(); submit(); }}>
              <label htmlFor="dev-name" style={{ font: '600 13px/1 var(--font-sans)', color: 'var(--text-body)' }}>
                Your name
              </label>
              <input id="dev-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada Lovelace"
                style={{ height: 42, padding: '0 13px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)',
                  font: '500 15px/1 var(--font-sans)', color: 'var(--text-strong)', background: 'var(--surface-card)' }} />
              <Button disabled={!name.trim()}>Continue</Button>
            </form>
          </>
        )}

        {error && (
          <div role="alert" style={{ color: 'var(--amber-600)', font: '500 13px/1.4 var(--font-sans)' }}>{error}</div>
        )}
      </div>
    </div>
  );
}
