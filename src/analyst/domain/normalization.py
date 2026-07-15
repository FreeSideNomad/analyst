"""Normalization domain — feature 013 (pure policy, no I/O).

Detects when distinct raw values are provably the SAME value rendered
inconsistently (letter case, stray/duplicated whitespace) and freezes the
repair as an explicit rule: a raw→canonical mapping plus a plain-language
description a person can judge. Rules are candidates — the charter forbids
applying them without approval — and the canonical value is always one of
the observed variants, never an invented string.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

_WHITESPACE_RUN = re.compile(r"\s+")


class UnknownNormalizationError(KeyError):
    """Acting on a normalization rule that does not exist (stale UI, retry)."""


def canonical_key(value: str) -> str:
    """The identity under which variants collide: trimmed, internal
    whitespace collapsed, casefolded (unicode-correct, not just lower())."""
    return _WHITESPACE_RUN.sub(" ", value.strip()).casefold()


@dataclass(frozen=True)
class Variant:
    """One observed raw rendering of a value, with its row count."""

    value: str
    rows: int


@dataclass(frozen=True)
class VariantGroup:
    """Raw renderings that are provably the same value, plus the chosen
    canonical rendering (always one of the variants)."""

    canonical: str
    variants: tuple[Variant, ...]


@dataclass(frozen=True)
class NormalizationRule:
    """A frozen, explicit repair candidate for one column.

    mapping holds ONLY the non-canonical variants; values outside the
    mapping pass through untouched. New variants arriving later are NOT
    covered — they must surface as a new proposal (never silently applied,
    extended across time)."""

    rule_id: str
    column: str
    groups: tuple[VariantGroup, ...]
    mapping: dict[str, str]
    description: str


def _is_clean(value: str) -> bool:
    return value == _WHITESPACE_RUN.sub(" ", value.strip())


def choose_canonical(variants: tuple[Variant, ...]) -> str:
    """Pick the rendering to standardize on: most rows win; ties prefer the
    clean form (no stray whitespace), then the title-cased rendering, then
    the lexicographically smallest — deterministic for a fixed input."""
    best_rows = max(v.rows for v in variants)
    leaders = [v.value for v in variants if v.rows == best_rows]
    clean = [v for v in leaders if _is_clean(v)]
    pool = clean or leaders
    titled = [v for v in pool if v == v.title()]
    return min(titled) if titled else min(pool)


def group_variants(counts: Mapping[str, int]) -> tuple[VariantGroup, ...]:
    """Group raw value counts by canonical identity; only real collisions
    (≥2 distinct renderings) become groups. Deterministic order."""
    by_key: dict[str, list[Variant]] = {}
    for value, rows in counts.items():
        by_key.setdefault(canonical_key(value), []).append(Variant(value, rows))
    groups = []
    for _, members in sorted(by_key.items()):
        if len(members) < 2:
            continue
        variants = tuple(sorted(members, key=lambda v: (-v.rows, v.value)))
        groups.append(VariantGroup(choose_canonical(variants), variants))
    return tuple(groups)


def rule_for(column: str, groups: tuple[VariantGroup, ...]) -> NormalizationRule:
    """Freeze groups into the column's rule (one rule per column in v1)."""
    mapping = {
        variant.value: group.canonical
        for group in groups
        for variant in group.variants
        if variant.value != group.canonical
    }
    merges = ", ".join(
        f'{len(group.variants)} variants into "{group.canonical}" '
        f"({sum(v.rows for v in group.variants)} rows)"
        for group in groups
    )
    return NormalizationRule(
        rule_id=f"norm:{column}",
        column=column,
        groups=groups,
        mapping=mapping,
        description=f'Standardize "{column}": merge {merges}.',
    )
