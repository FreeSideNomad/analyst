"""Structural honesty checks — feature 019. FIXED, COMMITTED CODE.

Where no reference numbers can exist (a user's own data), honesty is
structural: (1) the shuffled-label canary — train the fast tier on
deliberately permuted outcomes; a score away from coin-flip means the
plumbing leaks; (2) the giveaway detector — an entity column whose values
alone nearly perfectly rank the outcome almost certainly records the
outcome, and the user is warned before training. Both deterministic for a
fixed seed, both cheap (no GNN involved).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import DatasetSpec, TaskSpec

GIVEAWAY_AUROC = 0.95


def shuffled_label_canary(
    spec: DatasetSpec, task: TaskSpec, frame: pd.DataFrame, seed: int
) -> float:
    """Held-out AUROC of the baseline trained on seed-shuffled labels.
    Honest wiring scores ≈ 0.5 — there is nothing real to learn."""
    from .models.baseline import train_and_evaluate

    shuffled = frame.reset_index(drop=True).copy()
    rng = np.random.default_rng(seed)
    shuffled["label"] = rng.permutation(shuffled["label"].to_numpy())
    # Permutation can starve a small split of a class; the canary only
    # needs a scoreable test split, so reshuffle until both classes appear.
    for _ in range(20):
        counts = shuffled.groupby("split")["label"].nunique()
        if (counts >= 2).all():
            break
        shuffled["label"] = rng.permutation(shuffled["label"].to_numpy())
    metrics = train_and_evaluate(spec, task, shuffled, seed=seed, smoke=False)
    return float(metrics["test_auroc"])


def giveaway_columns(
    frame: pd.DataFrame,
    entity_frame: pd.DataFrame,
    entity_column: str,
    candidate_columns: list[str],
) -> list[str]:
    """Entity columns whose values ALONE nearly perfectly rank the outcome
    (AUROC ≥ 0.95 either direction) — no model, just ranking power."""
    from sklearn.metrics import roc_auc_score

    labels = frame.set_index(frame[entity_column])["label"]
    joined = entity_frame.set_index(entity_column).join(labels, how="inner")
    y = joined["label"].astype(int)
    if y.nunique() < 2:
        return []
    flagged: list[str] = []
    for col in candidate_columns:
        if col not in joined.columns:
            continue
        series = joined[col]
        if pd.api.types.is_numeric_dtype(series):
            score = series.astype(float)
        else:
            rate = y.groupby(series.astype(str)).mean()
            score = series.astype(str).map(rate)
        mask = score.notna()
        if mask.sum() < 10 or y[mask].nunique() < 2:
            continue
        auroc = float(roc_auc_score(y[mask], score[mask]))
        if max(auroc, 1 - auroc) >= GIVEAWAY_AUROC:
            flagged.append(col)
    return flagged
