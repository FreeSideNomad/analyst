"""Graph model: relational deep learning on the schema-defined graph.

The dataset's tables become a relbench Database (rows = nodes, foreign keys =
edges); relbench/torch-frame encode each table's columns by semantic type and
a heterogeneous GraphSAGE passes messages along foreign-key edges. Temporal
neighbor sampling guarantees each seed only sees rows dated before its as-of
time. This is the paper's "features are learned, not engineered" model: the
only inputs are the raw tables and the schema.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pandas as pd

from ..builddb import db_path
from ..errors import RelgraphError
from ..schema import DatasetSpec, TaskSpec

CHANNELS = 128
NUM_LAYERS = 2
NUM_NEIGHBORS = [128, 128]
BATCH_SIZE = 256
MAX_EPOCHS = 50
PATIENCE = 10
# Small tasks see few gradient steps per epoch and need the hotter rate;
# large tasks (many capped batches) diverge into constant predictions with
# it. The threshold matches the reproducibility/thread cutoff.
LR_SMALL = 5e-3
LR_LARGE = 1e-3
LARGE_TASK_ROWS = 5000
MAX_POS_WEIGHT = 5.0

SMOKE_NUM_NEIGHBORS = [4, 4]
SMOKE_BATCH_SIZE = 64
SMOKE_MAX_TRAIN_BATCHES = 8
SMOKE_MAX_EVAL_BATCHES = 4

# Full runs on large tasks: cap gradient/validation work per epoch (training
# shuffles, so successive epochs still cover the data); test evaluation is
# never capped.
FULL_MAX_TRAIN_BATCHES = 32
FULL_MAX_VAL_BATCHES = 24

STYPE_BY_TYPE = {
    "int": "numerical",
    "float": "numerical",
    "bool": "categorical",
    "string": "categorical",
    "date": "timestamp",
    "timestamp": "timestamp",
}


def _seed_everything(seed: int) -> None:
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _load_database(spec: DatasetSpec, task: TaskSpec):
    """Read the built DuckDB database into a relbench Database, dropping the
    task's excluded outcome columns."""
    import duckdb
    from relbench.base import Database, Table

    db_file = db_path(spec.name)
    if not db_file.is_file():
        raise RelgraphError(
            f"no database for dataset '{spec.name}'; run `relgraph build` first"
        )
    con = duckdb.connect(str(db_file), read_only=True)
    tables: dict[str, Table] = {}
    try:
        for tname, table in spec.tables.items():
            df = con.execute(f'SELECT * FROM "{tname}"').df()
            for col in task.excluded_columns(tname):
                if col in df.columns:
                    df = df.drop(columns=[col])
            for col in table.columns:
                if col.type in ("date", "timestamp") and col.name in df.columns:
                    df[col.name] = pd.to_datetime(df[col.name]).astype("datetime64[ns]")
            tables[tname] = Table(
                df=df,
                fkey_col_to_pkey_table={
                    fk.column: fk.ref_table for fk in table.foreign_keys
                },
                pkey_col=table.primary_key,
                time_col=table.time_column,
            )
    finally:
        con.close()
    return Database(tables)


def _col_to_stype(spec: DatasetSpec, task: TaskSpec) -> dict:
    """Semantic types for feature columns, straight from the schema."""
    from torch_frame import stype

    out: dict[str, dict] = {}
    for tname, table in spec.tables.items():
        excluded = task.excluded_columns(tname)
        fkey_cols = {fk.column for fk in table.foreign_keys}
        cols = {}
        for col in table.columns:
            if col.name in excluded or col.name in fkey_cols:
                continue
            if col.name in (table.primary_key,):
                continue
            cols[col.name] = getattr(stype, STYPE_BY_TYPE[col.type])
        if not cols:
            cols["__const__"] = stype.numerical
        out[tname] = cols
    return out


def _ensure_const_columns(db, col_to_stype: dict) -> None:
    for tname, cols in col_to_stype.items():
        if "__const__" in cols:
            db.table_dict[tname].df["__const__"] = 1.0


