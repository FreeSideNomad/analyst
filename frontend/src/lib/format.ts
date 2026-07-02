// ── formatting + role helpers ────────────────────────────────────────
import type { ColumnRole, ColumnType } from '../api/types';

export const money = (n: number): string =>
  n >= 1e6 ? '$' + (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M'
  : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K'
  : '$' + n;

export const nfmt = (n: number): string => n.toLocaleString('en-US');

// Domain ColumnType → display label (analyst.domain.types.ColumnType).
export const TYPE_LABEL: Record<ColumnType, string> = {
  text: 'Text', integer: 'Integer', decimal: 'Decimal',
  boolean: 'Boolean', date: 'Date', datetime: 'Datetime',
};

export type Tone = 'neutral' | 'brand' | 'success' | 'warning' | 'info';

// Domain role vocab (cataloguer): identifier·measure·category·timestamp·text·other.
const ROLE_BADGE: Record<ColumnRole, { label: string; tone: Tone }> = {
  identifier: { label: 'ID', tone: 'brand' },
  measure:    { label: 'Metric', tone: 'success' },
  category:   { label: 'Category', tone: 'neutral' },
  timestamp:  { label: 'Date', tone: 'neutral' },
  text:       { label: 'Text', tone: 'neutral' },
  other:      { label: 'Field', tone: 'neutral' },
};

export function roleBadge(role: ColumnRole): { label: string; tone: Tone } {
  return ROLE_BADGE[role] || ROLE_BADGE.other;
}
