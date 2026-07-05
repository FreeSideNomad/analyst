// ── components/ui.tsx ─────────────────────────────────────────────────
// SWISS design-system primitives (in a Tailwind/shadcn setup these are the
// themed shadcn components; here they're small inline-styled components over
// the CSS design tokens in index.css).
import { useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { Tone } from '../lib/format';

export const EYEBROW: CSSProperties = {
  font: '600 12px/1 var(--font-sans)', letterSpacing: '.14em',
  textTransform: 'uppercase', color: 'var(--text-muted)',
};

type IconComp = LucideIcon;

export function Icon({ as: C, size = 18, color = 'currentColor', style }: { as: IconComp; size?: number; color?: string; style?: CSSProperties }) {
  return <C size={size} color={color} strokeWidth={1.9} style={{ flex: 'none', ...style }} />;
}

const BADGE_TONE: Record<Tone, { bg: string; fg: string }> = {
  neutral: { bg: 'var(--neutral-100)', fg: 'var(--neutral-700)' },
  brand:   { bg: 'var(--brand-subtle)', fg: 'var(--brand)' },
  success: { bg: 'var(--green-100)', fg: 'var(--green-600)' },
  warning: { bg: 'var(--amber-100)', fg: 'var(--amber-600)' },
  info:    { bg: 'var(--blue-100)', fg: 'var(--blue-600)' },
};
export function Badge({ children, tone = 'neutral', style }: { children: ReactNode; tone?: Tone; style?: CSSProperties }) {
  const t = BADGE_TONE[tone] || BADGE_TONE.neutral;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, height: 20, padding: '0 7px',
      background: t.bg, color: t.fg, font: '600 10.5px/1 var(--font-sans)', letterSpacing: '.06em',
      textTransform: 'uppercase', borderRadius: 'var(--radius-sm)', whiteSpace: 'nowrap', ...style }}>{children}</span>
  );
}

export function Button({ children, variant = 'primary', size = 'md', iconLeft, iconRight, onClick, disabled, style }: {
  children: ReactNode; variant?: 'primary' | 'secondary' | 'ghost'; size?: 'sm' | 'md';
  iconLeft?: ReactNode; iconRight?: ReactNode; onClick?: () => void; disabled?: boolean; style?: CSSProperties;
}) {
  const [h, setH] = useState(false);
  const S = size === 'sm' ? { height: 34, padding: '0 13px', font: '14px' } : { height: 42, padding: '0 18px', font: '15px' };
  const V = {
    primary:   { background: h ? 'var(--brand-hover)' : 'var(--brand)', color: 'var(--on-brand)', border: '1px solid transparent' },
    secondary: { background: h ? 'var(--surface-sunken)' : 'var(--surface-card)', color: 'var(--text-strong)', border: '1px solid var(--border-default)' },
    ghost:     { background: h ? 'var(--surface-sunken)' : 'transparent', color: 'var(--text-strong)', border: '1px solid transparent' },
  }[variant];
  return (
    <button onClick={onClick} disabled={disabled} onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, height: S.height, padding: S.padding,
        font: `600 ${S.font}/1 var(--font-sans)`, letterSpacing: '-.01em', borderRadius: 'var(--radius-md)',
        cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.45 : 1, whiteSpace: 'nowrap',
        transition: 'background var(--dur-fast) var(--ease-standard)', ...V, ...style }}>
      {iconLeft}{children}{iconRight}
    </button>
  );
}

export function IconButton({ as: C, label, onClick }: { as: IconComp; label: string; onClick?: () => void }) {
  const [h, setH] = useState(false);
  return (
    <button aria-label={label} onClick={onClick} onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 38, height: 38,
        background: h ? 'var(--surface-sunken)' : 'transparent', border: '1px solid transparent', borderRadius: 'var(--radius-md)',
        color: 'var(--text-body)', cursor: 'pointer', transition: 'background var(--dur-fast)' }}>
      <Icon as={C} size={19} />
    </button>
  );
}

export function Card({ children, style, interactive, onClick }: { children: ReactNode; style?: CSSProperties; interactive?: boolean; onClick?: () => void }) {
  const [h, setH] = useState(false);
  return (
    <div onClick={onClick} onMouseEnter={() => interactive && setH(true)} onMouseLeave={() => interactive && setH(false)}
      style={{ background: 'var(--surface-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)',
        boxShadow: h ? 'var(--shadow-md)' : 'var(--shadow-xs)', transition: 'box-shadow var(--dur-base), transform var(--dur-base)',
        transform: h ? 'translateY(-2px)' : 'none', cursor: interactive ? 'pointer' : 'default', ...style }}>{children}</div>
  );
}

