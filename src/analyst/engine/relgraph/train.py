"""Training orchestration: dispatch to a model, write the run artifact."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .errors import RelgraphError
from .schema import DatasetSpec, TaskSpec
from .tasks import load_training_table

MODELS = ("graph", "baseline")


def _config_fingerprint(dataset: str, task: str, model: str, smoke: bool) -> str:
    payload = json.dumps(
        {
            "dataset": dataset,
            "task": task,
            "model": model,
            "smoke": smoke,
            "engine_version": 1,
        },
        sort_keys=True,
    )
    return "cfg-" + hashlib.sha256(payload.encode()).hexdigest()[:12]


def train(
    spec: DatasetSpec,
    task: TaskSpec,
    model: str,
    seed: int,
    smoke: bool,
    runs_dir: Path,
) -> dict:
    if model not in MODELS:
        raise RelgraphError(
            f"unknown model '{model}' (choose from: {', '.join(MODELS)})"
        )
    frame = load_training_table(spec.name, task.name)
    split_sizes = {
        name: int((frame["split"] == name).sum()) for name in ("train", "val", "test")
    }

    if model == "baseline":
        from .models.baseline import train_and_evaluate
    else:
        from .models.graph import train_and_evaluate
    metrics = train_and_evaluate(spec, task, frame, seed=seed, smoke=smoke)

    artifact = {
        "dataset": spec.name,
        "task": task.name,
        "model": model,
        "seed": seed,
        "config_fingerprint": _config_fingerprint(spec.name, task.name, model, smoke),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "split_sizes": split_sizes,
        "metrics": metrics,
        "smoke": smoke,
    }
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = artifact["recorded_at"].replace(":", "").replace(".", "").replace("+", "")
    path = runs_dir / f"{spec.name}_{task.name}_{model}_{stamp}.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    artifact["_path"] = str(path)
    return artifact
