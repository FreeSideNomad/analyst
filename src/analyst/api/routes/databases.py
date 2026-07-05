"""Database federation routes (feature 005) — connect / list / detach.

Wire rule, enforced by construction: NO response model in this module has a
password field. The secret stays inside the server-side ``ConnectionSpec``.

Connected tables are registered on the active repository as plain
``DatasetRecord``s named ``<connection>.<table>`` — profiled through the
federated connection and catalogued deterministically (no LLM). The manager
holder follows the repository instance, so the test-only ``/api/_reset``
(which swaps the repository) implicitly resets connections too.
"""

from __future__ import annotations

import dataclasses
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from analyst.agentic import enrich
from analyst.api.deps import get_repository
from analyst.api.repository import DatasetRecord, DatasetRepository
from analyst.api.schemas import Camel
from analyst.domain.catalog import CatalogEntry
from analyst.domain.connection import (
    ConnectionSpec,
    DatabaseEngine,
    ForeignKey,
    InvalidConnectionError,
    TableKeys,
    catalog_for_table,
)
from analyst.domain.dataset import DatasetSummary
from analyst.domain.relationships import (
    DECLARED,
    OPTIONAL,
    REQUIRED,
    Relationship,
)
from analyst.domain.status import IngestionStatus
from analyst.engine.federation import (
    DuplicateConnectionError,
    FederatedTable,
    FederationError,
    FederationService,
    UnknownConnectionError,
)

# A cataloguing strategy: (table, workspace relationships) -> CatalogEntry.
CatalogFn = Callable[[FederatedTable, tuple[Relationship, ...]], CatalogEntry]

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
# Wire schemas (no password on ANY response model)
# --------------------------------------------------------------------------- #
class ConnectRequest(Camel):
    name: str
    engine: str
    path: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None  # accepted, stored server-side, never echoed

    def to_spec(self) -> ConnectionSpec:
        try:
            engine = DatabaseEngine(self.engine)
        except ValueError:
            raise InvalidConnectionError(
                f"Unknown database engine '{self.engine}'. "
                f"Supported: {', '.join(e.value for e in DatabaseEngine)}."
            ) from None
        return ConnectionSpec(
            name=self.name,
            engine=engine,
            path=self.path,
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
        )


class ForeignKeySchema(Camel):
    columns: list[str]
    referenced_table: str
    referenced_columns: list[str]

    @classmethod
    def from_domain(cls, fk: ForeignKey) -> "ForeignKeySchema":
        return cls(
            columns=list(fk.columns),
            referenced_table=fk.referenced_table,
            referenced_columns=list(fk.referenced_columns),
        )


class ConnectedTableSchema(Camel):
    name: str
    dataset_id: str
    row_count: int
    primary_key: list[str] = []
    foreign_keys: list[ForeignKeySchema] = []

    @classmethod
    def from_domain(
        cls, connection: str, table: FederatedTable
    ) -> "ConnectedTableSchema":
        keys = table.keys or TableKeys(table=table.name)
        return cls(
            name=table.name,
            dataset_id=f"{connection}.{table.name}",
            row_count=table.profile.row_count,
            primary_key=list(keys.primary_key),
            foreign_keys=[ForeignKeySchema.from_domain(f) for f in keys.foreign_keys],
        )


class DatabaseSchema(Camel):
    name: str
    engine: str
    database: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    path: Optional[str] = None
    tables: list[ConnectedTableSchema] = []


# --------------------------------------------------------------------------- #
# Manager — federation service + repository record registration
# --------------------------------------------------------------------------- #
def _declared_relationships(
    tables: tuple[FederatedTable, ...],
) -> tuple[Relationship, ...]:
    """Single-column declared FKs across a connection (AC-1)."""
    null_counts = {
        (t.name, c.name): c.null_count for t in tables for c in t.profile.columns
    }
    out: list[Relationship] = []
    for table in tables:
        if not table.keys:
            continue
        for fk in table.keys.foreign_keys:
            if len(fk.columns) != 1 or len(fk.referenced_columns) != 1:
                continue
            child_col = fk.columns[0]
            has_nulls = null_counts.get((table.name, child_col), 0) > 0
            out.append(
                Relationship(
                    child_table=table.name,
                    child_column=child_col,
                    parent_table=fk.referenced_table,
                    parent_column=fk.referenced_columns[0],
                    origin=DECLARED,
                    join_type=OPTIONAL if has_nulls else REQUIRED,
                    coverage=1.0,
                )
            )
    return tuple(out)


def _enrich_catalog_fn(
    table: FederatedTable, relationships: tuple[Relationship, ...]
) -> CatalogEntry:
    """Default LLM-free, data-grounded cataloguing (deterministic, offline)."""
    keys = table.keys.primary_key if table.keys else ()
    return enrich.catalog_entry(table.name, table.profile, relationships, keys=keys)


