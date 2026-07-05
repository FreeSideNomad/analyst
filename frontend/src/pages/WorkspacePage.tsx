// ── pages/WorkspacePage.tsx — the Query surface (chat only, feature 006) ──
import { useState, useEffect, useRef } from 'react';
import {
  ChevronRight, ChevronDown, Search, Check, Send, Sparkles, Info,
} from 'lucide-react';
import type { AnswerResult, ChatMessage, ClarificationResult, TrustTrail as TrustTrailT } from '../api/types';
import { useQuery } from '../stores';
import { money } from '../lib/format';
import { Icon, Card, Button, Tag, SegmentedControl } from '../components/ui';

/* ── Q&A chat ─────────────────────────────────────────────────────── */
function BarChart({ result }: { result: AnswerResult }) {
  const ticks: number[] = [];
  for (let v = result.niceMax!; v >= 0; v -= result.tickStep!) ticks.push(v);
  return (
    <div>
      <div style={{ font: '600 15px/1.2 var(--font-sans)', color: 'var(--text-strong)', marginBottom: 12 }}>{result.chartTitle}</div>
      <div style={{ display: 'grid', gridTemplateColumns: '52px 1fr', gap: 10 }}>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: 200, textAlign: 'right' }}>
          {ticks.map((v, i) => <span key={i} className="mono" style={{ font: '400 10.5px/1 var(--font-mono)', color: 'var(--text-subtle)' }}>{money(v)}</span>)}
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, height: 200, borderLeft: '1px solid var(--border-default)', borderBottom: '1px solid var(--border-default)', padding: '0 10px' }}>
            {result.chartData!.map((d) => {
              const hl = d.label === result.highlight;
              return (
                <div key={d.label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', gap: 6, height: '100%' }}>
                  <span className="mono" style={{ font: '600 10.5px/1 var(--font-mono)', color: 'var(--text-muted)' }}>{money(d.value)}</span>
                  <div style={{ width: '62%', maxWidth: 54, height: (d.value / result.niceMax! * 100).toFixed(1) + '%',
                    background: hl ? 'var(--brand)' : 'var(--neutral-400)', borderRadius: '2px 2px 0 0', transition: 'height .5s var(--ease-standard)' }} />
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', gap: 16, padding: '8px 10px 0' }}>
            {result.chartData!.map((d) => <div key={d.label} style={{ flex: 1, textAlign: 'center', font: '500 12px/1.2 var(--font-sans)', color: 'var(--text-body)' }}>{d.label}</div>)}
          </div>
        </div>
      </div>
    </div>
  );
}

function TrustTrail({ trail, defaultOpen }: { trail: TrustTrailT; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  const [tab, setTab] = useState('assumptions');
  return (
    <div style={{ marginTop: 16, borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>
      <button onClick={() => setOpen(!open)} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', border: 'none', background: 'transparent', cursor: 'pointer', padding: 0 }}>
        <span style={{ width: 16, height: 16, borderRadius: 3, background: 'var(--amber-500)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon as={Info} size={11} color="#fff" /></span>
        <span style={{ font: '600 13px/1 var(--font-sans)', color: 'var(--text-strong)', flex: 1, textAlign: 'left' }}>Trust trail</span>
        <span style={{ font: '400 11px/1 var(--font-sans)', color: 'var(--text-subtle)' }}>assumptions · lineage · SQL</span>
        <Icon as={open ? ChevronDown : ChevronRight} size={16} color="var(--text-muted)" />
      </button>
      {open && (
        <div style={{ marginTop: 12 }} className="ana-in">
          <SegmentedControl size="sm" value={tab} onChange={setTab}
            options={[{ value: 'assumptions', label: 'Assumptions' }, { value: 'lineage', label: 'Lineage' }, { value: 'sql', label: 'SQL' }]} />
          <div style={{ marginTop: 12 }}>
            {tab === 'assumptions' && (
              <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 7 }}>
                {trail.assumptions.map((a, i) => <li key={i} style={{ font: '400 13px/1.5 var(--font-sans)', color: 'var(--text-body)' }}>{a}</li>)}
              </ul>
            )}
            {tab === 'lineage' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {trail.lineage.map((l, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 9 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--brand)', marginTop: 6, flex: 'none' }} />
                    <span className="mono" style={{ font: '400 12.5px/1.5 var(--font-mono)', color: 'var(--text-body)' }}>{l}</span>
                  </div>
                ))}
              </div>
            )}
            {tab === 'sql' && (
              <pre className="mono" style={{ margin: 0, padding: 14, background: 'var(--neutral-900)', color: '#e8eef6', borderRadius: 'var(--radius-md)',
                font: '400 12.5px/1.6 var(--font-mono)', overflow: 'auto', whiteSpace: 'pre' }}>{trail.sql}</pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// clarification options are bare strings; render "label — description" nicely.
function AskQuestion({ msg }: { msg: Extract<ChatMessage, { type: 'clarification' }> }) {
  const respond = useQuery((s) => s.respond);
  const p: ClarificationResult = msg.payload;
  return (
    <div style={{ display: 'flex', gap: 12, maxWidth: 640 }} className="ana-in">
      <div style={{ width: 30, height: 30, flex: 'none', borderRadius: '50%', background: 'var(--surface-sunken)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon as={Sparkles} size={16} color="var(--brand)" />
      </div>
      <Card style={{ padding: 16, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
          <span style={{ font: '700 11px/1 var(--font-sans)', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--brand)' }}>AskQuestion</span>
          <span style={{ font: '400 11px/1 var(--font-sans)', color: 'var(--text-subtle)' }}>· clarify before answering</span>
        </div>
        <div style={{ font: '500 14.5px/1.4 var(--font-sans)', color: 'var(--text-strong)', marginBottom: 12 }}>{p.question}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {p.options.map((o) => {
            const [head, ...rest] = o.split(' — ');
            const desc = rest.join(' — ');
            const chosen = msg.chosen === o;
            const dim = !!msg.chosen && !chosen;
            return (
              <button key={o} disabled={!!msg.chosen} onClick={() => respond(p, o)}
                style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '11px 13px', textAlign: 'left',
                  border: `1px solid ${chosen ? 'var(--brand)' : 'var(--border-default)'}`, borderRadius: 'var(--radius-md)',
                  background: chosen ? 'var(--brand-subtle)' : 'var(--surface-card)', opacity: dim ? 0.5 : 1,
                  cursor: msg.chosen ? 'default' : 'pointer', transition: 'all var(--dur-fast)' }}>
                <span style={{ width: 16, height: 16, flex: 'none', marginTop: 1, borderRadius: '50%', border: `1.5px solid ${chosen ? 'var(--brand)' : 'var(--border-strong)'}`,
                  background: chosen ? 'var(--brand)' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {chosen && <Icon as={Check} size={10} color="#fff" />}
                </span>
                <span style={{ flex: 1 }}>
                  <span className="mono" style={{ font: '600 13px/1.3 var(--font-mono)', color: 'var(--text-strong)' }}>{head}</span>
                  {desc && <span style={{ display: 'block', font: '400 12px/1.45 var(--font-sans)', color: 'var(--text-muted)', marginTop: 4 }}>{desc}</span>}
                </span>
              </button>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

function ResultMessage({ msg, isLast }: { msg: Extract<ChatMessage, { type: 'result' }>; isLast: boolean }) {
  const r = msg.result;
  return (
    <div style={{ display: 'flex', gap: 12, maxWidth: 680 }} className="ana-in">
      <div style={{ width: 30, height: 30, flex: 'none', borderRadius: '50%', background: r.abstain ? 'var(--amber-100)' : 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon as={r.abstain ? Info : Check} size={16} color={r.abstain ? 'var(--amber-600)' : '#fff'} />
      </div>
      <Card style={{ padding: 18, flex: 1 }}>
        <p style={{ margin: 0, font: '400 14.5px/1.55 var(--font-sans)', color: 'var(--text-body)', textWrap: 'pretty' }}>{r.summary}</p>
        {r.chartType === 'bar' && <div style={{ marginTop: 16 }}><BarChart result={r} /></div>}
        {r.chartType === 'stat' && r.stat && (
          <div style={{ marginTop: 16, padding: '18px 20px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', background: 'var(--neutral-50)' }}>
            <div style={{ font: '500 12px/1 var(--font-sans)', letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8 }}>{r.stat.label}</div>
            <div className="mono" style={{ font: '700 40px/1 var(--font-mono)', color: 'var(--brand)', letterSpacing: '-.02em' }}>{r.stat.value}</div>
            <div className="mono" style={{ font: '400 12.5px/1 var(--font-mono)', color: 'var(--text-muted)', marginTop: 8 }}>{r.stat.sub}</div>
          </div>
        )}
        {r.trustTrail && <TrustTrail trail={r.trustTrail} defaultOpen={isLast} />}
      </Card>
    </div>
  );
}

function Thinking() {
  return (
    <div style={{ display: 'flex', gap: 12 }} className="ana-in">
      <div style={{ width: 30, height: 30, flex: 'none', borderRadius: '50%', background: 'var(--surface-sunken)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon as={Sparkles} size={16} color="var(--brand)" />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, height: 30 }}>
        {[0, 1, 2].map((i) => <span key={i} style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--neutral-400)', animation: `ana-blink 1.2s ${i * 0.16}s infinite ease-in-out` }} />)}
        <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--text-muted)', marginLeft: 6 }}>planning against the semantic catalog…</span>
      </div>
    </div>
  );
}

function QueryChat() {
  const { messages, thinking, submit } = useQuery();
  const [text, setText] = useState('');
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => { if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight; }, [messages, thinking]);
  const send = () => { if (text.trim()) { submit(text); setText(''); } };
  const lastResultId = [...messages].reverse().find((m) => m.type === 'result')?.id;
  const suggestions = ['What is the revenue by region?', 'Who are the top 5 customers by revenue?', 'What is the average order value?'];

  return (
    <section style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--surface-page)' }}>
      <div style={{ height: 56, flex: 'none', display: 'flex', alignItems: 'center', gap: 10, padding: '0 24px', borderBottom: '1px solid var(--border-subtle)', background: 'var(--surface-card)' }}>
        <h1 style={{ margin: 0, font: '800 18px/1 var(--font-sans)', letterSpacing: '-.02em' }}>Query</h1>
        <span style={{ font: '400 12px/1.4 var(--font-sans)', color: 'var(--text-muted)' }}>Ask a plain-English question — answers span the whole workspace</span>
      </div>

      <div ref={scroller} style={{ flex: 1, overflow: 'auto', padding: '26px 28px', display: 'flex', flexDirection: 'column', gap: 22 }}>
        {messages.length === 0 && (
          <div style={{ margin: 'auto', textAlign: 'center', maxWidth: 420 }}>
            <div style={{ width: 44, height: 44, margin: '0 auto 14px', borderRadius: '50%', background: 'var(--brand-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon as={Sparkles} size={22} color="var(--brand)" />
            </div>
            <div style={{ font: '700 17px/1.3 var(--font-sans)', color: 'var(--text-strong)', marginBottom: 6 }}>Ask a question about your data</div>
            <div style={{ font: '400 13.5px/1.5 var(--font-sans)', color: 'var(--text-muted)' }}>Plain English. The agent plans against the semantic catalog, joins tables as needed, and shows its assumptions, lineage and SQL on every answer.</div>
          </div>
        )}
        {messages.map((m) => {
          if (m.type === 'user') return (
            <div key={m.id} style={{ alignSelf: 'flex-end', maxWidth: 560 }} className="ana-in">
              <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <div style={{ background: 'var(--neutral-900)', color: '#fff', padding: '10px 15px', borderRadius: 'var(--radius-lg)', font: '500 14.5px/1.4 var(--font-sans)' }}>{m.text}</div>
                <div style={{ width: 30, height: 30, flex: 'none', borderRadius: '50%', background: 'var(--navy-100)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center', font: '600 11px/1 var(--font-mono)' }}>IM</div>
              </div>
            </div>
          );
          if (m.type === 'clarification') return <AskQuestion key={m.id} msg={m} />;
          if (m.type === 'result') return <ResultMessage key={m.id} msg={m} isLast={m.id === lastResultId} />;
          return null;
        })}
        {thinking && <Thinking />}
      </div>

      <div style={{ flex: 'none', padding: '14px 24px 18px', borderTop: '1px solid var(--border-subtle)', background: 'var(--surface-card)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
          {suggestions.map((s) => <Tag key={s} onClick={() => submit(s)}>{s}</Tag>)}
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, height: 48, padding: '0 16px', background: 'var(--surface-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
            <Icon as={Search} size={17} color="var(--text-subtle)" />
            <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder="Ask across all tables — the agent joins them for you…"
              style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', font: '400 15px/1.4 var(--font-sans)', color: 'var(--text-strong)' }} />
          </div>
          <Button onClick={send} iconRight={<Icon as={Send} size={16} color="#fff" />}>Ask</Button>
        </div>
      </div>
    </section>
  );
}

export function WorkspacePage() {
  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
      <QueryChat />
    </div>
  );
}
