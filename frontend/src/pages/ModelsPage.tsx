// ── pages/ModelsPage.tsx — guided predictive models (feature 012) ────
// A person who writes no code trains a model as a sequence of DECISIONS:
// pick real data from the gallery, choose what to predict, curate the
// agent's feature proposals (each with a plain-language reason), train
// locally, read an honest evaluation. Predictions land as ordinary
// datasets; the agent never writes code — a committed trainer does it all.
import { useEffect, useState } from 'react';
import { Brain, Network, Trash2, ChevronLeft, Download } from 'lucide-react';
import { api } from '../api/client';
import type { ModelSample, ModelTask, RelationalBundle, RelationalTask } from '../api/types';
import { Icon, Card, Badge, EYEBROW } from '../components/ui';
import { useCatalog } from '../stores';

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span className="mono" style={{ width: 130, font: '500 12px/1 var(--font-mono)', color: 'var(--text-body)' }}>{label}</span>
      <div style={{ flex: 1, height: 8, background: 'var(--neutral-100)', borderRadius: 4 }}>
        <div style={{ width: `${Math.round(value * 100)}%`, height: 8, background: 'var(--brand)', borderRadius: 4 }} />
      </div>
      <span className="mono" style={{ font: '600 12px/1 var(--font-mono)', color: 'var(--text-strong)' }}>{(value * 100).toFixed(0)}%</span>
    </div>
  );
}