@dataclass
class DatabaseManager:
    """Thin orchestration: FederationService ↔ repository dataset records.

    Connecting returns promptly with each table marked ``pending`` and a
    placeholder description; a bounded background pool then catalogues each table
    for real, flipping it to ``complete`` (or ``failed``, contained per table).
    """

    repo: DatasetRepository
    service: FederationService = field(default_factory=FederationService)
    catalog_fn: CatalogFn = _enrich_catalog_fn
    max_workers: int = 4
    catalog_delay: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _pool: ThreadPoolExecutor | None = field(default=None, repr=False)

    def connect(self, spec: ConnectionSpec) -> DatabaseSchema:
        spec.validate()
        tables = self.service.connect(spec)
        relationships = _declared_relationships(tables)
        # 1) Immediate records: stub catalog + pending status; return promptly.
        records = [
            DatasetRecord(
                summary=DatasetSummary(
                    name=f"{spec.name}.{table.name}",
                    profile=table.profile,
                    catalog=catalog_for_table(
                        table.name,
                        spec.engine.label,
                        spec.name,
                        table.profile,
                        table.keys,
                    ),
                ),
                file_name=f"{spec.name}.{table.name}",
                status=IngestionStatus.COMPLETE,
                ingested_at=time.strftime("%Y-%m-%d"),
                federated=True,  # catalogued + visible, but not Q&A-queryable yet
                catalog_status="pending",
            )
            for table in tables
        ]
        self.repo.add_records(records)
        # 2) Background cataloguing (bounded concurrency), contained per table.
        pool = self._ensure_pool()
        for table in tables:
            pool.submit(self._catalogue_one, spec.name, table, relationships)
        return self._schema(spec)

    def _ensure_pool(self) -> ThreadPoolExecutor:
        if self._pool is None:
            self._pool = ThreadPoolExecutor(
                max_workers=self.max_workers, thread_name_prefix="catalog"
            )
        return self._pool

    def _catalogue_one(
        self,
        connection: str,
        table: FederatedTable,
        relationships: tuple[Relationship, ...],
    ) -> None:
        name = f"{connection}.{table.name}"
        try:
            if self.catalog_delay:
                time.sleep(self.catalog_delay)
            entry = self.catalog_fn(table, relationships)
            self._apply(name, entry, "complete")
        except Exception:  # noqa: BLE001 - failure is contained to this table
            self._apply(name, None, "failed")

    def _apply(self, name: str, entry: CatalogEntry | None, status: str) -> None:
        with self._lock:
            record = self.repo.get_dataset(name)
            if record is None:  # detached mid-flight — drop silently
                return
            if entry is not None:
                record.summary = dataclasses.replace(record.summary, catalog=entry)
            record.catalog_status = status

    def list(self) -> list[DatabaseSchema]:
        return [self._schema(spec) for spec in self.service.list()]

    def detach(self, name: str) -> None:
        tables = self.service.tables(name)  # raises UnknownConnectionError
        self.service.detach(name)
        self.repo.remove_records([f"{name}.{t.name}" for t in tables])

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None
        self.service.close()

    def _schema(self, spec: ConnectionSpec) -> DatabaseSchema:
        summary = spec.summary()
        return DatabaseSchema(
            name=summary.name,
            engine=summary.engine.value,
            database=summary.database,
            host=summary.host,
            port=summary.port,
            user=summary.user,
            path=summary.path,
            tables=[
                ConnectedTableSchema.from_domain(spec.name, t)
                for t in self.service.tables(spec.name)
            ],
        )


def get_manager(request: Request) -> DatabaseManager:
    """The manager bound to the current WORKSPACE's repository (HIGH H6).

    Managers are kept PER workspace repo — a workspace switch must never close
    another tenant's live connections. Each workspace repo is a stable singleton
    in the repo holder, so keying on its identity is safe and persistent.
    """
    repo = get_repository(request)
    managers = request.app.state.__dict__.setdefault("database_managers", {})
    key = id(repo)
    if key not in managers:
        managers[key] = DatabaseManager(
            repo=repo,
            catalog_fn=_configured_catalog_fn(),
            catalog_delay=_catalog_delay(),
        )
    return managers[key]


def _configured_catalog_fn() -> CatalogFn:
    """Live/cassette LLM cataloguing when configured, else data-grounded local."""
    from analyst.api.app import build_cataloguer
    from analyst.domain.catalog import payload_from_profile

    cataloguer = build_cataloguer()
    if cataloguer is None:
        return _enrich_catalog_fn

    def fn(
        table: FederatedTable, relationships: tuple[Relationship, ...]
    ) -> CatalogEntry:
        mine = tuple(r for r in relationships if r.child_table == table.name)
        payload = payload_from_profile(table.name, table.profile)
        return cataloguer.catalog(payload, mine)  # type: ignore[attr-defined]

    return fn


def _catalog_delay() -> float:
    """Make the pending → complete transition observable in the demo/e2e app.

    Defaults to a short delay in fixtures mode (so progress is visible) and 0 in
    the real store, where model latency provides the natural delay. Override
    with ANALYST_CATALOG_DELAY.
    """
    from analyst.api.app import fixtures_enabled

    override = os.environ.get("ANALYST_CATALOG_DELAY")
    if override is not None:
        return float(override)
    return 1.0 if fixtures_enabled() else 0.0


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.post("/databases/connect", status_code=201)
def connect_database(
    body: ConnectRequest, manager: DatabaseManager = Depends(get_manager)
) -> dict:
    try:
        return manager.connect(body.to_spec()).dump()
    except InvalidConnectionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except DuplicateConnectionError as exc:
        raise HTTPException(409, str(exc)) from exc
    except FederationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/databases")
def list_databases(manager: DatabaseManager = Depends(get_manager)) -> list[dict]:
    return [schema.dump() for schema in manager.list()]


@router.delete("/databases/{name}", status_code=204)
def detach_database(name: str, manager: DatabaseManager = Depends(get_manager)) -> None:
    try:
        manager.detach(name)
    except UnknownConnectionError as exc:
        raise HTTPException(404, str(exc)) from exc
