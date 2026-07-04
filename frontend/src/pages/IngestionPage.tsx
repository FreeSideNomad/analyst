// ── pages/IngestionPage.tsx — the data workbench (feature 006) ─────────
// Add data (upload files + connect databases) and browse everything as a
// source-grouped tree (Files / Databases → sources → tables → columns) with
// profile stats + the semantic catalog + a per-column drilldown.
import { useState, useRef } from 'react';
import {
  UploadCloud, FileText, Check, CircleCheck, Table2, TriangleAlert,
  ChevronRight, ChevronDown, Braces, HelpCircle, Database, Trash2, Lock,
} from 'lucide-react';
import { useCatalog, useIngestion } from '../stores';
import type { Dataset, CatalogEntry, ColumnDescription } from '../api/types';
import { columnVM, type ColumnVM } from '../lib/adapt';
import { nfmt, roleBadge } from '../lib/format';
import { Icon, IconButton, Card, Badge, StatusPill, ProgressBar, Sparkline, EYEBROW } from '../components/ui';
import { DatabasePanel } from '../components/DatabasePanel';

// Backend ingestion phases (repository._PHASES) → stepper labels.
const STEPS = ['Materializing to Parquet', 'Profiling columns', 'Generating catalog'];
const PHASE_IDX: Record<string, number> = { materializing: 0, profiling: 1, cataloguing: 2 };

/* ── upload zone ──────────────────────────────────────────────────── */
function FileDropZone({ onUpload }: { onUpload: (file: File) => void }) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const pick = (files: FileList | null) => { const f = files?.[0]; if (f) onUpload(f); };
  return (
    <div onClick={() => input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files); }}
      style={{ border: `1.5px dashed ${over ? 'var(--brand)' : 'var(--border-strong)'}`, borderRadius: 'var(--radius-lg)',
        background: over ? 'var(--brand-subtle)' : 'var(--surface-card)', padding: '34px 24px', textAlign: 'center',
        cursor: 'pointer', transition: 'all var(--dur-fast)' }}>
      <input ref={input} type="file" accept=".csv,.tsv,.xlsx,.xls,.json" style={{ display: 'none' }}
        aria-label="Choose a file to upload"
        onChange={(e) => { pick(e.target.files); e.target.value = ''; }} />
      <Icon as={UploadCloud} size={26} color="var(--text-muted)" style={{ margin: '0 auto 10px' }} />
      <div style={{ font: '700 16px/1.2 var(--font-sans)', color: 'var(--text-strong)' }}>Drop a file, or click to upload</div>
      <div style={{ font: '400 13px/1.4 var(--font-sans)', color: 'var(--text-muted)', marginTop: 5 }}>CSV · TSV · XLSX · JSON — profiling starts automatically</div>
    </div>
  );
}

