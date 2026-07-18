// ── pages/DashboardsPage.tsx — interactive dashboards (feature 015) ──
// The agent assembles a grid of widgets from a plain-English request; a
// shared filter re-scopes every widget BEFORE aggregation, clicking a bar
// cross-filters the others, and drill-down opens the rows behind a widget.
// Viewing is fully local: run/drill execute stored, re-guarded SQL only.
import { useEffect, useState } from 'react';
import { LayoutDashboard, Trash2, ChevronLeft, X } from 'lucide-react';
import { api } from '../api/client';
import type { AnswerResult, DashboardMeta, DashboardRun } from '../api/types';
import { Icon, Card, Badge, EYEBROW } from '../components/ui';
import { BarChart, LineChart, ResultTableView, TrustTrail } from './WorkspacePage';

type Filter = { column: string; value: string };

function WidgetCard({ dashId, meta, entry, filters, onCross, onChanged, plain }: {
  dashId: string;
  meta: { widgetId: string; title: string; chartType: string };
  entry: { answer: AnswerResult | null; error: string | null; unaffectedBy: string[] };
  filters: Filter[];
  onCross: (column: string, value: string) => void;
  onChanged: () => void;
  plain?: boolean;
}) {
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const [drill, setDrill] = useState<AnswerResult | null>(null);
  const answer = entry.answer;
  const crossColumn = answer?.table?.columns?.[0];
  return (
    <Card style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--text-strong)', flex: 1 }}>{meta.title}</span>
        {entry.unaffectedBy.length > 0 && (
          <span aria-label={`Widget ${meta.title} unaffected by filter`}>
            <Badge>Not filtered</Badge>
          </span>
        )}
        {!plain && answer?.table && (answer.chartData || answer.stat) && (
          <button aria-label={`Toggle table for ${meta.title}`} onClick={() => setView(view === 'chart' ? 'table' : 'chart')}
            style={{ border: '1px solid var(--border-default)', background: 'transparent', borderRadius: 'var(--radius-md)', padding: '3px 8px', cursor: 'pointer', font: '600 11px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
            {view === 'chart' ? 'Table' : 'Chart'}
          </button>
        )}
        {!plain && <button aria-label={`Drill into ${meta.title}`}
          onClick={() => api.drillDashboard(dashId, meta.widgetId, filters).then(setDrill).catch(() => {})}
          style={{ border: '1px solid var(--border-default)', background: 'transparent', borderRadius: 'var(--radius-md)', padding: '3px 8px', cursor: 'pointer', font: '600 11px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
          Rows
        </button>}
        {!plain && <button aria-label={`Remove widget ${meta.title}`}
          onClick={() => api.removeWidget(dashId, meta.widgetId).then(onChanged).catch(() => {})}
          style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 2 }}>
          <Icon as={Trash2} size={13} color="var(--text-subtle)" />
        </button>}
      </div>
      {entry.error && (
        <div role="alert" style={{ padding: '10px 12px', border: '1px solid var(--amber-100)', background: 'var(--amber-100)', borderRadius: 'var(--radius-md)', font: '500 12.5px/1.5 var(--font-sans)', color: 'var(--amber-600)' }}>
          {entry.error}
        </div>
      )}
      {answer && view === 'chart' && answer.chartType === 'bar' && answer.chartData && (
        <BarChart result={answer} onBarClick={crossColumn ? (label) => onCross(crossColumn, label) : undefined} />
      )}
      {answer && view === 'chart' && answer.chartType === 'line' && answer.chartData && <LineChart result={answer} />}
      {answer && view === 'chart' && answer.chartType === 'stat' && answer.stat && (
        <div style={{ padding: '14px 16px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', background: 'var(--neutral-50)' }}>
          <div style={{ font: '500 11px/1 var(--font-sans)', letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 6 }}>{answer.stat.label}</div>
          <div className="mono" style={{ font: '700 30px/1 var(--font-mono)', color: 'var(--brand)' }}>{answer.stat.value}</div>
        </div>
      )}
      {answer && (view === 'table' || answer.chartType === 'none') && answer.table && (
        <ResultTableView table={answer.table} title={meta.title} />
      )}
      {!plain && answer?.trustTrail && <TrustTrail trail={answer.trustTrail} />}
      {drill && (
        <div role="dialog" aria-label={`Rows behind ${meta.title}`} onClick={() => setDrill(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 40 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 720, maxHeight: '80vh', overflow: 'auto', background: 'var(--surface-card)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ font: '700 14px/1 var(--font-sans)', flex: 1 }}>Rows behind: {meta.title}</span>
              <button aria-label="Close drill" onClick={() => setDrill(null)} style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}><Icon as={X} size={16} /></button>
            </div>
            {drill.table && <ResultTableView table={drill.table} title={`rows-${meta.widgetId}`} />}
          </div>
        </div>
      )}
    </Card>
  );
}

function OpenDashboard({ meta, onBack }: { meta: DashboardMeta; onBack: () => void }) {
  const [run, setRun] = useState<DashboardRun | null>(null);
  const [filters, setFilters] = useState<Filter[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [edit, setEdit] = useState('');
  const [editBusy, setEditBusy] = useState(false);
  const [editAsk, setEditAsk] = useState<{ question: string; options: string[] } | null>(null);
  const [printing, setPrinting] = useState(false);
  const refresh = (f: Filter[]) => api.runDashboard(meta.dashboardId, f).then(setRun).catch(() => {});
  useEffect(() => { refresh([]); }, [meta.dashboardId]);
  const apply = (f: Filter[]) => { setFilters(f); refresh(f); };
  const dash = run?.dashboard ?? meta;
  const applyEdit = (text: string) => {
    if (!text.trim()) return;
    setEditBusy(true); setEditAsk(null);
    api.editDashboard(meta.dashboardId, text.trim())
      .then((out) => {
        if (out.clarification) { setEditAsk(out.clarification); return; }
        setEdit(''); refresh(filters);
      })
      .catch(() => {})
      .finally(() => setEditBusy(false));
  };
  if (printing) {
    return (
      <div>
        <div className="no-print" style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <button aria-label="Print" onClick={() => window.print()}
            style={{ padding: '7px 14px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 12.5px/1 var(--font-sans)' }}>Print</button>
          <button aria-label="Exit print preview" onClick={() => setPrinting(false)}
            style={{ padding: '7px 14px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12.5px/1 var(--font-sans)', color: 'var(--text-body)' }}>Exit preview</button>
        </div>
        <h2 style={{ margin: '0 0 14px', font: '800 20px/1.05 var(--font-sans)' }}>{dash.name}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 14 }}>
          {dash.widgets.map((w) => {
            const entry = run?.widgets[w.widgetId];
            if (!entry) return null;
            return (
              <WidgetCard key={w.widgetId} dashId={dash.dashboardId} meta={w} entry={entry}
                filters={filters} onCross={() => {}} onChanged={() => {}} plain />
            );
          })}
        </div>
      </div>
    );
  }
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <button aria-label="Back to all dashboards" onClick={onBack}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
          <Icon as={ChevronLeft} size={13} /> All dashboards
        </button>
        <h2 style={{ margin: 0, font: '800 19px/1.05 var(--font-sans)', flex: 1 }}>{dash.name}</h2>
        <button aria-label="Print preview" onClick={() => setPrinting(true)}
          style={{ padding: '5px 11px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
          Print preview
        </button>
        {dash.filters.map((f) => (
          <span key={f.column} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <input aria-label={`Filter ${f.label}`} placeholder={f.label} value={draft[f.column] ?? ''}
              onChange={(e) => setDraft({ ...draft, [f.column]: e.target.value })}
              onKeyDown={(e) => e.key === 'Enter' && draft[f.column] && apply([...filters.filter((x) => x.column !== f.column), { column: f.column, value: draft[f.column] }])}
              style={{ width: 110, height: 28, padding: '0 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 12px/1 var(--font-sans)' }} />
          </span>
        ))}
      </div>
      {filters.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {filters.map((f) => (
            <span key={f.column} aria-label={`Active filter ${f.column} ${f.value}`}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', background: 'var(--brand-subtle)', color: 'var(--brand)', borderRadius: 'var(--radius-full)', font: '600 12px/1 var(--font-sans)' }}>
              {f.column} = {f.value}
              <button aria-label={`Clear filter ${f.column}`} onClick={() => apply(filters.filter((x) => x.column !== f.column))}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', display: 'inline-flex', padding: 0 }}>
                <Icon as={X} size={12} color="var(--brand)" />
              </button>
            </span>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, maxWidth: 640, marginBottom: 14 }}>
        <input aria-label="Edit dashboard request" value={edit} onChange={(e) => setEdit(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && applyEdit(edit)}
          placeholder='edit by prompt, e.g. "add a widget showing average salary by department"'
          style={{ flex: 1, height: 34, padding: '0 11px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 13px/1 var(--font-sans)' }} />
        <button aria-label="Apply dashboard edit" disabled={editBusy || !edit.trim()} onClick={() => applyEdit(edit)}
          style={{ padding: '0 14px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 12.5px/1 var(--font-sans)', opacity: editBusy ? 0.6 : 1 }}>
          {editBusy ? 'Editing…' : 'Apply edit'}
        </button>
      </div>
      {editAsk && (
        <Card style={{ maxWidth: 640, padding: 14, marginBottom: 12 }}>
          <div style={{ font: '700 11px/1 var(--font-sans)', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--brand)', marginBottom: 6 }}>AskQuestion</div>
          <div style={{ font: '500 13.5px/1.4 var(--font-sans)', marginBottom: 10 }}>{editAsk.question}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {editAsk.options.map((o) => (
              <button key={o} onClick={() => applyEdit(o)}
                style={{ padding: '7px 12px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-full)', background: 'var(--surface-card)', cursor: 'pointer', font: '500 12.5px/1 var(--font-sans)' }}>{o}</button>
            ))}
          </div>
        </Card>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 14 }}>
        {dash.widgets.map((w) => {
          const entry = run?.widgets[w.widgetId];
          if (!entry) return null;
          return (
            <WidgetCard key={w.widgetId} dashId={dash.dashboardId} meta={w} entry={entry} filters={filters}
              onCross={(column, value) => apply([...filters.filter((x) => x.column !== column), { column, value }])}
              onChanged={() => refresh(filters)} />
          );
        })}
      </div>
    </div>
  );
}

export function DashboardsPage() {
  const [dashboards, setDashboards] = useState<DashboardMeta[]>([]);
  const [open, setOpen] = useState<DashboardMeta | null>(null);
  const [request, setRequest] = useState('');
  const [busy, setBusy] = useState(false);
  const [ask, setAsk] = useState<{ question: string; options: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = () => api.listDashboards().then((r) => setDashboards(r.dashboards)).catch(() => {});
  useEffect(() => { refresh(); }, []);
  const create = (text: string) => {
    if (!text.trim()) return;
    setBusy(true); setError(null); setAsk(null);
    api.createDashboard(text.trim())
      .then((out) => {
        if (out.clarification) { setAsk(out.clarification); return; }
        if (out.dashboard) { setOpen(out.dashboard); refresh(); }
      })
      .catch((e) => setError(e.message || 'The dashboard could not be assembled.'))
      .finally(() => setBusy(false));
  };
  return (
    <section style={{ flex: 1, overflow: 'auto', padding: '26px 30px' }}>
      <div style={EYEBROW}>Dashboards</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '6px 0 18px' }}>
        <h2 style={{ margin: 0, font: '800 22px/1.05 var(--font-sans)', letterSpacing: '-.02em' }}>Dashboards</h2>
        <Badge>{dashboards.length}</Badge>
      </div>
      {open ? (
        <OpenDashboard meta={open} onBack={() => { setOpen(null); refresh(); }} />
      ) : (
        <>
          <div style={{ display: 'flex', gap: 8, maxWidth: 640, marginBottom: 8 }}>
            <input aria-label="Dashboard request" value={request} onChange={(e) => setRequest(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && create(request)}
              placeholder="describe the dashboard you want, e.g. a sales overview dashboard"
              style={{ flex: 1, height: 38, padding: '0 12px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 13.5px/1 var(--font-sans)' }} />
            <button aria-label="Create dashboard" disabled={busy || !request.trim()} onClick={() => create(request)}
              style={{ padding: '0 16px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 13px/1 var(--font-sans)', opacity: busy ? 0.6 : 1 }}>
              {busy ? 'Assembling…' : 'Create dashboard'}
            </button>
          </div>
          {error && <div role="alert" style={{ maxWidth: 640, marginBottom: 10, padding: '10px 12px', border: '1px solid var(--amber-100)', background: 'var(--amber-100)', borderRadius: 'var(--radius-md)', font: '500 12.5px/1.5 var(--font-sans)', color: 'var(--amber-600)' }}>{error}</div>}
          {ask && (
            <Card style={{ maxWidth: 640, padding: 14, marginBottom: 12 }}>
              <div style={{ font: '700 11px/1 var(--font-sans)', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--brand)', marginBottom: 6 }}>AskQuestion</div>
              <div style={{ font: '500 13.5px/1.4 var(--font-sans)', marginBottom: 10 }}>{ask.question}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {ask.options.map((o) => (
                  <button key={o} onClick={() => create(o)}
                    style={{ padding: '7px 12px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-full)', background: 'var(--surface-card)', cursor: 'pointer', font: '500 12.5px/1 var(--font-sans)' }}>{o}</button>
                ))}
              </div>
            </Card>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 560 }}>
            {dashboards.map((d) => (
              <Card key={d.dashboardId} style={{ padding: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <button aria-label={`Open dashboard ${d.name}`} onClick={() => setOpen(d)}
                    style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 11, padding: '13px 15px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}>
                    <Icon as={LayoutDashboard} size={17} color="var(--brand)" />
                    <span style={{ flex: 1, font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--text-strong)' }}>{d.name}</span>
                    <Badge>{d.widgets.length} widgets</Badge>
                  </button>
                  <button aria-label={`Delete dashboard ${d.name}`} onClick={() => api.deleteDashboard(d.dashboardId).then(refresh)}
                    style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: '0 14px' }}>
                    <Icon as={Trash2} size={15} color="var(--text-subtle)" />
                  </button>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
