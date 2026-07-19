"""Task materialization: run a task's label query, assign out-of-time splits,
validate, and write the training table.

The label query must return the entity id column, an `as_of` time column, and
a binary `label` column. Splits come from the dataset's cutoff timestamps:
train (as_of < val), val (val <= as_of < test), test (as_of >= test).
"""

from __future__ import annotations

import duckdb
import pandas as pd

from .builddb import db_path
from .errors import RelgraphError
from .registry import cache_root
from .schema import DatasetSpec, TaskSpec

REQUIRED_COLUMNS = {"as_of", "label"}


def training_table_path(dataset: str, task: str):
    return cache_root() / dataset / "tasks" / f"{task}.parquet"


def _run_label_query(spec: DatasetSpec, task: TaskSpec) -> pd.DataFrame:
    db = db_path(spec.name)
    if not db.is_file():
        raise RelgraphError(
            f"no database for dataset '{spec.name}'; run `relgraph build` first"
        )
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(task.label_query).df()
    except duckdb.BinderException as e:
        raise RelgraphError(f"label query for task '{task.name}' is invalid: {e}")
    except duckdb.Error as e:
        raise RelgraphError(f"label query for task '{task.name}' failed: {e}")
    finally:
        con.close()


def assign_splits(
    df: pd.DataFrame, val_timestamp: str, test_timestamp: str
) -> pd.DataFrame:
    as_of = pd.to_datetime(df["as_of"])
    val_ts = pd.Timestamp(val_timestamp)
    test_ts = pd.Timestamp(test_timestamp)
    split = pd.Series("train", index=df.index)
    split[as_of >= val_ts] = "val"
    split[as_of >= test_ts] = "test"
    out = df.copy()
    out["split"] = split
    return out


def validate_training_table(task: TaskSpec, df: pd.DataFrame) -> None:
    if df.empty:
        raise RelgraphError(
            f"task '{task.name}': the training table is empty "
            f"(the label query returned no rows)"
        )
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise RelgraphError(
            f"task '{task.name}': label query must return columns "
            f"{sorted(REQUIRED_COLUMNS)}; missing {sorted(missing)}"
        )
    bad = set(pd.unique(df["label"])) - {0, 1}
    if bad:
        raise RelgraphError(
            f"task '{task.name}': labels must be 0 or 1, found {sorted(bad)}"
        )
    for split_name in ("train", "val", "test"):
        part = df[df["split"] == split_name]
        counts = part["label"].value_counts().to_dict()
        if part.empty:
            raise RelgraphError(f"task '{task.name}': split '{split_name}' is empty")
        if len(counts) < 2:
            raise RelgraphError(
                f"task '{task.name}': split '{split_name}' contains only one "
                f"label class (class counts: {counts})"
            )


def materialize(spec: DatasetSpec, task: TaskSpec) -> list[str]:
    df = _run_label_query(spec, task)
    if not df.empty and "as_of" in df.columns:
        df = assign_splits(df, spec.val_timestamp, spec.test_timestamp)
    else:
        df["split"] = pd.Series(dtype="object")
    validate_training_table(task, df)

    path = training_table_path(spec.name, task.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.register("training_table", df)
        con.execute(f"COPY training_table TO '{path.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()

    messages = [f"training table written to {path}"]
    for split_name in ("train", "val", "test"):
        part = df[df["split"] == split_name]
        pos = int((part["label"] == 1).sum())
        messages.append(
            f"{split_name}: {len(part)} rows, {pos} positive / "
            f"{len(part) - pos} negative"
        )
    return messages


def load_training_table(dataset: str, task: str) -> pd.DataFrame:
    path = training_table_path(dataset, task)
    if not path.is_file():
        raise RelgraphError(
            f"task '{task}' is not materialized for dataset '{dataset}'; "
            f"run `relgraph task` first"
        )
    return pd.read_parquet(path)