function UploadCard({ up }: { up: { fileName: string; status: string; phase: string | null; progress: number; error?: string | null } }) {
  const done = up.status === 'complete';
  const ci = done ? STEPS.length : (up.phase ? PHASE_IDX[up.phase] ?? 0 : 0);
  if (up.status === 'failed') {
    return (
      <Card style={{ padding: 18, borderColor: 'var(--amber-100)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <Icon as={TriangleAlert} size={18} color="var(--amber-600)" />
          <span className="mono" style={{ font: '600 14px/1 var(--font-mono)', color: 'var(--text-strong)', flex: 1 }}>{up.fileName}</span>
          <span style={{ font: '600 12px/1 var(--font-sans)', color: 'var(--amber-600)' }}>Failed</span>
        </div>
        <p style={{ margin: 0, font: '400 13px/1.5 var(--font-sans)', color: 'var(--text-body)' }}>
          {up.error || 'The file could not be ingested.'}
        </p>
      </Card>
    );
  }
  return (
    <Card style={{ padding: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <Icon as={FileText} size={18} color="var(--text-muted)" />
        <span className="mono" style={{ font: '600 14px/1 var(--font-mono)', color: 'var(--text-strong)', flex: 1 }}>{up.fileName}</span>
        <span style={{ font: '600 12px/1 var(--font-sans)', color: done ? 'var(--green-600)' : 'var(--text-muted)' }}>
          {done ? 'Complete' : (STEPS[ci] || 'In progress')}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <div style={{ flex: 1 }}><ProgressBar value={done ? 100 : up.progress} tone={done ? 'success' : 'brand'} /></div>
        <span className="mono" style={{ font: '600 13px/1 var(--font-mono)', color: 'var(--text-strong)', width: 40, textAlign: 'right' }}>{done ? 100 : Math.round(up.progress)}%</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {STEPS.map((label, i) => {
          const stepDone = i < ci || done;
          const active = i === ci && !done;
          return (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <span style={{ width: 16, height: 16, borderRadius: '50%', flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: stepDone ? 'var(--brand)' : (active ? 'var(--brand-subtle)' : 'var(--surface-sunken)'),
                border: active ? '1.5px solid var(--brand)' : 'none' }}>
                {stepDone && <Icon as={Check} size={11} color="#fff" />}
                {active && <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--brand)' }} />}
              </span>
              <span style={{ font: `${active ? 600 : 400} 13px/1.2 var(--font-sans)`,
                color: stepDone ? 'var(--text-body)' : (active ? 'var(--text-strong)' : 'var(--text-subtle)') }}>{label}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ── profile card (full column stats — used in the column drilldown) ── */
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
            <div style={{ marginTop: 2 }}><Sparkline data={col.hist} /></div>
          </>
        ) : (
          <div>
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
  const cols = catalog[d.id]?.columns || [];
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
        <button aria-label={`Open table ${d.name}`} onClick={() => setDetail(d.id)}
          style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 7, padding: '7px 16px 7px 2px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}>
          <Icon as={Table2} size={15} color={isDetail ? 'var(--brand)' : 'var(--text-muted)'} />
          <span className="mono" style={{ font: '600 12.5px/1.2 var(--font-mono)', color: 'var(--text-strong)', flex: 1 }}>{d.fileName}</span>
          {needsReview && <Icon as={HelpCircle} size={13} color="var(--amber-500)" />}
          {d.queryable
            ? <StatusPill status={status}>{status === 'ready' ? 'Ready' : 'Profiling'}</StatusPill>
            : <Badge tone="warning"><Icon as={Lock} size={9} style={{ marginRight: 3 }} />Not queryable</Badge>}
        </button>
      </div>
      {open && (
        <div>
          {cols.map((c) => {
            const sel = selectedColumn?.ds === d.id && selectedColumn?.name === c.name;
            const rb = roleBadge(c.role);
            return (
              <button key={c.name} onClick={() => selectColumn(d.id, c.name)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '5px 16px 5px 52px', border: 'none',
                  borderLeft: `2px solid ${sel ? 'var(--brand)' : 'transparent'}`, background: sel ? 'var(--brand-subtle)' : 'transparent',
                  cursor: 'pointer', textAlign: 'left' }}>
                <span className="mono" style={{ font: '500 12px/1.2 var(--font-mono)', color: sel ? 'var(--text-brand)' : 'var(--text-body)', flex: 1 }}>{c.name}</span>
                <Badge tone={rb.tone}>{rb.label}</Badge>
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

function SourceTree() {
  const { datasets, catalog } = useCatalog();
  const files = group(datasets.filter((d) => d.sourceKind === 'file'));
  const dbs = group(datasets.filter((d) => d.sourceKind === 'database'));
  return (
    <aside style={{ width: 288, flex: 'none', overflow: 'auto', borderRight: '1px solid var(--border-subtle)', background: 'var(--surface-card)', padding: '18px 0' }}>
      <div style={{ padding: '0 18px 16px', display: 'flex', alignItems: 'center', gap: 9 }}>
        <div style={{ width: 22, height: 22, background: 'var(--brand)', borderRadius: 2, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon as={Braces} size={12} color="#fff" /></div>
        <span style={{ font: '700 12px/1 var(--font-sans)', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--text-strong)' }}>Semantic catalog</span>
      </div>

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

/* ── column drilldown (profile + semantic description + role) ──────── */
function ColumnDrilldown({ d, col }: { d: Dataset; col: ColumnDescription | undefined }) {
  const { selectedColumn } = useCatalog();
  const profile = d.profile.columns.find((c) => c.name === selectedColumn?.name);
  if (!profile) return null;
  const rb = col ? roleBadge(col.role) : null;
  return (
    <Card style={{ padding: 18, marginBottom: 22, background: 'var(--surface-card)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
        <span style={{ ...EYEBROW }}>Column drilldown</span>
        <span className="mono" style={{ font: '700 15px/1 var(--font-mono)', color: 'var(--text-strong)' }}>{profile.name}</span>
        {rb && <Badge tone={rb.tone}>{rb.label}</Badge>}
      </div>
      {col && <p style={{ margin: '0 0 14px', font: '400 13px/1.55 var(--font-sans)', color: 'var(--text-body)', textWrap: 'pretty' }}>{col.description}</p>}
      <ProfileCard col={columnVM(profile, d.profile.rowCount)} />
    </Card>
  );
}

/* ── table detail (profile + semantic catalog, merged) ────────────── */
function TableDetail() {
  const { datasets, catalog, detailDatasetId, selectedColumn, selectColumn } = useCatalog();
  const d = datasets.find((x) => x.id === detailDatasetId) || datasets[0];
  if (!d) return null;
  const cat = catalog[d.id];
  const selCol = selectedColumn?.ds === d.id
    ? cat?.columns.find((c) => c.name === selectedColumn.name)
    : undefined;
  const showDrill = selectedColumn?.ds === d.id;

  return (
    <section style={{ flex: 1, overflow: 'auto', padding: '26px 30px' }}>
      <div style={EYEBROW}>Table detail</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '6px 0 4px' }}>
        <h2 style={{ margin: 0, font: '800 22px/1.05 var(--font-sans)', letterSpacing: '-.02em' }}>{d.name}</h2>
        {!d.queryable && (
          <Badge tone="warning"><Icon as={Lock} size={10} style={{ marginRight: 3 }} />Not yet answerable by Q&amp;A</Badge>
        )}
        <div style={{ flex: 1 }} />
        <DeleteDataset key={d.id} id={d.id} />
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
        <div style={{ display: 'flex', gap: 22, padding: '12px 18px 16px' }}>
          <span className="mono" style={{ font: '500 12.5px/1 var(--font-mono)', color: 'var(--text-muted)' }}>{nfmt(d.rowCount)} rows</span>
          <span className="mono" style={{ font: '500 12.5px/1 var(--font-mono)', color: 'var(--text-muted)' }}>{d.columnCount} columns</span>
          <span className="mono" style={{ font: '500 12.5px/1 var(--font-mono)', color: 'var(--text-muted)' }}>{d.profile.encoding || '—'}</span>
        </div>
      </Card>

      {showDrill && <ColumnDrilldown d={d} col={selCol} />}

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
                <Badge>{pc.inferredType}</Badge>
                <span className="mono" style={{ font: '500 11.5px/1 var(--font-mono)', color: pc.nullRate >= 0.03 ? 'var(--amber-600)' : 'var(--text-muted)' }}>{nullPct}% null</span>
                {rb && <Badge tone={rb.tone}>{rb.label}</Badge>}
              </div>
              {desc && <div style={{ font: '400 12px/1.45 var(--font-sans)', color: 'var(--text-muted)', textWrap: 'pretty' }}>{desc.description}</div>}
            </button>
          );
        })}
      </div>

      {cat && cat.clarifications.length > 0 && (
        <div style={{ marginTop: 22 }}>
          <div style={{ ...EYEBROW, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Icon as={HelpCircle} size={13} color="var(--amber-500)" /> Needs review
          </div>
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {cat.clarifications.map((q, i) => (
              <div key={i} style={{ padding: '12px 13px', border: '1px solid var(--amber-100)', borderRadius: 'var(--radius-md)', background: 'var(--amber-100)' }}>
                {q.column && <div className="mono" style={{ font: '600 11px/1 var(--font-mono)', color: 'var(--amber-600)', marginBottom: 6 }}>{q.column}</div>}
                <div style={{ font: '500 13px/1.45 var(--font-sans)', color: 'var(--text-strong)', marginBottom: 9 }}>{q.question}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {q.options.map((o, k) => (
                    <span key={k} style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--text-body)', background: 'var(--surface-card)',
                      border: '1px solid var(--border-default)', padding: '6px 10px', borderRadius: 'var(--radius-full)' }}>{o}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

/* ── add data (upload + connect a database) ───────────────────────── */
function AddData() {
  const { uploads, startIngestion } = useIngestion();
  return (
    <div style={{ padding: '22px 30px 6px', borderBottom: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 22, alignItems: 'start' }}>
        <div>
          <div style={EYEBROW}>Add data — upload a file</div>
          <div style={{ marginTop: 10 }}><FileDropZone onUpload={(file) => startIngestion(file)} /></div>
          {uploads.length > 0 && (
            <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 12 }} className="ana-in">
              {uploads.map((u) => <UploadCard key={u.name} up={u} />)}
            </div>
          )}
        </div>
        <div>
          <div style={EYEBROW}>Add data — connect a database</div>
          <Card style={{ padding: '10px 0 6px', marginTop: 10 }}>
            <DatabasePanel />
          </Card>
        </div>
      </div>
    </div>
  );
}

export function IngestionPage() {
  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
      <SourceTree />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <AddData />
        <TableDetail />
      </div>
    </div>
  );
}
