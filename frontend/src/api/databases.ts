// ── api/databases.ts ──────────────────────────────────────────────────
// Feature 005 wire types + calls for /api/databases (see routes/databases.py).
// Responses never carry a password — the secret stays server-side.

export type DatabaseEngine = 'sqlite' | 'postgres' | 'mssql' | 'db2';

export interface DbForeignKey {
  columns: string[];
  referencedTable: string;
  referencedColumns: string[];
}

export interface ConnectedTable {
  name: string;
  datasetId: string;
  rowCount: number;
  primaryKey: string[];
  foreignKeys: DbForeignKey[];
}

export interface DatabaseConnection {
  name: string;
  engine: DatabaseEngine;
  database?: string | null;
  host?: string | null;
  port?: number | null;
  user?: string | null;
  path?: string | null;
  tables: ConnectedTable[];
}

export interface ConnectDatabaseRequest {
  name: string;
  engine: DatabaseEngine;
  path?: string;
  host?: string;
  port?: number;
  database?: string;
  user?: string;
  password?: string; // sent once on connect; never returned
}

const JSON_HEADERS = { 'content-type': 'application/json' };

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const detail = await res.json().then((b) => b?.detail).catch(() => null);
    throw new Error(detail || `${res.status} ${res.statusText} — ${path}`);
  }
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>);
}

export const databasesApi = {
  list: () => j<DatabaseConnection[]>('/api/databases'),
  connect: (req: ConnectDatabaseRequest) =>
    j<DatabaseConnection>('/api/databases/connect', {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(req),
    }),
  detach: (name: string) =>
    j<void>(`/api/databases/${encodeURIComponent(name)}`, { method: 'DELETE' }),
};
