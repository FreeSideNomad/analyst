// ── lib/adapt.ts ─────────────────────────────────────────────────────
// Maps the wire ColumnProfile → the profile-card view-model. Isolates the UI
// from the domain shape: nullRate→percent, quantiles→[25/50/75], etc.
import type { ColumnProfile } from '../api/types';
import { TYPE_LABEL } from './format';

export interface ColumnVM {
  name: string;
  typeLabel: string;
  nullPercent: number;
  nullCount: number;
  distinctCount: number;
  uniquePct: number;
  samples: unknown[];
  isNumeric: boolean;
  minimum: unknown;
  maximum: unknown;
  q25: unknown;
  q50: unknown;
  q75: unknown;
  hist?: number[];        // REAL distribution counts (histogram or top-K)
  histLabels?: string[];  // the bucket range / value each bar represents
  isMixed: boolean;
  dominantLabel: string;
  isNested: boolean;
}

export function columnVM(col: ColumnProfile, rowCount: number): ColumnVM {
  const isNumeric = col.quantiles.length > 0 || col.minimum != null;
  const q = col.quantiles;
  return {
    name: col.name,
    typeLabel: TYPE_LABEL[col.inferredType] || col.inferredType,
    nullPercent: col.nullRate * 100,
    nullCount: col.nullCount,
    distinctCount: col.distinctCount,
    uniquePct: rowCount ? Math.round((col.distinctCount / rowCount) * 100) : 0,
    samples: col.samples,
    isNumeric,
    minimum: col.minimum,
    maximum: col.maximum,
    q25: q[0], q50: q[1], q75: q[2],
    hist: col.distribution.length ? col.distribution.map((b) => b.count) : undefined,
    histLabels: col.distribution.length ? col.distribution.map((b) => b.label) : undefined,
    isMixed: col.isMixed,
    dominantLabel: col.dominantType ? (TYPE_LABEL[col.dominantType] || col.dominantType) : '',
    isNested: col.isNested,
  };
}
