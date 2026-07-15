"""Normalization detection — feature 013 (engine layer).

Turns a dataset's profile + value counts into frozen rule candidates via the
pure domain policy. Fully local and deterministic: one GROUP BY per candidate
column, no model calls (AC-12), so it behaves identically offline.
"""

from __future__ import annotations

from analyst.domain.normalization import (
    NormalizationRule,
    canonical_key,
    group_variants,
    rule_for,
)
from analyst.domain.profile import DatasetProfile
from analyst.domain.types import ColumnType
from analyst.engine.store import DatasetStore

# Candidate gates. Raw distinct count is only a COST cap (one GROUP BY per
# candidate, bounded vocabulary). Identifier-likeness is judged on the
# CANONICAL vocabulary: a column that is still near-unique after collapsing
# case/whitespace variants is a key, not a category — standardizing it would
# corrupt identifiers (AC-12's exemption). Judging on raw distinct would
# wrongly exempt exactly the messy columns this feature exists for.
_MAX_DISTINCT = 200
_IDENTIFIER_RATIO = 0.9


def _candidates(profile: DatasetProfile) -> list[str]:
    if profile.row_count == 0:
        return []
    return [
        col.name
        for col in profile.columns
        if col.inferred_type == ColumnType.TEXT
        and 2 <= col.distinct_count <= _MAX_DISTINCT
    ]


def detect(
    store: DatasetStore, dataset: str, profile: DatasetProfile
) -> tuple[NormalizationRule, ...]:
    """Rule candidates for every column whose values collide under the
    canonical identity (case/whitespace variants of the same value)."""
    rules = []
    for column in _candidates(profile):
        counts = {
            value: rows
            for value, rows in store.value_counts(dataset, column).items()
            if canonical_key(value)  # values that trim to nothing are noise
        }
        rows_seen = sum(counts.values())
        canonical_vocabulary = {canonical_key(value) for value in counts}
        if rows_seen == 0 or len(canonical_vocabulary) / rows_seen >= _IDENTIFIER_RATIO:
            continue  # identifier-like: near-unique even after collapsing variants
        groups = group_variants(counts)
        if groups:
            rules.append(rule_for(column, groups))
    return tuple(rules)