class _Model:
    def __init__(
        self,
        data,
        col_stats,
        entity_table: str,
        seed: int,
        num_layers: int = NUM_LAYERS,
    ):
        import torch
        from relbench.modeling.nn import (
            HeteroEncoder,
            HeteroGraphSAGE,
            HeteroTemporalEncoder,
        )
        from torch.nn import Linear, Module, ModuleDict  # noqa: F401

        torch.manual_seed(seed)
        self.torch = torch
        self.entity_table = entity_table
        self.encoder = HeteroEncoder(
            channels=CHANNELS,
            node_to_col_names_dict={
                ntype: data[ntype].tf.col_names_dict for ntype in data.node_types
            },
            node_to_col_stats=col_stats,
        )
        self.temporal = HeteroTemporalEncoder(
            node_types=[nt for nt in data.node_types if "time" in data[nt]],
            channels=CHANNELS,
        )
        self.gnn = HeteroGraphSAGE(
            node_types=data.node_types,
            edge_types=data.edge_types,
            channels=CHANNELS,
            num_layers=num_layers,
        )
        self.head = torch.nn.Sequential(
            torch.nn.Linear(CHANNELS, CHANNELS),
            torch.nn.ReLU(),
            torch.nn.Linear(CHANNELS, 1),
        )
        self.modules = torch.nn.ModuleList(
            [self.encoder, self.temporal, self.gnn, self.head]
        )

    def parameters(self):
        return self.modules.parameters()

    def train(self):
        self.modules.train()

    def eval(self):
        self.modules.eval()

    def forward_with_embedding(self, batch):
        seed_time = batch[self.entity_table].seed_time
        x_dict = self.encoder(batch.tf_dict)
        rel_time = self.temporal(seed_time, batch.time_dict, batch.batch_dict)
        for ntype, t in rel_time.items():
            x_dict[ntype] = x_dict[ntype] + t
        x_dict = self.gnn(x_dict, batch.edge_index_dict)
        emb = x_dict[self.entity_table][: seed_time.size(0)]
        return self.head(emb).squeeze(-1), emb

    def forward(self, batch):
        return self.forward_with_embedding(batch)[0]


def _make_loader(
    data,
    entity_table: str,
    node_idx,
    seed_time,
    *,
    batch_size,
    num_neighbors,
    shuffle: bool,
    seed: int,
):
    import torch
    from torch_geometric.loader import NeighborLoader

    generator = torch.Generator()
    generator.manual_seed(seed)
    return NeighborLoader(
        data,
        num_neighbors=num_neighbors,
        input_nodes=(entity_table, node_idx),
        input_time=seed_time,
        time_attr="time",
        temporal_strategy="last",  # most recent valid neighbors carry signal
        batch_size=batch_size,
        shuffle=shuffle,
        generator=generator,
    )


def _patch_relbench_pandas3() -> None:
    """relbench 1.1.0 predates pandas 3: to_unix_time floor-divides the
    read-only array view pandas 3 returns. Replace it with a copy-safe
    equivalent (same values, same dtype)."""
    import numpy as np
    from relbench.modeling import graph as rb_graph
    from relbench.modeling import utils as rb_utils

    def to_unix_time(ser):
        assert ser.dtype in [np.dtype("datetime64[s]"), np.dtype("datetime64[ns]")]
        unix_time = np.asarray(ser.astype("int64")).copy()
        if ser.dtype == np.dtype("datetime64[ns]"):
            unix_time //= 10**9
        return unix_time

    rb_utils.to_unix_time = to_unix_time
    rb_graph.to_unix_time = to_unix_time


