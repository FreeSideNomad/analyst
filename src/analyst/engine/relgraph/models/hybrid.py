"""Hybrid tier: graph embeddings + engineered features → gradient boosting.

The literature's best performer (embeddings as extra features for the
tabular learner). Not in the paper's repo — so it carries no reference
number; the board guards its wiring (no worse than a small margin below
the stronger parent), not a supremacy claim. Same split, same seed policy,
same LightGBM settings as the baseline: deterministic by construction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FULL_TREES = 500
EARLY_STOPPING_ROUNDS = 50


def train_and_evaluate(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    embeddings: np.ndarray,
    seed: int,
) -> tuple[dict, dict]:
    import lightgbm as lgb
    from sklearn.metrics import average_precision_score, roc_auc_score

    label = frame["label"].astype(int).reset_index(drop=True)
    split = frame["split"].reset_index(drop=True)
    emb_cols = pd.DataFrame(
        embeddings,
        columns=[f"gnn_emb_{i}" for i in range(embeddings.shape[1])],
    )
    combined = pd.concat([features.reset_index(drop=True), emb_cols], axis=1)

    parts = {
        name: (combined[split == name], label[split == name])
        for name in ("train", "val", "test")
    }
    model = lgb.LGBMClassifier(
        n_estimators=FULL_TREES,
        learning_rate=0.05,
        random_state=seed,
        deterministic=True,
        force_row_wise=True,
        n_jobs=1,
        verbosity=-1,
    )
    model.fit(
        *parts["train"],
        eval_set=[parts["val"]],
        eval_metric="auc",
        callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)],
    )
    x_test, y_test = parts["test"]
    proba = model.predict_proba(x_test)[:, 1]
    metrics = {
        "test_auroc": float(roc_auc_score(y_test, proba)),
        "test_avg_precision": float(average_precision_score(y_test, proba)),
    }
    details = {"proba": model.predict_proba(combined)[:, 1]}
    return metrics, details
