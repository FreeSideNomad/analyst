"""Source acquisition: download, verify, extract into the local cache.

Cache layout (the executable contract with the acceptance suite):

  $RELGRAPH_CACHE_DIR/<dataset>/sources/<filename>   raw source files
  $RELGRAPH_CACHE_DIR/<dataset>/tables/<table>.csv   per-table data

A dataset counts as cached when every declared table file is present; in that
case download succeeds without touching the network. RELGRAPH_OFFLINE=1 makes
any non-file:// fetch fail immediately.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from .errors import RelgraphError
from .registry import cache_root
from .schema import DatasetSpec, SourceSpec


def offline() -> bool:
    return os.environ.get("RELGRAPH_OFFLINE") == "1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def table_file(dataset: str, table: str) -> Path:
    return cache_root() / dataset / "tables" / f"{table}.csv"


def is_cached(spec: DatasetSpec) -> bool:
    return all(
        table_file(spec.name, t.name).is_file()
        for t in spec.tables.values()
        if not t.derived
    )


def table_row_count(path: Path, encoding: str = "utf-8") -> int:
    with path.open("r", encoding=encoding, errors="replace") as f:
        return max(sum(1 for _ in f) - 1, 0)  # minus header


def _fetch(url: str, dest: Path) -> None:
    if url.startswith("file://"):
        src = Path(urllib.request.url2pathname(url[len("file://") :]))
        shutil.copyfile(src, dest)
        return
    if offline():
        raise RelgraphError(
            f"network access blocked (RELGRAPH_OFFLINE=1) while fetching {url}"
        )
    with urllib.request.urlopen(url, timeout=60) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)


def _kaggle_credentials_present() -> bool:
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    if os.environ.get("KAGGLE_API_TOKEN"):
        return True
    config_dir = os.environ.get("KAGGLE_CONFIG_DIR") or str(Path.home() / ".kaggle")
    return (Path(config_dir) / "kaggle.json").is_file()


def _fetch_kaggle(source: SourceSpec, dest_dir: Path) -> None:
    if not _kaggle_credentials_present():
        raise RelgraphError(
            "Kaggle credentials are not configured. Create a free Kaggle "
            "account, generate an API token (kaggle.com -> Settings -> API -> "
            "Create New Token), and either save it as ~/.kaggle/kaggle.json "
            "(or $KAGGLE_CONFIG_DIR/kaggle.json) or export KAGGLE_USERNAME "
            "and KAGGLE_KEY."
        )
    if offline():
        raise RelgraphError(
            f"network access blocked (RELGRAPH_OFFLINE=1) while fetching "
            f"Kaggle source {source.url}"
        )
    import kagglehub  # optional dependency, only needed for kaggle sources

    handle = source.url.removeprefix("kaggle://")
    downloaded = Path(kagglehub.dataset_download(handle))
    for f in downloaded.rglob("*"):
        if f.is_file():
            shutil.copyfile(f, dest_dir / f.name)


def _verify(source: SourceSpec, path: Path) -> None:
    if not source.sha256:
        return
    actual = sha256_file(path)
    if actual != source.sha256:
        raise RelgraphError(
            f"checksum mismatch for source '{source.name}' ({path.name}): "
            f"expected sha256 {source.sha256}, actual {actual}"
        )


def _fetch_verified(source: SourceSpec, url: str, dest: Path) -> None:
    """Fetch atomically: download to a temp file, verify, then rename. A
    truncated or corrupted transfer never poisons the cache. One retry for
    transient failures."""
    part = dest.with_suffix(dest.suffix + ".part")
    last_err: Exception | None = None
    for _ in range(2):
        part.unlink(missing_ok=True)
        try:
            _fetch(url, part)
            _verify(source, part)
            part.rename(dest)
            return
        except RelgraphError as e:
            if "network access blocked" in str(e):
                raise
            last_err = e
        except (urllib.error.URLError, OSError) as e:
            last_err = e
    part.unlink(missing_ok=True)
    raise last_err


def _obtain(source: SourceSpec, sources_dir: Path) -> tuple[Path, bool]:
    """Return (path to verified source file, used_fallback)."""
    dest = sources_dir / source.filename
    if dest.is_file():
        _verify(source, dest)
        return dest, False
    try:
        _fetch_verified(source, source.url, dest)
        return dest, False
    except (RelgraphError, urllib.error.URLError, OSError) as primary_err:
        if not source.fallback_url:
            if isinstance(primary_err, RelgraphError):
                raise
            raise RelgraphError(
                f"failed to download source '{source.name}' from {source.url}: "
                f"{primary_err}"
            )
        try:
            _fetch_verified(source, source.fallback_url, dest)
        except (RelgraphError, urllib.error.URLError, OSError) as fallback_err:
            raise RelgraphError(
                f"failed to download source '{source.name}': primary "
                f"{source.url} ({primary_err}); fallback {source.fallback_url} "
                f"({fallback_err})"
            )
        return dest, True


def _extract(
    spec: DatasetSpec, source: SourceSpec, src_path: Path, tables_dir: Path
) -> None:
    """Materialize tables/<table>.csv for tables served by this source."""
    if source.archive == "zip":
        with zipfile.ZipFile(src_path) as zf:
            members = {Path(m).name: m for m in zf.namelist() if not m.endswith("/")}
            for table in spec.tables.values():
                if table.file in members:
                    with (
                        zf.open(members[table.file]) as member,
                        (tables_dir / f"{table.name}.csv").open("wb") as out,
                    ):
                        shutil.copyfileobj(member, out)
        return
    for table in spec.tables.values():
        if table.file == source.filename:
            shutil.copyfile(src_path, tables_dir / f"{table.name}.csv")


def download(spec: DatasetSpec) -> list[str]:
    """Ensure every declared table is cached; return progress messages."""
    messages: list[str] = []
    dataset_cache = cache_root() / spec.name
    tables_dir = dataset_cache / "tables"
    sources_dir = dataset_cache / "sources"

    if is_cached(spec):
        messages.append(f"dataset '{spec.name}' is already cached; no download needed")
    else:
        tables_dir.mkdir(parents=True, exist_ok=True)
        sources_dir.mkdir(parents=True, exist_ok=True)
        for source in spec.sources:
            if source.kind == "kaggle":
                _fetch_kaggle(source, sources_dir)
                for table in spec.tables.values():
                    member = sources_dir / table.file
                    if member.is_file():
                        shutil.copyfile(member, tables_dir / f"{table.name}.csv")
                messages.append(f"source '{source.name}': downloaded from Kaggle")
                continue
            src_path, used_fallback = _obtain(source, sources_dir)
            _extract(spec, source, src_path, tables_dir)
            if used_fallback:
                messages.append(
                    f"source '{source.name}': primary source unreachable, "
                    f"downloaded from fallback {source.fallback_url}"
                )
            else:
                messages.append(f"source '{source.name}': ok")
        missing = [
            t.name
            for t in spec.tables.values()
            if not t.derived and not table_file(spec.name, t.name).is_file()
        ]
        if missing:
            raise RelgraphError(
                f"after downloading all sources, tables are still missing: "
                f"{', '.join(sorted(missing))}"
            )

    for tname, table in spec.tables.items():
        if table.derived:
            continue
        path = table_file(spec.name, tname)
        messages.append(f"table {tname}: {table_row_count(path, table.encoding)} rows")
    return messages