function TaskFlow({ task: initial, onDone }: { task: ModelTask; onDone: () => void }) {
  const [task, setTask] = useState(initial);
  const [selected, setSelected] = useState<Record<string, boolean>>(
    Object.fromEntries(initial.proposed.map((f) => [f.name, true])),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const accepted = Object.entries(selected).filter(([, on]) => on).map(([n]) => n);
  const acceptAndTrain = async () => {
    setBusy(true); setError(null);
    try {
      await api.updateModelFeatures(task.task_id, accepted);
      const trained = await api.trainModel(task.task_id);
      setTask(trained);
    } catch (e) {
      setError((e as Error).message || 'Training failed.');
    } finally {
      setBusy(false);
    }
  };
  if (task.status === 'trained' && task.metrics) {
    return (
      <Card style={{ padding: 18, maxWidth: 720 }} aria-label={`Model ${task.task_id} trained`}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
          <span style={EYEBROW}>Trained model</span>
          <span className="mono" style={{ font: '700 14px/1 var(--font-mono)' }}>{task.task_id} v{task.version}</span>
          <Badge tone="success">trained</Badge>
        </div>
        <p aria-label="Model evaluation" style={{ margin: '0 0 12px', font: '500 14px/1.55 var(--font-sans)', color: 'var(--text-strong)' }}>{task.evaluation}</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
          <MetricBar label="Simple line fit" value={task.metrics.linear.r2} />
          <MetricBar label="Upgraded model fit" value={task.metrics.gbm.r2} />
        </div>
        <div style={{ ...EYEBROW, marginBottom: 6 }}>What mattered most</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 14 }}>
          {task.importances.slice(0, 6).map(([name, weight]) => <MetricBar key={name} label={name} value={weight} />)}
        </div>
        {task.predictions_dataset && (
          <div aria-label={`Predictions dataset ${task.predictions_dataset}`}
            style={{ display: 'flex', alignItems: 'center', gap: 8, font: '500 13px/1.4 var(--font-sans)', color: 'var(--text-body)' }}>
            <Icon as={Download} size={14} color="var(--brand)" />
            Predictions saved as <span className="mono">{task.predictions_dataset}</span> — query, chart, or export it like any dataset.
          </div>
        )}
        <button aria-label="Finish model" onClick={onDone}
          style={{ marginTop: 14, padding: '7px 13px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12.5px/1 var(--font-sans)' }}>
          Done
        </button>
      </Card>
    );
  }
  return (
    <Card style={{ padding: 18, maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
        <span style={EYEBROW}>New model</span>
        <span className="mono" style={{ font: '700 14px/1 var(--font-mono)' }}>{task.dataset} → {task.target}</span>
      </div>
      <p aria-label="Teaching note" style={{ margin: '0 0 8px', font: '400 13.5px/1.6 var(--font-sans)', color: 'var(--text-body)' }}>{task.teaching_note}</p>
      <p aria-label="Split note" style={{ margin: '0 0 14px', padding: '10px 12px', background: 'var(--brand-subtle)', borderRadius: 'var(--radius-md)', font: '400 13px/1.55 var(--font-sans)', color: 'var(--text-strong)' }}>{task.split_note}</p>
      <div style={{ ...EYEBROW, marginBottom: 8 }}>Proposed features — keep what makes sense</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14, maxHeight: 320, overflow: 'auto' }}>
        {task.proposed.map((f) => (
          <label key={f.name} style={{ display: 'flex', alignItems: 'flex-start', gap: 9, padding: '8px 10px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}>
            <input type="checkbox" checked={!!selected[f.name]} onChange={() => setSelected({ ...selected, [f.name]: !selected[f.name] })} style={{ marginTop: 2 }} />
            <span>
              <span className="mono" style={{ font: '600 12.5px/1.3 var(--font-mono)', color: 'var(--text-strong)' }}>{f.name}</span>
              <span style={{ display: 'block', font: '400 12px/1.45 var(--font-sans)', color: 'var(--text-muted)', marginTop: 2 }}>{f.reason}</span>
            </span>
          </label>
        ))}
      </div>
      {error && <div role="alert" style={{ marginBottom: 10, font: '500 12.5px/1.4 var(--font-sans)', color: 'var(--amber-600)' }}>{error}</div>}
      <button aria-label="Accept features and train" disabled={busy || accepted.length === 0} onClick={acceptAndTrain}
        style={{ padding: '9px 16px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 13px/1 var(--font-sans)', opacity: busy || accepted.length === 0 ? 0.6 : 1 }}>
        {busy ? 'Training locally…' : `Accept ${accepted.length} features & train`}
      </button>
    </Card>
  );
}

function RelationalFlow({ task: initial, onDone }: { task: RelationalTask; onDone: () => void }) {
  const [task, setTask] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const train = async () => {
    setBusy(true); setError(null);
    try {
      setTask(await api.trainRelational(task.task_id));
      useCatalog.getState().refresh();
    } catch (e) {
      setError((e as Error).message || 'Training failed.');
    } finally {
      setBusy(false);
    }
  };
  if (task.status === 'trained' && task.metrics && task.story) {
    return (
      <Card style={{ padding: 18, maxWidth: 720 }} aria-label={`Relational model ${task.task_id} trained`}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
          <span style={EYEBROW}>Trained relational model</span>
          <span className="mono" style={{ font: '700 14px/1 var(--font-mono)' }}>{task.task_id} v{task.version}</span>
          <Badge tone="success">trained</Badge>
        </div>
        <p aria-label="Relational evaluation" style={{ margin: '0 0 12px', font: '500 14px/1.55 var(--font-sans)', color: 'var(--text-strong)' }}>{task.evaluation}</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
          <MetricBar label="Simple approach" value={task.metrics.baseline.test_auroc} />
          <MetricBar label="Graph approach" value={task.metrics.graph.test_auroc} />
          <MetricBar label="Combined" value={task.metrics.hybrid.test_auroc} />
        </div>
        <div aria-label="Relational story" style={{ marginBottom: 14, padding: '10px 12px', background: 'var(--brand-subtle)', borderRadius: 'var(--radius-md)', font: '400 12.5px/1.6 var(--font-sans)', color: 'var(--text-strong)' }}>
          Learned from {task.story.tables.length} linked tables ({task.story.tables.join(', ')}) across {task.story.edges.length} validated links, {task.story.num_layers} hops deep. Split {task.story.split}: {task.story.split_sizes.train} to learn from, {task.story.split_sizes.val} to tune on, {task.story.split_sizes.test} future rows as the honest test. Seed {task.seed} — the same seed always gives the same result.
        </div>
        {task.predictions_dataset && (
          <div aria-label={`Predictions dataset ${task.predictions_dataset}`}
            style={{ display: 'flex', alignItems: 'center', gap: 8, font: '500 13px/1.4 var(--font-sans)', color: 'var(--text-body)' }}>
            <Icon as={Download} size={14} color="var(--brand)" />
            Predictions saved as <span className="mono">{task.predictions_dataset}</span> — query, chart, or export it like any dataset.
          </div>
        )}
        <button aria-label="Finish relational model" onClick={onDone}
          style={{ marginTop: 14, padding: '7px 13px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12.5px/1 var(--font-sans)' }}>
          Done
        </button>
      </Card>
    );
  }
  return (
    <Card style={{ padding: 18, maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
        <span style={EYEBROW}>New relational model</span>
        <span className="mono" style={{ font: '700 14px/1 var(--font-mono)' }}>{task.dataset} → {task.task}</span>
      </div>
      <p aria-label="Task framing" style={{ margin: '0 0 8px', font: '600 14px/1.5 var(--font-sans)', color: 'var(--text-strong)' }}>{task.framing.question}</p>
      <p style={{ margin: '0 0 8px', font: '400 13px/1.6 var(--font-sans)', color: 'var(--text-body)' }}>{task.framing.moment}</p>
      <p aria-label="Honesty note" style={{ margin: '0 0 10px', padding: '10px 12px', background: 'var(--brand-subtle)', borderRadius: 'var(--radius-md)', font: '400 13px/1.55 var(--font-sans)', color: 'var(--text-strong)' }}>{task.framing.honesty}</p>
      <div aria-label="Excluded outcomes" style={{ marginBottom: 14, font: '500 12.5px/1.5 var(--font-sans)', color: 'var(--text-muted)' }}>
        Hidden from the model: {task.excluded_outcomes.map((c) => <span key={c} className="mono" style={{ marginRight: 8 }}>{c}</span>)}
      </div>
      {error && <div role="alert" style={{ marginBottom: 10, font: '500 12.5px/1.4 var(--font-sans)', color: 'var(--amber-600)' }}>{error}</div>}
      <button aria-label="Train relational model" disabled={busy} onClick={train}
        style={{ padding: '9px 16px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 13px/1 var(--font-sans)', opacity: busy ? 0.6 : 1 }}>
        {busy ? 'Training locally (graph + simple + combined)…' : 'Train locally'}
      </button>
    </Card>
  );
}

function AuthoringFlow({ task: initial, onDone }: { task: RelationalTask; onDone: () => void }) {
  const [task, setTask] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hideChoice, setHideChoice] = useState('');
  const act = async (fn: () => Promise<RelationalTask>) => {
    setBusy(true); setError(null);
    try { setTask(await fn()); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  if (task.status === 'trained') return <RelationalFlow task={task} onDone={onDone} />;
  if (task.status === 'defined') {
    return (
      <Card style={{ padding: 18, maxWidth: 720 }}>
        <div style={{ ...EYEBROW, marginBottom: 8 }}>Decisions confirmed</div>
        <div aria-label="Confirmed honesty checks" style={{ marginBottom: 12, padding: '10px 12px', background: 'var(--brand-subtle)', borderRadius: 'var(--radius-md)', font: '400 13px/1.6 var(--font-sans)', color: 'var(--text-strong)' }}>
          Honesty check: training on deliberately shuffled outcomes scored {task.canary?.toFixed(2)} — a coin flip, as honest wiring should. {task.warnings && task.warnings.length > 0 ? task.warnings.join(' ') : 'No columns give the answer away.'}
        </div>
        {error && <div role="alert" style={{ marginBottom: 10, font: '500 12.5px/1.4 var(--font-sans)', color: 'var(--amber-600)' }}>{error}</div>}
        <button aria-label="Train relational model" disabled={busy} onClick={() => act(() => api.trainRelational(task.task_id))}
          style={{ padding: '9px 16px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 13px/1 var(--font-sans)', opacity: busy ? 0.6 : 1 }}>
          {busy ? 'Training locally (graph + simple + combined)…' : 'Train locally'}
        </button>
      </Card>
    );
  }
  return (
    <Card style={{ padding: 18, maxWidth: 720 }} aria-label="Authored decisions">
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
        <span style={EYEBROW}>Proposed decisions — confirm or adjust</span>
        <span className="mono" style={{ font: '700 13px/1 var(--font-mono)' }}>{task.entity_table}</span>
      </div>
      <p style={{ margin: '0 0 8px', font: '600 14px/1.5 var(--font-sans)', color: 'var(--text-strong)' }}>{task.framing.question}</p>
      <p style={{ margin: '0 0 8px', font: '400 13px/1.6 var(--font-sans)', color: 'var(--text-body)' }}>{task.framing.moment}</p>
      <p style={{ margin: '0 0 10px', padding: '10px 12px', background: 'var(--brand-subtle)', borderRadius: 'var(--radius-md)', font: '400 13px/1.55 var(--font-sans)', color: 'var(--text-strong)' }}>{task.framing.honesty}</p>
      <div className="mono" style={{ marginBottom: 10, font: '400 12px/1.5 var(--font-mono)', color: 'var(--text-muted)', overflowX: 'auto' }}>{task.label_sql}</div>
      <div aria-label="Hidden outcome columns" style={{ marginBottom: 10, font: '500 12.5px/1.5 var(--font-sans)', color: 'var(--text-muted)' }}>
        Hidden from the model: {(task.hidden_columns ?? []).map((c) => <span key={c} className="mono" style={{ marginRight: 8 }}>{c}</span>)}
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
          Validation cutoff{' '}
          <input aria-label="Validation cutoff" value={task.val_cutoff ?? ''} onChange={(e) => setTask({ ...task, val_cutoff: e.target.value })}
            style={{ width: 110, height: 30, padding: '0 8px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 12.5px/1 var(--font-mono)' }} />
        </label>
        <label style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
          Test cutoff{' '}
          <input aria-label="Test cutoff" value={task.test_cutoff ?? ''} onChange={(e) => setTask({ ...task, test_cutoff: e.target.value })}
            style={{ width: 110, height: 30, padding: '0 8px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 12.5px/1 var(--font-mono)' }} />
        </label>
        <input aria-label="Hide another column" placeholder="hide another column…" value={hideChoice} onChange={(e) => setHideChoice(e.target.value)}
          style={{ width: 170, height: 30, padding: '0 8px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 12.5px/1 var(--font-sans)' }} />
      </div>
      {error && <div role="alert" style={{ marginBottom: 10, font: '500 12.5px/1.4 var(--font-sans)', color: 'var(--amber-600)' }}>{error}</div>}
      <button aria-label="Confirm decisions" disabled={busy} onClick={() => act(async () => {
        await api.updateRelationalDecisions(task.task_id, { valCutoff: task.val_cutoff, testCutoff: task.test_cutoff, hide: hideChoice ? [hideChoice.trim()] : [] });
        return api.confirmRelational(task.task_id);
      })}
        style={{ padding: '9px 16px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 13px/1 var(--font-sans)', opacity: busy ? 0.6 : 1 }}>
        {busy ? 'Checking honesty…' : 'Confirm decisions'}
      </button>
    </Card>
  );
}

export function ModelsPage() {
  const datasets = useCatalog((s) => s.datasets);
  const [samples, setSamples] = useState<ModelSample[]>([]);
  const [bundle, setBundle] = useState<RelationalBundle | null>(null);
  const [models, setModels] = useState<(ModelTask | RelationalTask)[]>([]);
  const [task, setTask] = useState<ModelTask | null>(null);
  const [relTask, setRelTask] = useState<RelationalTask | null>(null);
  const [authTask, setAuthTask] = useState<RelationalTask | null>(null);
  const [authQuestion, setAuthQuestion] = useState('');
  const [dataset, setDataset] = useState('');
  const [target, setTarget] = useState('');
  const [relChoice, setRelChoice] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = () => {
    api.modelGallery().then((r) => setSamples(r.samples)).catch(() => {});
    api.relationalBundle().then(setBundle).catch(() => {});
    api.listModels().then((r) => setModels(r.models)).catch(() => {});
  };
  useEffect(() => { refresh(); }, []);
  const addSample = (key: string) => {
    setBusy(key); setError(null);
    api.addModelSample(key)
      .then(() => useCatalog.getState().refresh())
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null));
  };
  const addBundle = () => {
    setBusy('bundle'); setError(null);
    api.addRelationalBundle()
      .then(() => { useCatalog.getState().refresh(); refresh(); })
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null));
  };
  const start = () => {
    if (!dataset || !target.trim()) return;
    setBusy('start'); setError(null);
    api.createModelTask(dataset, target.trim())
      .then(setTask)
      .catch((e) => setError(e.message || 'Could not start the model.'))
      .finally(() => setBusy(null));
  };
  const startAuthoring = () => {
    if (!authQuestion.trim()) return;
    setBusy('author'); setError(null);
    api.authorRelational(authQuestion.trim())
      .then(setAuthTask)
      .catch((e) => setError(e.message || 'Could not author the task.'))
      .finally(() => setBusy(null));
  };
  const startRelational = () => {
    if (!relChoice) return;
    setBusy('rel-start'); setError(null);
    api.createRelationalTask(relChoice)
      .then(setRelTask)
      .catch((e) => setError(e.message || 'Could not start the relational model.'))
      .finally(() => setBusy(null));
  };
  if (authTask) {
    return (
      <section style={{ flex: 1, overflow: 'auto', padding: '26px 30px' }}>
        <button aria-label="Back to models" onClick={() => { setAuthTask(null); refresh(); }}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 12, padding: '5px 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
          <Icon as={ChevronLeft} size={13} /> Models
        </button>
        <AuthoringFlow task={authTask} onDone={() => { setAuthTask(null); refresh(); }} />
      </section>
    );
  }
  if (relTask) {
    return (
      <section style={{ flex: 1, overflow: 'auto', padding: '26px 30px' }}>
        <button aria-label="Back to models" onClick={() => { setRelTask(null); refresh(); }}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 12, padding: '5px 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
          <Icon as={ChevronLeft} size={13} /> Models
        </button>
        <RelationalFlow task={relTask} onDone={() => { setRelTask(null); refresh(); }} />
      </section>
    );
  }
  if (task) {
    return (
      <section style={{ flex: 1, overflow: 'auto', padding: '26px 30px' }}>
        <button aria-label="Back to models" onClick={() => { setTask(null); refresh(); }}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 12, padding: '5px 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', background: 'transparent', cursor: 'pointer', font: '600 12px/1 var(--font-sans)', color: 'var(--text-muted)' }}>
          <Icon as={ChevronLeft} size={13} /> Models
        </button>
        <TaskFlow task={task} onDone={() => { setTask(null); refresh(); }} />
      </section>
    );
  }
  const fileDatasets = datasets.filter((d) => d.sourceKind === 'file');
  const targetColumns = fileDatasets.find((d) => d.id === dataset)?.profile.columns ?? [];
  return (
    <section style={{ flex: 1, overflow: 'auto', padding: '26px 30px' }}>
      <div style={EYEBROW}>Models</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '6px 0 18px' }}>
        <h2 style={{ margin: 0, font: '800 22px/1.05 var(--font-sans)', letterSpacing: '-.02em' }}>Guided models</h2>
        <Badge>{models.length}</Badge>
      </div>
      {error && <div role="alert" style={{ maxWidth: 680, marginBottom: 12, padding: '10px 12px', border: '1px solid var(--amber-100)', background: 'var(--amber-100)', borderRadius: 'var(--radius-md)', font: '500 12.5px/1.5 var(--font-sans)', color: 'var(--amber-600)' }}>{error}</div>}

      <div style={{ ...EYEBROW, marginBottom: 8 }}>Sample gallery — real data, downloaded on demand</div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        {samples.map((s) => (
          <Card key={s.key} style={{ padding: 14, width: 300 }}>
            <div style={{ font: '700 13.5px/1.2 var(--font-sans)', marginBottom: 5 }}>{s.title}</div>
            <div style={{ font: '400 12px/1.5 var(--font-sans)', color: 'var(--text-muted)', marginBottom: 10 }}>{s.description}</div>
            <button aria-label={`Add sample ${s.title}`} disabled={busy === s.key} onClick={() => addSample(s.key)}
              style={{ padding: '6px 12px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 12px/1 var(--font-sans)', opacity: busy === s.key ? 0.6 : 1 }}>
              {busy === s.key ? 'Downloading…' : 'Add to workspace'}
            </button>
          </Card>
        ))}
      </div>

      {bundle && (
        <>
          <div style={{ ...EYEBROW, marginBottom: 8 }}>Relational — learn across linked tables</div>
          <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <Card style={{ padding: 14, width: 300 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
                <Icon as={Network} size={15} color="var(--brand)" />
                <span style={{ font: '700 13.5px/1.2 var(--font-sans)' }}>{bundle.title}</span>
              </div>
              <div style={{ font: '400 12px/1.5 var(--font-sans)', color: 'var(--text-muted)', marginBottom: 10 }}>{bundle.description}</div>
              {bundle.available ? (
                <button aria-label={`Add bundle ${bundle.title}`} disabled={busy === 'bundle' || bundle.added} onClick={addBundle}
                  style={{ padding: '6px 12px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 12px/1 var(--font-sans)', opacity: busy === 'bundle' ? 0.6 : 1 }}>
                  {bundle.added ? 'In workspace' : busy === 'bundle' ? 'Downloading…' : 'Add to workspace'}
                </button>
              ) : (
                <div aria-label="Relational tier unavailable" style={{ font: '500 12px/1.5 var(--font-sans)', color: 'var(--amber-600)' }}>{bundle.message}</div>
              )}
            </Card>
            {bundle.available && (
              <div style={{ display: 'flex', gap: 8, flexDirection: 'column' }}>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input aria-label="Authoring question" placeholder="ask about your own linked data… e.g. which loans will default?" value={authQuestion} onChange={(e) => setAuthQuestion(e.target.value)}
                    style={{ width: 380, height: 36, padding: '0 10px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 13px/1 var(--font-sans)' }} />
                  <button aria-label="Author relational task" disabled={!authQuestion.trim() || busy === 'author'} onClick={startAuthoring}
                    style={{ padding: '0 16px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 13px/1 var(--font-sans)', opacity: !authQuestion.trim() ? 0.5 : 1 }}>
                    {busy === 'author' ? 'Authoring…' : 'Author'}
                  </button>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                <select aria-label="Relational task" value={relChoice} onChange={(e) => setRelChoice(e.target.value)}
                  style={{ width: 300, height: 36, padding: '0 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 13px/1 var(--font-sans)' }}>
                  <option value="">choose a question…</option>
                  {bundle.tasks.map((t) => <option key={t.name} value={t.name}>{t.question}</option>)}
                </select>
                <button aria-label="Start relational model" disabled={!relChoice || busy === 'rel-start'} onClick={startRelational}
                  style={{ padding: '0 16px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 13px/1 var(--font-sans)', opacity: !relChoice ? 0.5 : 1 }}>
                  {busy === 'rel-start' ? 'Preparing…' : 'Start'}
                </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      <div style={{ ...EYEBROW, marginBottom: 8 }}>New model</div>
      <div style={{ display: 'flex', gap: 8, maxWidth: 680, marginBottom: 22 }}>
        <select aria-label="Model dataset" value={dataset} onChange={(e) => { setDataset(e.target.value); setTarget(''); }}
          style={{ flex: 1, height: 36, padding: '0 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 13px/1 var(--font-sans)' }}>
          <option value="">choose a dataset…</option>
          {fileDatasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select aria-label="Model target" value={target} onChange={(e) => setTarget(e.target.value)} disabled={!dataset}
          style={{ flex: 1, height: 36, padding: '0 9px', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', font: '400 13px/1 var(--font-sans)' }}>
          <option value="">what to predict…</option>
          {targetColumns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
        </select>
        <button aria-label="Start model" disabled={!dataset || !target || busy === 'start'} onClick={start}
          style={{ padding: '0 16px', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: '#fff', cursor: 'pointer', font: '600 13px/1 var(--font-sans)', opacity: !dataset || !target ? 0.5 : 1 }}>
          {busy === 'start' ? 'Thinking…' : 'Start'}
        </button>
      </div>

      <div style={{ ...EYEBROW, marginBottom: 8 }}>Trained models</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 680 }}>
        {models.length === 0 && <p style={{ font: '400 13px/1.5 var(--font-sans)', color: 'var(--text-muted)' }}>No models yet — add a sample above and start one.</p>}
        {models.map((m) => {
          const rel = 'kind' in m && m.kind === 'relational' ? (m as RelationalTask) : null;
          return (
            <Card key={m.task_id} style={{ padding: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <button aria-label={`Open model ${m.task_id}`} onClick={() => (rel ? (rel.authored ? setAuthTask(rel) : setRelTask(rel)) : setTask(m as ModelTask))}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 11, padding: '13px 15px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}>
                  <Icon as={rel ? Network : Brain} size={17} color="var(--brand)" />
                  <span style={{ flex: 1 }}>
                    <span className="mono" style={{ display: 'block', font: '600 13px/1.2 var(--font-mono)', color: 'var(--text-strong)' }}>
                      {rel ? `${rel.dataset} → ${rel.task}` : `${(m as ModelTask).dataset} → ${(m as ModelTask).target}`}
                    </span>
                    {rel && rel.metrics && (
                      <span aria-label={`Model ${m.task_id} metrics`} style={{ display: 'block', font: '400 12px/1.4 var(--font-sans)', color: 'var(--text-muted)', marginTop: 3 }}>
                        simple {rel.metrics.baseline.test_auroc.toFixed(2)} · graph {rel.metrics.graph.test_auroc.toFixed(2)} · combined {rel.metrics.hybrid.test_auroc.toFixed(2)} · seed {rel.seed}
                      </span>
                    )}
                    {!rel && (m as ModelTask).metrics && (
                      <span aria-label={`Model ${m.task_id} metrics`} style={{ display: 'block', font: '400 12px/1.4 var(--font-sans)', color: 'var(--text-muted)', marginTop: 3 }}>
                        fit {((m as ModelTask).metrics!.gbm.r2 * 100).toFixed(0)}% · typical miss ${Math.round((m as ModelTask).metrics!.gbm.mae).toLocaleString()}
                      </span>
                    )}
                  </span>
                  <Badge tone={m.status === 'trained' ? 'success' : 'neutral'}>{m.status}</Badge>
                </button>
                <button aria-label={`Delete model ${m.task_id}`} onClick={() => api.deleteModel(m.task_id).then(refresh)}
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: '0 14px' }}>
                  <Icon as={Trash2} size={15} color="var(--text-subtle)" />
                </button>
              </div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
