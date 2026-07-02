// ── pages/IngestionPage.tsx ───────────────────────────────────────────
import { useState } from 'react';
import { UploadCloud, FileText, Check, CircleCheck, Table2, TriangleAlert } from 'lucide-react';
import { useCatalog, useIngestion } from '../stores';
import { columnVM, type ColumnVM } from '../lib/adapt';
import { nfmt } from '../lib/format';
import { Icon, Card, Badge, StatusPill, ProgressBar, Sparkline, EYEBROW } from '../components/ui';

// Backend ingestion phases (repository._PHASES) → stepper labels.
const STEPS = ['Materializing to Parquet', 'Profiling columns', 'Generating catalog'];
const PHASE_IDX: Record<string, number> = { materializing: 0, profiling: 1, cataloguing: 2 };

function FileDropZone({ onUpload }: { onUpload: () => void }) {
  const [over, setOver] = useState(false);
  return (
    <div onClick={onUpload}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onUpload(); }}
      style={{ border: `1.5px dashed ${over ? 'var(--brand)' : 'var(--border-strong)'}`, borderRadius: 'var(--radius-lg)',
        background: over ? 'var(--brand-subtle)' : 'var(--surface-card)', padding: '34px 24px', textAlign: 'center',
        cursor: 'pointer', transition: 'all var(--dur-fast)' }}>
      <Icon as={UploadCloud} size={26} color="var(--text-muted)" style={{ margin: '0 auto 10px' }} />
      <div style={{ font: '700 16px/1.2 var(--font-sans)', color: 'var(--text-strong)' }}>Drop a file, or click to upload</div>
      <div style={{ font: '400 13px/1.4 var(--font-sans)', color: 'var(--text-muted)', marginTop: 5 }}>CSV · TSV · XLSX · JSON — profiling starts automatically</div>
    </div>
  );
}

function UploadCard({ up }: { up: { fileName: string; status: string; phase: string | null; progress: number } }) {
  const done = up.status === 'complete';
  const ci = done ? STEPS.length : (up.phase ? PHASE_IDX[up.phase] ?? 0 : 0);
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

export function IngestionPage() {
  const { datasets, activeProfileId, setActiveProfile } = useCatalog();
  const { uploads, startIngestion } = useIngestion();
  const active = datasets.find((d) => d.id === activeProfileId) || datasets[0];

  return (
    <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(380px,1fr) minmax(440px,1.25fr)', overflow: 'hidden' }}>
      {/* left — ingestion */}
      <section style={{ overflow: 'auto', padding: '26px 30px', borderRight: '1px solid var(--border-subtle)' }}>
        <div style={EYEBROW}>Data ingestion</div>
        <h2 style={{ margin: '6px 0 18px', font: '800 22px/1.05 var(--font-sans)', letterSpacing: '-.02em' }}>New uploads</h2>
        <FileDropZone onUpload={() => startIngestion()} />
        {uploads.length > 0 && (
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 12 }} className="ana-in">
            {uploads.map((u) => <UploadCard key={u.name} up={u} />)}
          </div>
        )}
        <div style={{ height: 1, background: 'var(--border-subtle)', margin: '26px 0 20px' }} />
        <div style={EYEBROW}>Ingested datasets</div>
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 1, border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          {datasets.map((d) => {
            const on = d.id === activeProfileId;
            return (
              <button key={d.id} onClick={() => setActiveProfile(d.id)}
                style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 15px', border: 'none',
                  borderLeft: `2px solid ${on ? 'var(--brand)' : 'transparent'}`, background: on ? 'var(--brand-subtle)' : 'var(--surface-card)',
                  cursor: 'pointer', textAlign: 'left', transition: 'background var(--dur-fast)' }}>
                <Icon as={Table2} size={17} color={on ? 'var(--brand)' : 'var(--text-muted)'} />
                <div style={{ flex: 1 }}>
                  <div className="mono" style={{ font: '600 13.5px/1.2 var(--font-mono)', color: 'var(--text-strong)' }}>{d.fileName}</div>
                  <div className="mono" style={{ font: '400 11.5px/1.3 var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>{nfmt(d.rowCount)} rows · {d.columnCount} cols</div>
                </div>
                <StatusPill status={d.status === 'complete' ? 'ready' : 'running'}>{d.status === 'complete' ? 'Ready' : 'Profiling'}</StatusPill>
              </button>
            );
          })}
        </div>
      </section>

      {/* right — autopilot profiling */}
      {active && (
        <section style={{ overflow: 'auto', padding: '26px 30px' }}>
          <div style={EYEBROW}>Autopilot profiling</div>
          <h2 style={{ margin: '6px 0 16px', font: '800 22px/1.05 var(--font-sans)', letterSpacing: '-.02em' }}>{active.name}</h2>
          <Card style={{ padding: 0, marginBottom: 22 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid var(--border-subtle)' }}>
              <span className="mono" style={{ font: '600 15px/1 var(--font-mono)', color: 'var(--text-strong)' }}>{active.fileName}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, font: '600 12.5px/1 var(--font-sans)', color: 'var(--green-600)' }}>
                <Icon as={CircleCheck} size={15} color="var(--green-500)" /> Profiling complete
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', padding: '16px 18px', gap: 12 }}>
              {[['Rows', nfmt(active.rowCount)], ['Columns', String(active.columnCount)], ['Encoding', active.profile.encoding || '—'], ['Ingested', active.ingestedAt || '—']].map(([k, v]) => (
                <div key={k}>
                  <div style={{ font: '500 11px/1 var(--font-sans)', letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 5 }}>{k}</div>
                  <div className="mono" style={{ font: '600 15px/1 var(--font-mono)', color: 'var(--text-strong)' }}>{v}</div>
                </div>
              ))}
            </div>
            {(active.profile.synthesizedHeaders || active.profile.hadDuplicateColumns) && (
              <div style={{ display: 'flex', gap: 8, padding: '0 18px 14px' }}>
                {active.profile.synthesizedHeaders && <Badge tone="warning">Headers synthesized</Badge>}
                {active.profile.hadDuplicateColumns && <Badge tone="warning">Duplicate columns disambiguated</Badge>}
              </div>
            )}
          </Card>
          <div style={{ ...EYEBROW, marginBottom: 12 }}>Column profiles</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 14 }}>
            {active.profile.columns.map((c) => <ProfileCard key={c.name} col={columnVM(c, active.profile.rowCount)} />)}
          </div>
        </section>
      )}
    </div>
  );
}
