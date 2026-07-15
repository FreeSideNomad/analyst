// ── pages/ChartsPage.tsx — saved charts (feature 014) ────────────────
// A saved chart is a saved question + validated SQL + presentation; opening
// one RE-RUNS the query against current data (never a snapshot) and renders
// through the same AnswerBody the Q&A thread uses — one renderer, one truth.
import { useEffect, useState } from 'react';
import { BarChart3, Trash2, Download, ChevronLeft } from 'lucide-react';
import { api } from '../api/client';
import type { AnswerResult, SavedChartMeta } from '../api/types';
import { Icon, Card, Badge, EYEBROW } from '../components/ui';
import { AnswerBody } from './WorkspacePage';

const BASE = import.meta.env.VITE_API_BASE ?? '';

function OpenedChart({ meta, onBack, onDeleted }: {
  meta: SavedChartMeta; onBack: () => void; onDeleted: () => void;
}) {
  const [answer, setAnswer] = useState<AnswerResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api.openChart(meta.chartId)
      .then((a) => { if (live) setAnswer(a); })
      .catch((e) => { if (live) setError(e.message || 'Could not open this chart.'); });
    return () => { live = false; };
  }, [meta.chartId]);
  return (
    <div style={{ maxWidth: 720 }}>
      <button aria-label="Back to all charts" onClick={onBack}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 12, padding: '5px 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
        <Icon as={ChevronLeft} size={13} /> All charts
      </button>
      <Card style={{ padding: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <h2 style={{ margin: 0, font: '700 17px/1.2 var(--font-sans)', color: 'var(--text-strong)', flex: 1 }}>{meta.name}</h2>
          <a aria-label="Export chart result as CSV" href={`${BASE}/api/charts/${encodeURIComponent(meta.chartId)}/export?format=csv`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: '5px 10px', font: '600 12px/1 var(--font-sans)', color: 'var(--text-body)', textDecoration: 'none' }}>
            <Icon as={Download} size={13} /> CSV
          </a>
          <a aria-label="Export chart result as Excel" href={`${BASE}/api/charts/${encodeURIComponent(meta.chartId)}/export?format=xlsx`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: '5px 10px', font: '600 12px/1 var(--font-sans)', color: 'var(--text-body)', textDecoration: 'none' }}>
            <Icon as={Download} size={13} /> Excel
          </a>
        </div>
        {error && (
          <div role="alert" style={{ padding: '12px 14px', border: '1px solid var(--amber-100)', background: 'var(--amber-100)', borderRadius: 'var(--radius-md)', font: '500 13px/1.5 var(--font-sans)', color: 'var(--amber-600)' }}>
            {error}
            <button aria-label="Delete broken chart" onClick={() => api.deleteChart(meta.chartId).then(onDeleted)}
              style={{ marginLeft: 10, border: '1px solid var(--border-default)', background: 'var(--surface-card)', borderRadius: 'var(--radius-md)', padding: '4px 9px', cursor: 'pointer', font: '600 12px/1 var(--font-sans)' }}>Delete chart</button>
          </div>
        )}
        {answer && <AnswerBody r={answer} isLast={false} />}
      </Card>
    </div>
  );
}

export function ChartsPage() {
  const [charts, setCharts] = useState<SavedChartMeta[]>([]);
  const [open, setOpen] = useState<SavedChartMeta | null>(null);
  const refresh = () => api.listCharts().then((r) => setCharts(r.charts)).catch(() => {});
  useEffect(() => { refresh(); }, []);
  return (
    <section style={{ flex: 1, overflow: 'auto', padding: '26px 30px' }}>
      <div style={EYEBROW}>Charts</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '6px 0 18px' }}>
        <h2 style={{ margin: 0, font: '800 22px/1.05 var(--font-sans)', letterSpacing: '-.02em' }}>Saved charts</h2>
        <Badge>{charts.length}</Badge>
      </div>
      {open ? (
        <OpenedChart meta={open} onBack={() => { setOpen(null); refresh(); }}
          onDeleted={() => { setOpen(null); refresh(); }} />
      ) : charts.length === 0 ? (
        <p style={{ font: '400 13.5px/1.6 var(--font-sans)', color: 'var(--text-muted)', maxWidth: 460 }}>
          No saved charts yet. Ask a question in the Query view, then use
          “Save as chart” on an answer — the chart re-runs its query against
          current data every time you open it.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 560 }}>
          {charts.map((c) => (
            <Card key={c.chartId} style={{ padding: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <button aria-label={`Open chart ${c.name}`} onClick={() => setOpen(c)}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 11, padding: '13px 15px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}>
                  <Icon as={BarChart3} size={17} color="var(--brand)" />
                  <span style={{ flex: 1 }}>
                    <span style={{ display: 'block', font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--text-strong)' }}>{c.name}</span>
                    {c.question && <span style={{ display: 'block', font: '400 12px/1.4 var(--font-sans)', color: 'var(--text-muted)', marginTop: 3 }}>{c.question}</span>}
                  </span>
                  <Badge>{c.chartType}</Badge>
                </button>
                <button aria-label={`Delete chart ${c.name}`} onClick={() => api.deleteChart(c.chartId).then(refresh)}
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: '0 14px' }}>
                  <Icon as={Trash2} size={15} color="var(--text-subtle)" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
