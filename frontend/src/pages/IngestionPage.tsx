// ── pages/IngestionPage.tsx — the data workbench (feature 006) ─────────
// Add data (upload files + connect databases) and browse everything as a
// source-grouped tree (Files / Databases → sources → tables → columns) with
// profile stats + the semantic catalog + a per-column drilldown.
import { useState, useRef, useEffect } from 'react';
import {
  UploadCloud, FileText, CircleCheck, Table2, TriangleAlert,
  ChevronRight, ChevronDown, Braces, HelpCircle, Database, Trash2, Lock,
  Plus, Upload, Plug, Unplug,
} from 'lucide-react';
import { api } from '../api/client';
import { useCatalog, useIngestion } from '../stores';
import type { Dataset, CatalogEntry, ColumnDescription, CurationState, NormalizationState, Relationship } from '../api/types';
import { columnVM, type ColumnVM } from '../lib/adapt';
import { nfmt, roleBadge } from '../lib/format';
import { Icon, IconButton, Card, Badge, StatusPill, ProgressBar, Sparkline, EYEBROW } from '../components/ui';
import { ConnectForm } from '../components/DatabasePanel';

function ProfileCard({ col }: { col: ColumnVM }) {
  const nullTone = col.nullPercent >= 3 ? 'warning' : 'brand';
  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '12px 14px', borderBottom: '1px solid var(--border-subtle)', background: 'var(--neutral-50)' }}>
        <span className="mono" style={{ font: '600 14px/1 var(--font-mono)', color: 'var(--text-strong)' }}>{col.name}</span>
        <div style={{ display: 'flex', gap: 6 }}>
          {col.isMixed && <Badge tone="warning">Mixed</Badge>}
          {col.isNested && <Badge tone="info">Nested</Badge>}
          <Badge>{col.typeLabel}</Badge>
        </div>
      </div>
      <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {col.isMixed && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, font: '400 12px/1.4 var(--font-sans)', color: 'var(--amber-600)' }}>
            <Icon as={TriangleAlert} size={14} color="var(--amber-500)" />
            Mostly {col.dominantLabel.toLowerCase()}, widened to text — some off-type values.
          </div>
        )}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>Null rate</span>
            <span className="mono" style={{ font: '600 12px/1 var(--font-mono)', color: col.nullPercent >= 3 ? 'var(--amber-600)' : 'var(--text-strong)' }}>
              {col.nullPercent.toFixed(2)}% ({nfmt(col.nullCount)})
            </span>
          </div>
          <ProgressBar value={Math.max(col.nullPercent, col.nullPercent > 0 ? 1.5 : 0)} tone={nullTone} height={6} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>Distinct</span>
          <span className="mono" style={{ font: '600 12px/1 var(--font-mono)', color: 'var(--text-strong)' }}>{nfmt(col.distinctCount)} · {col.uniquePct}% unique</span>
        </div>
        {col.isNumeric ? (
          <>
            <div style={{ display: 'flex', gap: 14 }}>
              <div style={{ flex: 1 }}>
                <div style={{ font: '500 11px/1 var(--font-sans)', color: 'var(--text-muted)', marginBottom: 3 }}>MIN / MAX</div>
                <div className="mono" style={{ font: '600 12.5px/1.3 var(--font-mono)', color: 'var(--text-strong)' }}>{String(col.minimum)} → {String(col.maximum)}</div>
              </div>
              <div style={{ flex: 1.3 }}>
                <div style={{ font: '500 11px/1 var(--font-sans)', color: 'var(--text-muted)', marginBottom: 3 }}>QUANTILES 25 / 50 / 75</div>
                <div className="mono" style={{ font: '600 12.5px/1.3 var(--font-mono)', color: 'var(--text-strong)' }}>{String(col.q25)} · {String(col.q50)} · {String(col.q75)}</div>
              </div>
            </div>
            <div style={{ marginTop: 2 }}>
              <div style={{ font: '500 11px/1 var(--font-sans)', color: 'var(--text-muted)', marginBottom: 4 }}>DISTRIBUTION</div>
              <Sparkline data={col.hist} labels={col.histLabels} />
            </div>
          </>
        ) : (
          <div>
            {col.hist && (
              <div style={{ marginBottom: 10 }}>
                <div style={{ font: '500 11px/1 var(--font-sans)', color: 'var(--text-muted)', marginBottom: 4 }}>TOP VALUES</div>
                <Sparkline data={col.hist} labels={col.histLabels} />
              </div>
            )}
            <div style={{ font: '500 11px/1 var(--font-sans)', color: 'var(--text-muted)', marginBottom: 6 }}>SAMPLE VALUES</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {col.samples.map((v, i) => (
                <span key={i} className="mono" style={{ font: '500 12px/1 var(--font-mono)', color: v === null ? 'var(--text-subtle)' : 'var(--text-body)',
                  background: 'var(--surface-sunken)', padding: '4px 8px', borderRadius: 'var(--radius-sm)' }}>{v === null ? '∅ null' : String(v)}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ── source-grouped tree (Files / Databases → source → table → column) ── */
type Groups = { key: string; datasets: Dataset[] }[];

function group(datasets: Dataset[]): Groups {
  const map = new Map<string, Dataset[]>();
  for (const d of datasets) {
    const arr = map.get(d.group) ?? [];
    arr.push(d);
    map.set(d.group, arr);
  }
  return [...map.entries()].map(([key, ds]) => ({ key, datasets: ds }));
}

function TableNode({ d, catalog }: { d: Dataset; catalog: Record<string, CatalogEntry> }) {
  const { expanded, toggleExpand, selectColumn, selectedColumn, detailDatasetId, setDetail } = useCatalog();
  const open = !!expanded[d.id];
  // Fix 3: column nodes come from the PROFILE (always present), with the role
  // badge from the catalog when it exists (files may not be LLM-catalogued).
  const catCols = catalog[d.id]?.columns || [];
  const cols = d.profile.columns.map((pc) => ({
    name: pc.name,
    role: catCols.find((c) => c.name === pc.name)?.role,
  }));
  const isDetail = d.id === detailDatasetId;
  const needsReview = (catalog[d.id]?.clarifications || []).length > 0;
  const status = d.status === 'complete' ? 'ready' : 'running';
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', background: isDetail ? 'var(--brand-subtle)' : 'transparent' }}>
        <button aria-label={`Toggle columns of ${d.fileName}`} onClick={() => toggleExpand(d.id)}
          style={{ display: 'flex', alignItems: 'center', border: 'none', background: 'transparent', cursor: 'pointer', padding: '7px 2px 7px 30px' }}>
          <Icon as={open ? ChevronDown : ChevronRight} size={14} color="var(--text-muted)" />
        </button>
        <button aria-label={`Open table ${d.entity}`} onClick={() => setDetail(d.id)}
          style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 7, padding: '7px 16px 7px 2px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}>
          <Icon as={Table2} size={15} color={isDetail ? 'var(--brand)' : 'var(--text-muted)'} />
          <span className="mono" style={{ font: '600 12.5px/1.2 var(--font-mono)', color: 'var(--text-strong)', flex: 1 }}>{d.entity}</span>
          {needsReview && <Icon as={HelpCircle} size={13} color="var(--amber-500)" />}
          {d.catalogStatus === 'pending'
            ? <Badge tone="info">Cataloguing…</Badge>
            : d.queryable
            ? <StatusPill status={status}>{status === 'ready' ? 'Ready' : 'Profiling'}</StatusPill>
            : <Badge tone="warning"><Icon as={Lock} size={9} style={{ marginRight: 3 }} />Not queryable</Badge>}
        </button>
      </div>
      {open && (
        <div>
          {cols.map((c) => {
            const sel = selectedColumn?.ds === d.id && selectedColumn?.name === c.name;
            const rb = c.role ? roleBadge(c.role) : null;
            return (
              <button key={c.name} onClick={() => selectColumn(d.id, c.name)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '5px 16px 5px 52px', border: 'none',
                  borderLeft: `2px solid ${sel ? 'var(--brand)' : 'transparent'}`, background: sel ? 'var(--brand-subtle)' : 'transparent',
                  cursor: 'pointer', textAlign: 'left' }}>
                <span className="mono" style={{ font: '500 12px/1.2 var(--font-mono)', color: sel ? 'var(--text-brand)' : 'var(--text-body)', flex: 1 }}>{c.name}</span>
                {rb && <Badge tone={rb.tone}>{rb.label}</Badge>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function GroupNode({ g, catalog, defaultOpen }: { g: { key: string; datasets: Dataset[] }; catalog: Record<string, CatalogEntry>; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button aria-label={`Toggle source ${g.key}`} onClick={() => setOpen((o) => !o)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 6, padding: '7px 18px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}>
        <Icon as={open ? ChevronDown : ChevronRight} size={14} color="var(--text-muted)" />
        <span style={{ font: '700 12px/1.2 var(--font-sans)', color: 'var(--text-strong)', flex: 1 }}>{g.key}</span>
        <span className="mono" style={{ font: '400 10.5px/1 var(--font-mono)', color: 'var(--text-subtle)' }}>{g.datasets.length}</span>
      </button>
      {open && g.datasets.map((d) => <TableNode key={d.id} d={d} catalog={catalog} />)}
    </div>
  );
}

/* ── add-data menu: the "+" in the nav header (upload / connect DB) ── */
function AddMenu() {
  const startIngestion = useIngestion((s) => s.startIngestion);
  const [menu, setMenu] = useState<null | 'menu' | 'connect'>(null);
  // Say when cataloguing runs WITHOUT AI (profile-derived descriptions only)
  // instead of degrading silently — checked when the menu opens, at the
  // moment the user is about to add data.
  const [noAiCatalog, setNoAiCatalog] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const openMenu = () => {
    setMenu((m) => (m ? null : 'menu'));
    api.health().then((h) => setNoAiCatalog(h.catalog === 'off')).catch(() => setNoAiCatalog(false));
  };
  return (
    <div style={{ position: 'relative' }}>
      <input ref={input} type="file" accept=".csv,.tsv,.xlsx,.xls,.json" style={{ display: 'none' }}
        aria-label="Choose a file to upload"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) startIngestion(f); e.target.value = ''; setMenu(null); }} />
      <IconButton as={Plus} label="Add data" onClick={openMenu} />
      {menu === 'menu' && (
        <div style={{ position: 'absolute', top: 38, right: 0, zIndex: 10, width: noAiCatalog ? 230 : 190, background: 'var(--surface-card)',
          border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-md)', padding: 5 }}>
          <button aria-label="Upload a file" onClick={() => input.current?.click()}
            style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', borderRadius: 'var(--radius-sm)', textAlign: 'left', font: '500 13px/1 var(--font-sans)', color: 'var(--text-strong)' }}>
            <Icon as={Upload} size={15} color="var(--text-muted)" /> Upload a file
          </button>
          <button aria-label="Connect a database" onClick={() => setMenu('connect')}
            style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', borderRadius: 'var(--radius-sm)', textAlign: 'left', font: '500 13px/1 var(--font-sans)', color: 'var(--text-strong)' }}>
            <Icon as={Plug} size={15} color="var(--text-muted)" /> Connect a database
          </button>
          {noAiCatalog && (
            <div role="note" aria-label="Cataloguing without AI"
              style={{ display: 'flex', gap: 7, margin: '5px 3px 3px', padding: '8px 9px', borderTop: '1px solid var(--border-subtle)', font: '400 11.5px/1.45 var(--font-sans)', color: 'var(--amber-600)' }}>
              <Icon as={TriangleAlert} size={13} color="var(--amber-500)" />
              <span>
                Cataloguing without AI — new data gets profile-derived descriptions.
                Set <span className="mono">ANTHROPIC_API_KEY</span> or <span className="mono">CLAUDE_CODE_OAUTH_TOKEN</span> for semantic descriptions.
              </span>
            </div>
          )}
        </div>
      )}
      {menu === 'connect' && (
        <div style={{ position: 'absolute', top: 38, right: 0, zIndex: 10, width: 250, background: 'var(--surface-card)',
          border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-md)' }}>
          <ConnectForm onDone={() => setMenu(null)} />
        </div>
      )}
    </div>
  );
}

function SourceTree() {
  const { datasets, catalog } = useCatalog();
  const uploads = useIngestion((s) => s.uploads);
  const files = group(datasets.filter((d) => d.sourceKind === 'file'));
  const dbs = group(datasets.filter((d) => d.sourceKind === 'database'));
  return (
    <aside style={{ width: 288, flex: 'none', overflow: 'auto', borderRight: '1px solid var(--border-subtle)', background: 'var(--surface-card)', padding: '18px 0' }}>
      <div style={{ padding: '0 14px 14px 18px', display: 'flex', alignItems: 'center', gap: 9 }}>
        <div style={{ width: 22, height: 22, background: 'var(--brand)', borderRadius: 2, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon as={Braces} size={12} color="#fff" /></div>
        <span style={{ font: '700 12px/1 var(--font-sans)', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--text-strong)', flex: 1 }}>Catalog</span>
        <AddMenu />
      </div>
      {uploads.length > 0 && (
        <div style={{ padding: '0 18px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {uploads.map((u) => (
            <div key={u.name}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, font: '500 11.5px/1.2 var(--font-mono)',
                color: u.status === 'failed' ? 'var(--amber-600)' : 'var(--text-muted)' }}>
                <Icon as={u.status === 'failed' ? TriangleAlert : FileText} size={12} color={u.status === 'failed' ? 'var(--amber-600)' : 'var(--text-subtle)'} />
                <span style={{ flex: 1 }}>{u.fileName}</span>
                <span>{u.status === 'failed' ? 'Failed' : u.status === 'complete' ? '✓' : `${Math.round(u.progress)}%`}</span>
              </div>
              {u.status === 'failed' && u.error && (
                <div style={{ padding: '3px 0 0 19px', font: '400 11px/1.4 var(--font-sans)', color: 'var(--text-body)' }}>{u.error}</div>
              )}
            </div>
          ))}
        </div>
      )}

      <div style={{ padding: '0 18px', display: 'flex', alignItems: 'center', gap: 7, ...EYEBROW, margin: '4px 0 6px' }}>
        <Icon as={FileText} size={12} color="var(--text-subtle)" /> Files
      </div>
      {files.length === 0
        ? <div style={{ padding: '2px 18px 8px', font: '400 12px/1.4 var(--font-sans)', color: 'var(--text-subtle)' }}>No files yet — upload one to begin.</div>
        : files.map((g) => <GroupNode key={g.key} g={g} catalog={catalog} defaultOpen />)}

      <div style={{ padding: '0 18px', display: 'flex', alignItems: 'center', gap: 7, ...EYEBROW, margin: '16px 0 6px' }}>
        <Icon as={Database} size={12} color="var(--text-subtle)" /> Databases
      </div>
      {dbs.length === 0
        ? <div style={{ padding: '2px 18px 8px', font: '400 12px/1.4 var(--font-sans)', color: 'var(--text-subtle)' }}>No databases connected.</div>
        : dbs.map((g) => <GroupNode key={g.key} g={g} catalog={catalog} defaultOpen />)}
    </aside>
  );
}

/* ── delete affordance: two-step inline confirm ───────────────────── */
function DeleteDataset({ id }: { id: string }) {
  const remove = useCatalog((s) => s.remove);
  const [arm, setArm] = useState(false);
  if (!arm) return <IconButton as={Trash2} label={`Delete dataset ${id}`} onClick={() => setArm(true)} />;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <button onClick={() => remove(id)} aria-label={`Confirm delete ${id}`}
        style={{ font: '600 12px/1 var(--font-sans)', color: '#fff', background: 'var(--red-500, #c0392b)',
          border: 'none', borderRadius: 'var(--radius-md)', padding: '6px 10px', cursor: 'pointer' }}>
        Delete dataset?
      </button>
      <button onClick={() => setArm(false)} aria-label="Cancel delete"
        style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--text-muted)', background: 'transparent',
          border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: '6px 10px', cursor: 'pointer' }}>
        Cancel
      </button>
    </span>
  );
}

/* ── disconnect a database (from the DB table's detail pane) ───────── */
function DisconnectDatabase({ connection }: { connection: string }) {
  const detach = useCatalog((s) => s.detachDatabase);
  const [arm, setArm] = useState(false);
  if (!arm) return (
    <button aria-label={`Disconnect database ${connection}`} onClick={() => setArm(true)}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, font: '600 12px/1 var(--font-sans)', color: 'var(--text-muted)',
        background: 'transparent', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: '6px 10px', cursor: 'pointer' }}>
      <Icon as={Unplug} size={13} /> Disconnect
    </button>
  );
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <button onClick={() => { void detach(connection); }} aria-label={`Confirm disconnect ${connection}`}
        style={{ font: '600 12px/1 var(--font-sans)', color: '#fff', background: 'var(--red-500, #c0392b)', border: 'none', borderRadius: 'var(--radius-md)', padding: '6px 10px', cursor: 'pointer' }}>
        Disconnect "{connection}"?
      </button>
      <button onClick={() => setArm(false)} aria-label="Cancel disconnect"
        style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--text-muted)', background: 'transparent', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: '6px 10px', cursor: 'pointer' }}>
        Cancel
      </button>
    </span>
  );
}

/* ── relationships (feature 009): declared/inferred + required/optional ── */
function RelBadges({ r }: { r: Relationship }) {
  return (
    <>
      <Badge tone={r.origin === 'declared' ? 'info' : 'neutral'}>{r.origin}</Badge>
      <Badge tone={r.joinType === 'required' ? 'brand' : 'warning'}>{r.joinType}</Badge>
    </>
  );
}

// Composite keys show all their columns (e.g. "pa, pb"); single-column is unchanged.
const childCols = (r: Relationship) => [r.childColumn, ...(r.extraColumns ?? []).map((p) => p[0])].join(', ');
const parentCols = (r: Relationship) => [r.parentColumn, ...(r.extraColumns ?? []).map((p) => p[1])].join(', ');

function RelationshipsBlock({ table, rels }: { table: string; rels: Relationship[] }) {
  const outgoing = rels.filter((r) => r.childTable === table);
  const incoming = rels.filter((r) => r.parentTable === table && r.childTable !== table);
  if (outgoing.length === 0 && incoming.length === 0) return null;
  const row = { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', background: 'var(--surface-card)' } as const;
  const monoRef = { font: '600 12.5px/1.2 var(--font-mono)', color: 'var(--text-strong)' } as const;
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{ ...EYEBROW, marginBottom: 10 }}>Relationships</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {outgoing.map((r, i) => (
          <div key={`out-${i}`} aria-label={`Relationship ${r.childColumn} references ${r.parentTable}`} style={row}>
            <span className="mono" style={monoRef}>{childCols(r)}</span>
            <Icon as={ChevronRight} size={13} color="var(--text-muted)" />
            <span className="mono" style={monoRef}>{r.parentTable}.{parentCols(r)}</span>
            <span style={{ flex: 1 }} />
            <RelBadges r={r} />
          </div>
        ))}
        {incoming.map((r, i) => (
          <div key={`in-${i}`} aria-label={`Referenced by ${r.childTable}`} style={row}>
            <span style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>Referenced by</span>
            <span className="mono" style={monoRef}>{r.childTable}.{childCols(r)}</span>
            <span style={{ flex: 1 }} />
            <RelBadges r={r} />
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── column drilldown (profile + semantic description + role + FK) ──── */
/* ── catalog curation (feature 016): answer clarifications, suggest
   corrections. The user's input is GROUND TRUTH; the agent completes the
   analysis within the column + own-table blast radius. ── */
function ClarificationForm({ dsId, q, onDone }: {
  dsId: string; q: { question: string; options: string[]; column?: string | null };
  onDone: (s: CurationState) => void;
}) {
  const [choice, setChoice] = useState<string | null>(null);
  const [custom, setCustom] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const answer = choice === '__other__' ? custom : choice;
  const submit = () => {
    if (!answer || !q.column) return;
    setBusy(true); setError(null);
    api.answerClarification(dsId, q.column, answer)
      .then(onDone)
      .catch((e) => setError(e.message || 'The answer could not be applied.'))
      .finally(() => setBusy(false));
  };
  return (
    <div aria-label={`Clarification about ${q.column ?? 'the table'}`}
      style={{ padding: '12px 13px', border: '1px solid var(--amber-100)', borderRadius: 'var(--radius-md)', background: 'var(--amber-100)' }}>
      {q.column && <div className="mono" style={{ font: '600 11px/1 var(--font-mono)', color: 'var(--amber-600)', marginBottom: 6 }}>{q.column}</div>}
      <div style={{ font: '500 13px/1.45 var(--font-sans)', color: 'var(--text-strong)', marginBottom: 9 }}>{q.question}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
        {q.options.map((o) => (
          <label key={o} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px', borderRadius: 'var(--radius-md)',
            border: `1px solid ${choice === o ? 'var(--brand)' : 'var(--border-default)'}`, background: 'var(--surface-card)', cursor: 'pointer',
            font: '500 12.5px/1.4 var(--font-sans)', color: 'var(--text-body)' }}>
            <input type="radio" name={`clar-${q.column}`} checked={choice === o} onChange={() => setChoice(o)} style={{ marginTop: 2 }} />
            {o}
          </label>
        ))}
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 'var(--radius-md)',
          border: `1px solid ${choice === '__other__' ? 'var(--brand)' : 'var(--border-default)'}`, background: 'var(--surface-card)', cursor: 'pointer',
          font: '500 12.5px/1.4 var(--font-sans)', color: 'var(--text-body)' }}>
          <input type="radio" name={`clar-${q.column}`} checked={choice === '__other__'} onChange={() => setChoice('__other__')} />
          Something else:
          <input aria-label="Custom answer" value={custom} onFocus={() => setChoice('__other__')} onChange={(e) => setCustom(e.target.value)}
            placeholder="describe the meaning in your words"
            style={{ flex: 1, height: 26, padding: '0 8px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', font: '400 12.5px/1 var(--font-sans)' }} />
        </label>
      </div>
      {error && <div role="alert" style={{ font: '500 12px/1.4 var(--font-sans)', color: 'var(--amber-600)', marginBottom: 8 }}>{error}</div>}
      <button aria-label="Submit answer" disabled={!answer || busy} onClick={submit}
        style={{ padding: '7px 13px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff',
          cursor: !answer || busy ? 'default' : 'pointer', opacity: !answer || busy ? 0.6 : 1, font: '600 12px/1 var(--font-sans)' }}>
        {busy ? 'Completing analysis…' : 'Submit answer'}
      </button>
    </div>
  );
}

function CorrectionControl({ dsId, column, onDone }: {
  dsId: string; column: string | null; onDone: (s: CurationState) => void;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = () => {
    if (!note.trim()) return;
    setBusy(true);
    api.suggestCorrection(dsId, column, note.trim())
      .then((s) => { onDone(s); setOpen(false); setNote(''); })
      .catch(() => {})
      .finally(() => setBusy(false));
  };
  if (!open) {
    return (
      <button aria-label={column ? `Suggest a correction for ${column}` : 'Suggest a correction for the table'}
        onClick={() => setOpen(true)}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid var(--border-default)', background: 'transparent',
          borderRadius: 'var(--radius-md)', padding: '4px 9px', cursor: 'pointer', font: '600 11.5px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
        Suggest a correction
      </button>
    );
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <input aria-label="Correction" autoFocus value={note} onChange={(e) => setNote(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()} placeholder="what does this actually mean?"
        style={{ width: 260, height: 28, padding: '0 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 12.5px/1 var(--font-sans)' }} />
      <button aria-label="Submit correction" disabled={busy || !note.trim()} onClick={submit}
        style={{ border: 'none', background: 'var(--brand)', color: '#fff', borderRadius: 'var(--radius-md)', padding: '6px 11px',
          cursor: 'pointer', font: '600 12px/1 var(--font-sans)', opacity: busy ? 0.6 : 1 }}>Apply</button>
    </span>
  );
}

/* ── normalization proposal / applied-rule cards (feature 013) ──────
   The ONLY way a rule takes effect is the Approve button here — proposals
   are never silently applied (charter invariant). */
function NormalizationBlock({ column, norm, act }: {
  column: string;
  norm: NormalizationState | null;
  act: (ruleId: string, action: 'approve' | 'dismiss' | 'revoke') => void;
}) {
  const proposal = norm?.proposals.find((p) => p.column === column);
  const applied = norm?.applied.find((p) => p.column === column);
  if (!proposal && !applied) return null;
  const btn = (label: string, onClick: () => void, primary = false) => (
    <button aria-label={label} onClick={onClick}
      style={{ padding: '6px 12px', border: primary ? 'none' : '1px solid var(--border-default)', borderRadius: 'var(--radius-md)',
        background: primary ? 'var(--brand)' : 'transparent', color: primary ? '#fff' : 'var(--text-body)',
        cursor: 'pointer', font: '600 12px/1 var(--font-sans)' }}>{label.split(' ')[0]}</button>
  );
  return (
    <div style={{ marginBottom: 14 }}>
      {proposal && (
        <div aria-label={`Normalization proposal for ${column}`}
          style={{ padding: '12px 13px', border: '1px solid var(--amber-100)', borderRadius: 'var(--radius-md)', background: 'var(--amber-100)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Icon as={TriangleAlert} size={14} color="var(--amber-500)" />
            <span style={{ font: '600 12px/1 var(--font-sans)', letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--amber-600)' }}>Normalization proposal</span>
          </div>
          <div style={{ font: '500 13px/1.5 var(--font-sans)', color: 'var(--text-strong)', marginBottom: 9 }}>{proposal.description}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 11 }}>
            {proposal.groups.flatMap((g) => g.variants).map((v) => (
              <span key={v.value} className="mono" style={{ font: '500 12px/1 var(--font-mono)', color: 'var(--text-body)',
                background: 'var(--surface-card)', border: '1px solid var(--border-default)', padding: '5px 9px', borderRadius: 'var(--radius-full)' }}>
                {JSON.stringify(v.value)} · {v.rows} {v.rows === 1 ? 'row' : 'rows'}
              </span>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {btn('Approve normalization proposal', () => act(proposal.ruleId, 'approve'), true)}
            {btn('Dismiss normalization proposal', () => act(proposal.ruleId, 'dismiss'))}
          </div>
        </div>
      )}
      {applied && (
        <div aria-label={`Applied normalization for ${column}`}
          style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 13px', border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)', background: 'var(--neutral-50)', marginTop: proposal ? 8 : 0 }}>
          <Badge tone="success">Applied</Badge>
          <span style={{ flex: 1, font: '400 12.5px/1.45 var(--font-sans)', color: 'var(--text-body)' }}>{applied.description}</span>
          {btn('Revoke normalization rule', () => act(applied.ruleId, 'revoke'))}
        </div>
      )}
    </div>
  );
}

function ColumnDrilldown({ d, col, rels, norm, act, curation, onCurated }: {
  d: Dataset; col: ColumnDescription | undefined; rels: Relationship[];
  norm: NormalizationState | null;
  act: (ruleId: string, action: 'approve' | 'dismiss' | 'revoke') => void;
  curation: CurationState | null;
  onCurated: (s: CurationState) => void;
}) {
  const { selectedColumn } = useCatalog();
  const profile = d.profile.columns.find((c) => c.name === selectedColumn?.name);
  if (!profile) return null;
  const rb = col ? roleBadge(col.role) : null;
  const fk = rels.find((r) => r.childTable === d.entity && r.childColumn === profile.name)
    ?? rels.find((r) => r.childColumn === profile.name && r.childTable !== d.entity && r.parentTable !== d.entity);
  return (
    <Card style={{ padding: 18, marginBottom: 22, background: 'var(--surface-card)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
        <span style={{ ...EYEBROW }}>Column drilldown</span>
        <span className="mono" style={{ font: '700 15px/1 var(--font-mono)', color: 'var(--text-strong)' }}>{profile.name}</span>
        {rb && <Badge tone={rb.tone}>{rb.label}</Badge>}
        {curation?.columns[profile.name] && (
          <span aria-label={`Human-confirmed meaning for ${profile.name}`}>
            <Badge tone="success">Confirmed</Badge>
          </span>
        )}
        <span style={{ flex: 1 }} />
        <CorrectionControl dsId={d.id} column={profile.name} onDone={onCurated} />
      </div>
      <NormalizationBlock column={profile.name} norm={norm} act={act} />
      {col && <p style={{ margin: '0 0 14px', font: '400 13px/1.55 var(--font-sans)', color: 'var(--text-body)', textWrap: 'pretty' }}>{col.description}</p>}
      {fk && (
        <div aria-label={`Column relationship referencing ${fk.parentTable}`} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, padding: '8px 12px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', background: 'var(--neutral-50)' }}>
          <span style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>References</span>
          <span className="mono" style={{ font: '600 12.5px/1.2 var(--font-mono)', color: 'var(--text-strong)' }}>{fk.parentTable}.{fk.parentColumn}</span>
          <span style={{ flex: 1 }} />
          <RelBadges r={fk} />
        </div>
      )}
      <ProfileCard col={columnVM(profile, d.profile.rowCount)} />
    </Card>
  );
}

/* ── table detail (profile + semantic catalog, merged) ────────────── */
function TableDetail() {
  const { datasets, catalog, detailDatasetId, selectedColumn, selectColumn, clearColumn } = useCatalog();
  const d = datasets.find((x) => x.id === detailDatasetId) || datasets[0];
  const dsId = d?.id;
  // Feature 013: pending/applied normalization rules for this table.
  const [norm, setNorm] = useState<NormalizationState | null>(null);
  // Feature 016: curated (human-confirmed) meanings for this table.
  const [curation, setCuration] = useState<CurationState | null>(null);
  useEffect(() => {
    if (!dsId) return;
    let live = true;
    api.getNormalization(dsId).then((s) => { if (live) setNorm(s); }).catch(() => { if (live) setNorm(null); });
    api.getCuration(dsId).then((s) => { if (live) setCuration(s); }).catch(() => { if (live) setCuration(null); });
    return () => { live = false; };
  }, [dsId]);
  const onCurated = (s: CurationState) => {
    setCuration(s);
    void useCatalog.getState().refresh();
  };
  if (!d) return null;
  const act = (ruleId: string, action: 'approve' | 'dismiss' | 'revoke') =>
    api.actOnNormalization(d.id, ruleId, action).then(setNorm).catch(() => {});
  const cat = catalog[d.id];
  const selCol = selectedColumn?.ds === d.id
    ? cat?.columns.find((c) => c.name === selectedColumn.name)
    : undefined;
  const showDrill = selectedColumn?.ds === d.id;
  const rels = cat?.relationships ?? [];

  return (
    <section style={{ flex: 1, overflow: 'auto', padding: '26px 30px' }}>
      <div style={EYEBROW}>Table detail</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '6px 0 4px' }}>
        <h2 style={{ margin: 0, font: '800 22px/1.05 var(--font-sans)', letterSpacing: '-.02em' }}>{d.name}</h2>
        {!d.queryable && (
          <Badge tone="warning"><Icon as={Lock} size={10} style={{ marginRight: 3 }} />Not yet answerable by Q&amp;A</Badge>
        )}
        <div style={{ flex: 1 }} />
        {d.sourceKind === 'database'
          ? <DisconnectDatabase connection={d.group} />
          : <DeleteDataset key={d.id} id={d.id} />}
      </div>

      <Card style={{ padding: 0, marginBottom: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid var(--border-subtle)' }}>
          <span className="mono" style={{ font: '600 15px/1 var(--font-mono)', color: 'var(--text-strong)' }}>{d.fileName}</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, font: '600 12.5px/1 var(--font-sans)', color: 'var(--green-600)' }}>
            <Icon as={CircleCheck} size={15} color="var(--green-500)" /> Profiling complete
          </span>
        </div>
        {cat?.tableDescription && (
          <p style={{ margin: 0, padding: '14px 18px 0', font: '400 13.5px/1.55 var(--font-sans)', color: 'var(--text-body)', textWrap: 'pretty' }}>{cat.tableDescription}</p>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 22, padding: '12px 18px 16px' }}>
          <span className="mono" style={{ font: '500 12.5px/1 var(--font-mono)', color: 'var(--text-muted)' }}>{nfmt(d.rowCount)} rows</span>
          <span className="mono" style={{ font: '500 12.5px/1 var(--font-mono)', color: 'var(--text-muted)' }}>{d.columnCount} columns</span>
          <span className="mono" style={{ font: '500 12.5px/1 var(--font-mono)', color: 'var(--text-muted)' }}>{d.profile.encoding || '—'}</span>
          <span style={{ flex: 1 }} />
          {d.sourceKind === 'file' && ['csv', 'parquet', 'xlsx'].map((fmt) => (
            <a key={fmt} aria-label={`Download dataset as ${fmt}`}
              href={`/api/datasets/${encodeURIComponent(d.id)}/export?format=${fmt}`}
              style={{ font: '600 11.5px/1 var(--font-sans)', letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--brand)', textDecoration: 'none' }}>
              {fmt}
            </a>
          ))}
        </div>
      </Card>

      {showDrill ? (
        <>
          <button onClick={() => clearColumn()} aria-label="Back to all columns"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 10, padding: '5px 9px', border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
            <Icon as={ChevronRight} size={13} style={{ transform: 'rotate(180deg)' }} /> All columns
          </button>
          <ColumnDrilldown d={d} col={selCol} rels={rels} norm={norm} act={act} curation={curation} onCurated={onCurated} />
        </>
      ) : (
      <>
      <RelationshipsBlock table={d.entity} rels={rels} />
      <div style={{ ...EYEBROW, marginBottom: 10 }}>Columns</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {d.profile.columns.map((pc) => {
          const desc = cat?.columns.find((c) => c.name === pc.name);
          const rb = desc ? roleBadge(desc.role) : null;
          const sel = selectedColumn?.ds === d.id && selectedColumn?.name === pc.name;
          const nullPct = (pc.nullRate * 100).toFixed(2);
          return (
            <button key={pc.name} aria-label={`Column ${pc.name}`} onClick={() => selectColumn(d.id, pc.name)}
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: '10px 12px', border: 'none', borderRadius: 'var(--radius-md)',
                background: sel ? 'var(--surface-card)' : 'transparent', boxShadow: sel ? 'var(--shadow-xs)' : 'none',
                outline: sel ? '1px solid var(--navy-100)' : 'none', cursor: 'pointer' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                <span className="mono" style={{ font: '600 13px/1 var(--font-mono)', color: 'var(--text-strong)', flex: 1 }}>{pc.name}</span>
                {norm?.proposals.some((p) => p.column === pc.name) && (
                  <span aria-label={`Normalization proposal pending for ${pc.name}`}>
                    <Badge tone="warning">Proposal</Badge>
                  </span>
                )}
                {curation?.columns[pc.name] && (
                  <span aria-label={`Human-confirmed meaning for ${pc.name}`}>
                    <Badge tone="success">Confirmed</Badge>
                  </span>
                )}
                <Badge>{pc.inferredType}</Badge>
                <span className="mono" style={{ font: '500 11.5px/1 var(--font-mono)', color: pc.nullRate >= 0.03 ? 'var(--amber-600)' : 'var(--text-muted)' }}>{nullPct}% null</span>
                {rb && <Badge tone={rb.tone}>{rb.label}</Badge>}
              </div>
              {desc && <div style={{ font: '400 12px/1.45 var(--font-sans)', color: 'var(--text-muted)', textWrap: 'pretty' }}>{desc.description}</div>}
            </button>
          );
        })}
      </div>
      </>
      )}

      {cat && cat.clarifications.length > 0 && (
        <div style={{ marginTop: 22 }}>
          <div style={{ ...EYEBROW, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Icon as={HelpCircle} size={13} color="var(--amber-500)" /> Needs review
          </div>
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {cat.clarifications.map((q, i) => (
              <ClarificationForm key={i} dsId={d.id} q={q} onDone={onCurated} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

export function IngestionPage() {
  const hasData = useCatalog((s) => s.datasets.length > 0);
  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
      <SourceTree />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {hasData
          ? <TableDetail />
          : <div style={{ margin: 'auto', textAlign: 'center', maxWidth: 360, color: 'var(--text-muted)' }}>
              <Icon as={UploadCloud} size={30} color="var(--text-subtle)" style={{ margin: '0 auto 12px' }} />
              <div style={{ font: '700 16px/1.3 var(--font-sans)', color: 'var(--text-strong)', marginBottom: 6 }}>No data yet</div>
              <div style={{ font: '400 13.5px/1.5 var(--font-sans)' }}>Use the <strong>+</strong> in the catalog rail to upload a file or connect a database.</div>
            </div>}
      </div>
    </div>
  );
}
