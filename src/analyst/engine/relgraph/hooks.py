"""Dataset hooks: the knowledge layer's narrow, named escape hatch.

A dataset directory may contain hooks.py defining

    def transform(table_name: str, df: pandas.DataFrame) -> pandas.DataFrame

which is applied to each table after reading and before it is written to the
database. Everything that cannot be expressed declaratively (odd encodings,
identity fixes) lives there — never in the engine.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable

import pandas as pd

TransformFn = Callable[[str, "pd.DataFrame"], "pd.DataFrame"]


def load_transform(dataset_dir: Path) -> TransformFn | None:
    hooks_path = dataset_dir / "hooks.py"
    if not hooks_path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(
        f"relgraph_hooks_{dataset_dir.name}", hooks_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "transform", None)
