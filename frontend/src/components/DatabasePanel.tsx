// ── components/DatabasePanel.tsx ──────────────────────────────────────
// Feature 005: the "Databases" section of the catalog tree — list connected
// (federated) databases, detach them, and connect a new one via a small
// labelled form. Secrets are sent once on connect and never come back.
import { useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { Database, Plug, X } from 'lucide-react';
import { useCatalog } from '../stores';
import type { DatabaseEngine } from '../api/databases';
import { Icon, Badge } from './ui';

const ENGINES: { value: DatabaseEngine; label: string }[] = [
  { value: 'sqlite', label: 'SQLite' },
  { value: 'postgres', label: 'PostgreSQL' },
  { value: 'mssql', label: 'SQL Server' },
  { value: 'db2', label: 'IBM DB2' },
];

const FIELD: CSSProperties = {
  width: '100%', boxSizing: 'border-box', padding: '6px 8px',
  font: '400 12.5px/1.3 var(--font-sans)', color: 'var(--text-strong)',
  background: 'var(--surface-app, #fff)', border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--radius-sm)',
};
const LABEL: CSSProperties = {
  display: 'block', font: '600 10.5px/1 var(--font-sans)', letterSpacing: '.08em',
  textTransform: 'uppercase', color: 'var(--text-muted)', margin: '8px 0 3px',
};

function Field({ id, label, type = 'text', value, onChange }: {
  id: string; label: string; type?: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <div>
      <label htmlFor={id} style={LABEL}>{label}</label>
      <input id={id} type={type} value={value} onChange={(e) => onChange(e.target.value)} style={FIELD} />
    </div>
  );
}

function ConnectForm({ onDone }: { onDone: () => void }) {
  const connectDatabase = useCatalog((s) => s.connectDatabase);
  const [engine, setEngine] = useState<DatabaseEngine>('sqlite');
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [host, setHost] = useState('');
  const [port, setPort] = useState('');
  const [database, setDatabase] = useState('');
  const [user, setUser] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await connectDatabase({
        name, engine,
        ...(engine === 'sqlite'
          ? { path }
          : { host, port: port ? Number(port) : undefined, database, user, password }),
      });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} style={{ padding: '4px 18px 12px' }}>
      <Field id="db-conn-name" label="Connection name" value={name} onChange={setName} />
      <div>
        <label htmlFor="db-conn-engine" style={LABEL}>Database engine</label>
        <select id="db-conn-engine" value={engine} onChange={(e) => setEngine(e.target.value as DatabaseEngine)} style={FIELD}>
          {ENGINES.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}
        </select>
      </div>
      {engine === 'sqlite' ? (
        <Field id="db-conn-path" label="Database file path" value={path} onChange={setPath} />
      ) : (
        <>
          <Field id="db-conn-host" label="Host" value={host} onChange={setHost} />
          <Field id="db-conn-port" label="Port" value={port} onChange={setPort} />
          <Field id="db-conn-database" label="Database name" value={database} onChange={setDatabase} />
          <Field id="db-conn-user" label="Username" value={user} onChange={setUser} />
          <Field id="db-conn-password" label="Password" type="password" value={password} onChange={setPassword} />
        </>
      )}
      {error && (
        <div role="alert" style={{ margin: '8px 0 0', padding: '7px 9px', font: '400 12px/1.4 var(--font-sans)',
          color: 'var(--red-600, #b03a2e)', background: 'var(--red-50, #fdf0ee)', borderRadius: 'var(--radius-sm)' }}>
          {error}
        </div>
      )}
      <button type="submit" disabled={busy}
        style={{ marginTop: 10, width: '100%', padding: '7px 0', border: 'none', cursor: busy ? 'wait' : 'pointer',
          font: '600 12px/1 var(--font-sans)', color: '#fff', background: 'var(--brand)', borderRadius: 'var(--radius-md)',
          opacity: busy ? 0.6 : 1 }}>
        {busy ? 'Connecting…' : 'Connect database'}
      </button>
    </form>
  );
}

export function DatabasePanel() {
  const connections = useCatalog((s) => s.connections);
  const detachDatabase = useCatalog((s) => s.detachDatabase);
  const [open, setOpen] = useState(false);

  return (
    <div>
      {connections.map((c) => (
        <div key={c.name} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 18px' }}>
          <Icon as={Database} size={16} color="var(--brand)" />
          <span className="mono" style={{ font: '600 13px/1.2 var(--font-mono)', color: 'var(--text-strong)', flex: 1 }}>{c.name}</span>
          <Badge tone="info">{c.engine}</Badge>
          <button onClick={() => { void detachDatabase(c.name); }} aria-label={`Detach database ${c.name}`}
            style={{ display: 'inline-flex', border: 'none', background: 'transparent', cursor: 'pointer', padding: 2, color: 'var(--text-muted)' }}>
            <Icon as={X} size={14} />
          </button>
        </div>
      ))}
      <button onClick={() => setOpen((o) => !o)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '8px 18px', border: 'none',
          background: 'transparent', cursor: 'pointer', textAlign: 'left', color: 'var(--text-subtle)' }}>
        <Icon as={Plug} size={16} color="var(--text-subtle)" />
        <span style={{ font: '500 13px/1.2 var(--font-sans)', flex: 1 }}>Connect a database</span>
        <span style={{ font: '400 10px/1 var(--font-mono)' }}>{open ? '−' : '+'}</span>
      </button>
      {open && <ConnectForm onDone={() => setOpen(false)} />}
    </div>
  );
}
