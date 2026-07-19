"""Feature-engineered baseline: generic window aggregates + gradient boosting.

Deterministic given a seed: single-threaded, fixed seeds everywhere.
"""

from __future__ import annotations

import pandas as pd

from ..features import build_features
from ..schema import DatasetSpec, TaskSpec

SMOKE_MAX_ROWS = 400
SMOKE_TREES = 25
FULL_TREES = 500
EARLY_STOPPING_ROUNDS = 50


def train_and_evaluate(
    spec: DatasetSpec,
    task: TaskSpec,
    frame: pd.DataFrame,
    seed: int,
    smoke: bool,
    return_details: bool = False,
):
    import lightgbm as lgb
    from sklearn.metrics import average_precision_score, roc_auc_score

    if smoke:
        train_mask = frame["split"] == "train"
        keep = frame[train_mask].head(SMOKE_MAX_ROWS).index
        frame = pd.concat([frame.loc[keep], frame[~train_mask]])

    features = build_features(spec, task, frame)
    label = frame["label"].astype(int).reset_index(drop=True)
    split = frame["split"].reset_index(drop=True)
    features = features.reset_index(drop=True)

    parts = {
        name: (features[split == name], label[split == name])
        for name in ("train", "val", "test")
    }
    model = lgb.LGBMClassifier(
        n_estimators=SMOKE_TREES if smoke else FULL_TREES,
        learning_rate=0.05,
        random_state=seed,
        deterministic=True,
        force_row_wise=True,
        n_jobs=1,
        verbosity=-1,
    )
    fit_kwargs = {}
    if not smoke:
        fit_kwargs = {
            "eval_set": [parts["val"]],
            "eval_metric": "auc",
            "callbacks": [lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)],
        }
    model.fit(*parts["train"], **fit_kwargs)

    x_test, y_test = parts["test"]
    proba = model.predict_proba(x_test)[:, 1]
    metrics = {
        "test_auroc": float(roc_auc_score(y_test, proba)),
        "test_avg_precision": float(average_precision_score(y_test, proba)),
    }
    if not return_details:
        return metrics
    # Per-row probabilities over the whole frame (frame order) plus the
    # feature matrix, for predictions output and the hybrid tier.
    details = {
        "proba": model.predict_proba(features)[:, 1],
        "features": features,
    }
    return metrics, details
