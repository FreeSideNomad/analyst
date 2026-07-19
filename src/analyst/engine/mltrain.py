"""The trainer — feature 012 (engine layer). FIXED, COMMITTED CODE.

The LLM never writes training code: it proposes features and teaching
notes; THIS function is the only thing that trains. Both models — linear
regression (the teaching anchor) and LightGBM (the upgrade) — share one
deterministic preprocessing pipeline so their metrics are comparable by
construction.

Structural guarantees (mutation-gated by the board):
- the target can never enter the feature space (excluded here, not by
  convention);
- the holdout is split once, by seed, and never touches `fit`;
- same inputs + same seed => identical metrics (LightGBM deterministic
  settings).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pandas.api.types as ptypes


class LeakageError(ValueError):
    """The target (or nothing at all) was offered as the feature set."""


# The bounded parameter schema (AC-10): the agent AND the UI move only
# these knobs, only within these ranges.
PARAMETER_SCHEMA: dict[str, dict] = {
    "n_estimators": {"min": 50, "max": 2000, "default": 400},
    "learning_rate": {"min": 0.005, "max": 0.5, "default": 0.05},
    "holdout": {"min": 0.1, "max": 0.4, "default": 0.2},
    "seed": {"min": 0, "max": 2**31 - 1, "default": 42},
}


def validate_params(params: dict) -> dict:
    """Defaults filled, bounds enforced; out-of-bounds is a plain error."""
    out = {}
    for name, spec in PARAMETER_SCHEMA.items():
        value = params.get(name, spec["default"])
        if not spec["min"] <= value <= spec["max"]:
            raise ValueError(
                f"Parameter '{name}' must be between {spec['min']} and "
                f"{spec['max']} (got {value})."
            )
        out[name] = value
    unknown = set(params) - set(PARAMETER_SCHEMA)
    if unknown:
        raise ValueError(f"Unknown parameters: {sorted(unknown)}")
    return out


@dataclass(frozen=True)
class TrainedResult:
    metrics: dict  # {"linear": {"r2","mae"}, "gbm": {"r2","mae"}}
    importances: tuple[tuple[str, float], ...]  # top gbm features, weighted
    predictions: pd.DataFrame  # every row: actual, predicted (gbm), is_holdout
    row_count: int
    holdout_count: int
    params: dict


def train(
    frame: pd.DataFrame, target: str, features: list[str], params: dict | None = None
) -> TrainedResult:
    from lightgbm import LGBMRegressor
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    clean = validate_params(params or {})
    if not features:
        raise LeakageError("At least one feature is required.")
    if target in features:
        raise LeakageError(
            f"'{target}' is the value being predicted — it cannot also be a "
            "feature (that would be answering the question with the answer)."
        )
    missing = [f for f in features if f not in frame.columns]
    if missing:
        raise LeakageError(f"Unknown feature column(s): {missing}")

    y = pd.to_numeric(frame[target], errors="coerce")
    keep = y.notna()
    X = frame.loc[keep, features]
    y = y[keep]

    train_idx, hold_idx = train_test_split(
        X.index, test_size=clean["holdout"], random_state=clean["seed"]
    )
    assert set(train_idx).isdisjoint(hold_idx)  # structural: never overlaps

    categorical = [c for c in features if not ptypes.is_numeric_dtype(X[c])]
    numeric = [c for c in features if c not in categorical]
    preprocess = ColumnTransformer(
        [
            ("num", "passthrough", numeric),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical,
            ),
        ]
    )
    X_train, y_train = X.loc[train_idx], y.loc[train_idx]
    X_hold, y_hold = X.loc[hold_idx], y.loc[hold_idx]
    # NaNs in numeric features: median-impute deterministically from TRAIN only.
    medians = X_train[numeric].median(numeric_only=True)
    X_train = X_train.fillna(medians)
    X_hold = X_hold.fillna(medians)
    X_all = X.fillna(medians)

    linear = Pipeline([("pre", preprocess), ("m", LinearRegression())])
    linear.fit(X_train, y_train)
    gbm = Pipeline(
        [
            ("pre", preprocess),
            (
                "m",
                LGBMRegressor(
                    random_state=clean["seed"],
                    n_estimators=clean["n_estimators"],
                    learning_rate=clean["learning_rate"],
                    deterministic=True,
                    force_row_wise=True,
                    verbose=-1,
                ),
            ),
        ]
    )
    gbm.fit(X_train, y_train)

    def scores(model) -> dict:  # noqa: ANN001
        predicted = model.predict(X_hold)
        return {
            "r2": round(float(r2_score(y_hold, predicted)), 4),
            "mae": round(float(mean_absolute_error(y_hold, predicted)), 2),
        }

    names = list(gbm.named_steps["pre"].get_feature_names_out())
    raw_importance = gbm.named_steps["m"].feature_importances_
    per_feature: dict[str, float] = {}
    for name, value in zip(names, raw_importance):
        base = name.split("__", 1)[-1]
        for feature in features:
            if base == feature or base.startswith(f"{feature}_"):
                per_feature[feature] = per_feature.get(feature, 0.0) + float(value)
                break
    total = sum(per_feature.values()) or 1.0
    importances = tuple(
        sorted(
            ((f, round(v / total, 4)) for f, v in per_feature.items()),
            key=lambda item: -item[1],
        )
    )

    predictions = pd.DataFrame(
        {
            "actual": y,
            "predicted": gbm.predict(X_all).round(2),
            "is_holdout": X.index.isin(hold_idx),
        },
        index=X.index,
    )
    return TrainedResult(
        metrics={"linear": scores(linear), "gbm": scores(gbm)},
        importances=importances,
        predictions=predictions,
        row_count=len(X),
        holdout_count=len(hold_idx),
        params=clean,
    )