const PILL_TONE: Record<string, { fg: string; bg: string; dot: string }> = {
  connected: { fg: 'var(--green-600)', bg: 'var(--green-100)', dot: 'var(--green-500)' },
  ready:     { fg: 'var(--green-600)', bg: 'var(--green-100)', dot: 'var(--green-500)' },
  running:   { fg: 'var(--blue-600)', bg: 'var(--blue-100)', dot: 'var(--blue-500)' },
};
export function StatusPill({ status = 'ready', children }: { status?: string; children: ReactNode }) {
  const t = PILL_TONE[status] || PILL_TONE.ready;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 22, padding: '0 9px 0 7px',
      background: t.bg, color: t.fg, font: '600 12px/1 var(--font-sans)', borderRadius: 'var(--radius-full)', whiteSpace: 'nowrap' }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.dot }} />{children}
    </span>
  );
}

export function ProgressBar({ value, tone = 'brand', height = 8 }: { value: number; tone?: 'brand' | 'warning' | 'success'; height?: number }) {
  const c = { brand: 'var(--brand)', warning: 'var(--amber-500)', success: 'var(--green-500)' }[tone];
  return (
    <div style={{ height, borderRadius: 'var(--radius-full)', background: 'var(--surface-sunken)', overflow: 'hidden' }}>
      <div style={{ width: Math.max(0, Math.min(100, value)) + '%', height: '100%', background: c, borderRadius: 'var(--radius-full)',
        transition: 'width var(--dur-slow) var(--ease-standard)' }} />
    </div>
  );
}

export function SegmentedControl({ options, value, onChange, size = 'md' }: {
  options: { value: string; label: string }[]; value: string; onChange: (v: string) => void; size?: 'sm' | 'md';
}) {
  const h = size === 'sm' ? 30 : 38;
  return (
    <div role="tablist" style={{ display: 'inline-flex', padding: 3, gap: 2, background: 'var(--surface-sunken)', borderRadius: 'var(--radius-full)' }}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button key={o.value} onClick={() => onChange(o.value)} style={{ height: h, padding: '0 15px', border: 'none',
            cursor: 'pointer', borderRadius: 'var(--radius-full)', background: active ? 'var(--neutral-900)' : 'transparent',
            color: active ? '#fff' : 'var(--text-body)', font: `600 ${size === 'sm' ? '13px' : '14px'}/1 var(--font-sans)`,
            letterSpacing: '-.01em', transition: 'background var(--dur-fast), color var(--dur-fast)', whiteSpace: 'nowrap' }}>{o.label}</button>
        );
      })}
    </div>
  );
}

export function Tag({ children, onClick, selected }: { children: ReactNode; onClick?: () => void; selected?: boolean }) {
  const [h, setH] = useState(false);
  return (
    <button onClick={onClick} onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 32, padding: '0 13px',
        background: selected ? 'var(--brand-subtle)' : (h ? 'var(--surface-sunken)' : 'var(--surface-card)'),
        color: selected ? 'var(--brand)' : 'var(--text-body)', border: `1px solid ${selected ? 'var(--navy-100)' : 'var(--border-default)'}`,
        font: '500 13px/1 var(--font-sans)', borderRadius: 'var(--radius-full)', cursor: 'pointer', whiteSpace: 'nowrap',
        transition: 'background var(--dur-fast), border-color var(--dur-fast)' }}>{children}</button>
  );
}

// data-driven distribution — REAL histogram / top-K counts drawn as bars
export function Sparkline({ data, labels, width = 210, height = 42, color = 'var(--brand)' }: { data?: number[]; labels?: string[]; width?: number; height?: number; color?: string }) {
  if (!data || !data.length) return <svg width={width} height={height} />;
  const max = Math.max(...data) || 1, pad = 2, gap = 1.5;
  const bw = (width - pad * 2 - gap * (data.length - 1)) / data.length;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      {data.map((v, i) => {
        const h = Math.max(1, (v / max) * (height - pad * 2));
        return (
          <rect key={i} x={pad + i * (bw + gap)} y={height - pad - h} width={Math.max(1, bw)} height={h}
            rx={1} fill={color} fillOpacity={0.85}>
            <title>{`${labels?.[i] ?? i}: ${v}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}