def train_and_evaluate(
    spec: DatasetSpec,
    task: TaskSpec,
    frame: pd.DataFrame,
    seed: int,
    smoke: bool,
    return_details: bool = False,
):
    import torch
    from relbench.modeling.graph import make_pkey_fkey_graph
    from sklearn.metrics import average_precision_score, roc_auc_score

    _patch_relbench_pandas3()

    _seed_everything(seed)
    large_task = len(frame) > LARGE_TASK_ROWS
    # Single-threaded CPU keeps same-seed runs bitwise reproducible; large
    # tasks trade that determinism for multi-threaded speed.
    if large_task:
        import os as _os

        torch.set_num_threads(min(8, _os.cpu_count() or 1))
    else:
        torch.set_num_threads(1)

    db = _load_database(spec, task)
    col_to_stype = _col_to_stype(spec, task)
    _ensure_const_columns(db, col_to_stype)

    # Map raw entity ids to graph node indices before relbench reindexes.
    entity_table = task.entity_table
    raw_pkey = db.table_dict[entity_table].df[spec.table(entity_table).primary_key]
    id_to_idx = {v: i for i, v in enumerate(raw_pkey)}

    db.reindex_pkeys_and_fkeys()
    data, col_stats = make_pkey_fkey_graph(db, col_to_stype)

    frame = frame.reset_index(drop=True)
    if smoke:
        train_part = frame[frame["split"] == "train"].head(
            SMOKE_MAX_TRAIN_BATCHES * SMOKE_BATCH_SIZE
        )
        frame = pd.concat([train_part, frame[frame["split"] != "train"]])

    def split_inputs_frame(part: pd.DataFrame):
        missing = [v for v in part[task.entity_column] if v not in id_to_idx]
        if missing:
            raise RelgraphError(
                f"task '{task.name}': {len(missing)} entity ids not present "
                f"in table '{entity_table}'"
            )
        idx = torch.tensor(
            [id_to_idx[v] for v in part[task.entity_column]], dtype=torch.long
        )
        seed_time = torch.tensor(
            pd.to_datetime(part["as_of"])
            .astype("datetime64[ns]")
            .astype("int64")
            .to_numpy()
            // 1_000_000_000,
            dtype=torch.long,
        )
        label = torch.tensor(part["label"].astype(float).to_numpy())
        return idx, seed_time, label

    def split_inputs(name: str):
        return split_inputs_frame(frame[frame["split"] == name])

    # Knowledge-layer hints: tasks whose signal sits more hops away declare
    # deeper sampling in their task metadata.
    full_neighbors = list(task.graph.get("num_neighbors", NUM_NEIGHBORS))
    num_layers = int(task.graph.get("num_layers", len(full_neighbors)))
    if len(full_neighbors) != num_layers:
        raise RelgraphError(
            f"task '{task.name}': graph num_neighbors "
            f"({len(full_neighbors)} hops) must match num_layers ({num_layers})"
        )
    batch_size = SMOKE_BATCH_SIZE if smoke else BATCH_SIZE
    num_neighbors = [4] * num_layers if smoke else full_neighbors
    loaders = {}
    labels = {}
    for name in ("train", "val", "test"):
        idx, seed_time, label = split_inputs(name)
        loaders[name] = _make_loader(
            data,
            entity_table,
            idx,
            seed_time,
            batch_size=batch_size,
            num_neighbors=num_neighbors,
            shuffle=(name == "train"),
            seed=seed,
        )
        labels[name] = label

    model = _Model(data, col_stats, entity_table, seed, num_layers=num_layers)
    lr = LR_LARGE if large_task else LR_SMALL
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    train_labels = labels["train"]
    pos = float(train_labels.sum())
    neg = float(len(train_labels) - pos)
    pos_weight = torch.tensor(min(neg / max(pos, 1.0), MAX_POS_WEIGHT))
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    def batch_labels(batch, name: str):
        # input_id indexes into the loader's input tensors, aligning each
        # seed with its label regardless of shuffling.
        return labels[name][batch[entity_table].input_id]

    def evaluate(name: str, max_batches: int | None):
        model.eval()
        preds, ys = [], []
        with torch.no_grad():
            for i, batch in enumerate(loaders[name]):
                if max_batches is not None and i >= max_batches:
                    break
                preds.append(torch.sigmoid(model.forward(batch)).numpy())
                ys.append(batch_labels(batch, name).numpy())
        pred = np.concatenate(preds) if preds else np.zeros(0)
        y = np.concatenate(ys) if ys else np.zeros(0)
        return pred, y

    max_epochs = 1 if smoke else MAX_EPOCHS
    max_train_batches = SMOKE_MAX_TRAIN_BATCHES if smoke else FULL_MAX_TRAIN_BATCHES
    max_val_batches = SMOKE_MAX_EVAL_BATCHES if smoke else FULL_MAX_VAL_BATCHES
    max_test_batches = SMOKE_MAX_EVAL_BATCHES if smoke else None
    best_val = -math.inf
    best_state = None
    epochs_since_best = 0
    for _ in range(max_epochs):
        model.train()
        for i, batch in enumerate(loaders["train"]):
            if max_train_batches is not None and i >= max_train_batches:
                break
            optimizer.zero_grad()
            loss = loss_fn(model.forward(batch), batch_labels(batch, "train"))
            loss.backward()
            optimizer.step()
        val_pred, val_y = evaluate("val", max_val_batches)
        val_auroc = (
            roc_auc_score(val_y, val_pred) if len(np.unique(val_y)) == 2 else 0.5
        )
        if val_auroc > best_val:
            best_val = val_auroc
            best_state = {
                k: v.detach().clone() for k, v in model.modules.state_dict().items()
            }
            epochs_since_best = 0
        else:
            epochs_since_best += 1
            if epochs_since_best >= PATIENCE:
                break
    if best_state is not None:
        model.modules.load_state_dict(best_state)

    pred, y = evaluate("test", max_test_batches)
    if len(np.unique(y)) < 2:
        raise RelgraphError(
            f"task '{task.name}': test evaluation saw only one label class"
        )
    metrics = {
        "test_auroc": float(roc_auc_score(y, pred)),
        "test_avg_precision": float(average_precision_score(y, pred)),
    }
    if not return_details:
        return metrics

    # Post-training detail pass (predictions + embeddings for every row of
    # the training frame, in frame order). Runs under no_grad on the best
    # weights; consumes no training RNG, so metrics above are unaffected.
    all_idx, all_seed_time, _ = split_inputs_frame(frame)
    detail_loader = _make_loader(
        data,
        entity_table,
        all_idx,
        all_seed_time,
        batch_size=batch_size,
        num_neighbors=num_neighbors,
        shuffle=False,
        seed=seed,
    )
    model.eval()
    probas, embeddings = [], []
    with torch.no_grad():
        for batch in detail_loader:
            out, emb = model.forward_with_embedding(batch)
            probas.append(torch.sigmoid(out).numpy())
            embeddings.append(emb.numpy())
    details = {
        "proba": np.concatenate(probas) if probas else np.zeros(0),
        "embeddings": (
            np.concatenate(embeddings) if embeddings else np.zeros((0, CHANNELS))
        ),
    }
    return metrics, details
