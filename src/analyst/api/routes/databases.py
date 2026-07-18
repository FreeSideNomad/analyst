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
import logging
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
from analyst.domain.workspace_context import (
    WorkspaceContext,
    build_workspace_context,
)
from analyst.engine.credentials import (
    CredentialVault,
    VaultError,
    VaultStore,
    load_operator_key,
)
from analyst.engine.federation import (
    DuplicateConnectionError,
    FederatedTable,
    FederationError,
    FederationService,
    UnknownConnectionError,
    _redact_secrets,
)

_LOG = logging.getLogger(__name__)

# A cataloguing strategy: (table, workspace relationships, workspace context)
# -> CatalogEntry (feature 010: the context carries the other tables' meanings).
CatalogFn = Callable[
    [FederatedTable, tuple[Relationship, ...], "WorkspaceContext | None"],
    CatalogEntry,
]

# Feature 007: engines with a DuckDB scanner whose tables can be ATTACHed into
# the store's connection for within-DB Q&A (push-down). Bridge-only engines
# (SQL Server / DB2) are visible + catalogued but not yet queryable.
_QUERYABLE_ENGINES = frozenset({DatabaseEngine.SQLITE, DatabaseEngine.POSTGRES})

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
            engine = DatabaseEngine((self.engine or "").strip())
        except ValueError:
            raise InvalidConnectionError(
                f"Unknown database engine '{self.engine}'. "
                f"Supported: {', '.join(e.value for e in DatabaseEngine)}."
            ) from None

        # Pasted values arrive with stray whitespace (a trailing space in a
        # SQLite path reads as a different, nonexistent file — defect
        # 2026-07-18). Strip everything except the password, whose spaces
        # may be real.
        def clean(value: str | None) -> str | None:
            return value.strip() if isinstance(value, str) else value

        return ConnectionSpec(
            name=clean(self.name) or "",
            engine=engine,
            path=clean(self.path),
            host=clean(self.host),
            port=self.port,
            database=clean(self.database),
            user=clean(self.user),
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
    status: str = "connected"  # feature 011: "connected" | "unreachable"
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
            if not fk.columns or len(fk.columns) != len(fk.referenced_columns):
                continue
            child_col = fk.columns[0]
            has_nulls = any(null_counts.get((table.name, c), 0) > 0 for c in fk.columns)
            out.append(
                Relationship(
                    child_table=table.name,
                    child_column=child_col,
                    parent_table=fk.referenced_table,
                    parent_column=fk.referenced_columns[0],
                    origin=DECLARED,
                    join_type=OPTIONAL if has_nulls else REQUIRED,
                    coverage=1.0,
                    extra_columns=tuple(zip(fk.columns[1:], fk.referenced_columns[1:])),
                )
            )
    return tuple(out)


def _enrich_catalog_fn(
    table: FederatedTable,
    relationships: tuple[Relationship, ...],
    context: WorkspaceContext | None = None,
) -> CatalogEntry:
    """Default LLM-free, data-grounded cataloguing (deterministic, offline)."""
    keys = table.keys.primary_key if table.keys else ()
    return enrich.catalog_entry(
        table.name, table.profile, relationships, keys=keys, context=context
    )


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
    # Feature 011 — sealed credential persistence. No vault (no operator key)
    # means connections stay session-only, exactly the pre-011 behavior.
    vault: CredentialVault | None = None
    _unreachable: "dict[str, ConnectionSpec]" = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _pool: ThreadPoolExecutor | None = field(default=None, repr=False)

    def connect(self, spec: ConnectionSpec) -> DatabaseSchema:
        spec.validate()
        tables = self.service.connect(spec)
        relationships = _declared_relationships(tables)
        # Feature 010: snapshot the pre-existing workspace's meanings BEFORE
        # registering this connection's records, so each table is catalogued
        # knowing its neighbours. A failure degrades to isolation (AC-10).
        context = self._workspace_context(relationships)
        # 1) Immediate records; return promptly. A table whose catalog was
        # persisted in a previous session — and whose schema is unchanged —
        # comes back complete at once (feature 010, AC-7); the rest start as
        # a stub catalog + pending status.
        persisted = {t.name: self._persisted_entry(spec.name, t) for t in tables}
        records = [
            DatasetRecord(
                summary=DatasetSummary(
                    name=f"{spec.name}.{table.name}",
                    profile=table.profile,
                    catalog=persisted[table.name]
                    or catalog_for_table(
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
                catalog_status="complete" if persisted[table.name] else "pending",
            )
            for table in tables
        ]
        self.repo.add_records(records)
        # Feature 007: for a scanner engine (sqlite/postgres) on the real store,
        # register the tables as views in the store's connection so within-DB
        # Q&A can execute planner SQL against them (push-down, read-only).
        self._attach_for_query(spec, tables, records)
        # 2) Background cataloguing (bounded concurrency), contained per table.
        # Tables restored from a persisted catalog are already complete.
        pool = self._ensure_pool()
        for table in tables:
            if persisted[table.name] is None:
                pool.submit(
                    self._catalogue_one, spec.name, table, relationships, context
                )
        # Feature 010 (AC-4): connecting may have created file↔DB relationships
        # — refresh the affected EXISTING tables' meanings in the background
        # (cross-source discovery reads through the scanner; keep connect prompt).
        pool.submit(self._recatalogue_neighbors, [r.name for r in records])
        # Feature 011 (AC-1): remember the connection, sealed, for next session.
        self._persist_credentials(spec)
        self._unreachable.pop(spec.name, None)
        return self._schema(spec)

    # ------------------------------------------------------------------ #
    # Feature 011 — sealed persistence + reconnect
    # ------------------------------------------------------------------ #
    def _vault_store(self) -> VaultStore | None:
        store = getattr(self.repo, "store", None)
        if store is None:  # fixtures — no disk, no persistence
            return None
        return VaultStore(store.base_dir)

    def _persist_credentials(self, spec: ConnectionSpec) -> None:
        if self.vault is None:
            return
        vault_store = self._vault_store()
        if vault_store is None:
            return
        try:
            vault_store.put(spec.name, self.vault.seal(spec))
        except Exception:  # noqa: BLE001 - persistence failure never fails connect
            _LOG.warning("could not persist credentials for %r", spec.name)

    def restore_persisted(self) -> None:
        """Reconnect this workspace's remembered databases (feature 011).

        Runs once when the manager is created. Fail-safe by construction: a
        record that cannot be opened (absent/changed key, tampered ciphertext)
        is ignored this session — kept on disk so restoring the right key
        later revives it — and the user simply re-enters. A reachable
        database reconnects through the normal path, so its persisted catalog
        (feature 010) is shown immediately; an unreachable one stays listed
        as retryable.
        """
        vault_store = self._vault_store()
        if vault_store is None or self.vault is None:
            return
        for name, token in sorted(vault_store.all().items()):
            try:
                spec = self.vault.open(token)
            except VaultError:
                _LOG.warning(
                    "stored credentials for %r could not be opened with the "
                    "configured key; re-entry required",
                    name,
                )
                continue
            try:
                self.connect(spec)
            except FederationError as exc:
                self._register_unreachable(spec, exc)
            except Exception as exc:  # noqa: BLE001 - one bad record is contained
                _LOG.warning(
                    "could not restore connection %r: %s",
                    name,
                    _redact_secrets(str(exc), spec),
                )

    def _register_unreachable(self, spec: ConnectionSpec, exc: Exception) -> None:
        """The remembered database didn't answer (feature 011, AC-4): keep it
        visible — listed as unreachable, its persisted meaning (feature 010)
        shown from the sidecars — and retryable without re-entry."""
        _LOG.warning(
            "remembered database %r is unreachable: %s",
            spec.name,
            _redact_secrets(str(exc), spec),
        )
        self._unreachable[spec.name] = spec
        loader = getattr(self.repo, "load_persisted_catalog", None)
        lister = getattr(self.repo, "persisted_connection_tables", None)
        if loader is None or lister is None:
            return
        records = []
        for name in lister(spec.name):
            loaded = loader(name)
            if loaded is None:
                continue
            entry, _fingerprint, profile = loaded
            if profile is None:
                continue
            records.append(
                DatasetRecord(
                    summary=DatasetSummary(name=name, profile=profile, catalog=entry),
                    file_name=name,
                    status=IngestionStatus.COMPLETE,
                    federated=True,
                    db_queryable=False,  # no live data until it reconnects
                    catalog_status="complete",
                )
            )
        self.repo.add_records(records)

    def reconnect(self, name: str) -> DatabaseSchema:
        """Retry an unreachable remembered connection (feature 011, AC-4) —
        with the sealed spec, so the user never re-enters credentials."""
        spec = self._unreachable.get(name)
        if spec is None:
            raise UnknownConnectionError(f"No unreachable connection named '{name}'.")
        return self.connect(spec)

    def _recatalogue_neighbors(self, new_names: list[str]) -> None:
        try:
            self.repo.recatalogue_affected(new_names)
        except Exception:  # noqa: BLE001 - contained (AC-10): connect is done
            _LOG.warning("retroactive re-cataloguing failed for %s", new_names)

    def _persisted_entry(
        self, connection: str, table: FederatedTable
    ) -> CatalogEntry | None:
        """A previous session's catalog for this table, iff the schema is
        unchanged (feature 010, AC-7). Anything else → derive afresh."""
        from analyst.api.repository import _schema_fingerprint

        loader = getattr(self.repo, "load_persisted_catalog", None)
        if loader is None:
            return None
        loaded = loader(f"{connection}.{table.name}")
        if loaded is None:
            return None
        entry, fingerprint, _profile = loaded
        if fingerprint != _schema_fingerprint(table.profile):
            return None
        return entry

    def _workspace_context(
        self, relationships: tuple[Relationship, ...]
    ) -> WorkspaceContext | None:
        try:
            return build_workspace_context(
                {r.name: r.summary.catalog for r in self.repo.list_datasets()},
                relationships,
            )
        except Exception:  # noqa: BLE001 - degrade to isolation, never fail connect
            return None

    def _attach_for_query(
        self,
        spec: ConnectionSpec,
        tables: tuple[FederatedTable, ...],
        records: list[DatasetRecord],
    ) -> None:
        store = getattr(self.repo, "store", None)
        if store is None or spec.engine not in _QUERYABLE_ENGINES:
            return
        try:
            store.attach_database(spec.name, spec, tuple(t.name for t in tables))
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, but LOUDLY
            # The connection stays catalogued + visible, but its tables are not
            # Q&A-queryable. Never silent: the operator needs to see WHY (a
            # missing DuckDB scanner extension, an unreachable host, etc.).
            _LOG.warning(
                "within-DB Q&A disabled for connection %r (%s): could not attach "
                "for query execution: %s",
                spec.name,
                spec.engine.value,
                _redact_secrets(str(exc), spec),
            )
            return
        for record in records:
            record.db_queryable = True

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
        context: WorkspaceContext | None = None,
    ) -> None:
        name = f"{connection}.{table.name}"
        try:
            if self.catalog_delay:
                time.sleep(self.catalog_delay)
            trimmed = context.for_table(table.name) if context is not None else None
            entry = self.catalog_fn(table, relationships, trimmed)
            self._apply(name, entry, "complete")
            self._persist(name, entry, table)
        except Exception:  # noqa: BLE001 - failure is contained to this table
            self._apply(name, None, "failed")

    def _persist(self, name: str, entry: CatalogEntry, table: FederatedTable) -> None:
        """Persist the derived catalog for the next session (feature 010, AC-6)."""
        saver = getattr(self.repo, "persist_catalog", None)
        if saver is None:
            return
        from analyst.api.repository import _schema_fingerprint

        try:
            saver(name, entry, _schema_fingerprint(table.profile), table.profile)
        except Exception:  # noqa: BLE001 - persistence failure never fails cataloguing
            _LOG.warning("could not persist catalog for %r", name)

    def _apply(self, name: str, entry: CatalogEntry | None, status: str) -> None:
        with self._lock:
            record = self.repo.get_dataset(name)
            if record is None:  # detached mid-flight — drop silently
                return
            if entry is not None:
                record.summary = dataclasses.replace(record.summary, catalog=entry)
            record.catalog_status = status

    def list(self) -> list[DatabaseSchema]:
        out = [self._schema(spec) for spec in self.service.list()]
        for _name, spec in sorted(self._unreachable.items()):
            summary = spec.summary()
            out.append(
                DatabaseSchema(
                    name=summary.name,
                    engine=summary.engine.value,
                    status="unreachable",
                    database=summary.database,
                    host=summary.host,
                    port=summary.port,
                    user=summary.user,
                    path=summary.path,
                    tables=[],
                )
            )
        return out

    def detach(self, name: str) -> None:
        tables = self.service.tables(name)  # raises UnknownConnectionError
        self.service.detach(name)
        store = getattr(self.repo, "store", None)
        if store is not None:
            store.detach_database(name)
        self.repo.remove_records([f"{name}.{t.name}" for t in tables])
        # Feature 011 (AC-5): detaching forgets the stored credentials.
        vault_store = self._vault_store()
        if vault_store is not None:
            vault_store.remove(name)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None
        # Review #6: symmetric with detach() — drop the store-side ATTACH + views
        # for every live connection, else a new manager on the same store fails to
        # re-ATTACH and the tables come back silently not-queryable.
        store = getattr(self.repo, "store", None)
        if store is not None:
            for schema in self.service.list():
                store.detach_database(schema.name)
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
        operator_key = load_operator_key()
        manager = DatabaseManager(
            repo=repo,
            catalog_fn=_configured_catalog_fn(),
            catalog_delay=_catalog_delay(),
            vault=CredentialVault(operator_key) if operator_key else None,
        )
        managers[key] = manager
        # Feature 011 (AC-2): the workspace's remembered databases come back
        # before its first request is answered — no re-entry.
        manager.restore_persisted()
    return managers[key]


def _configured_catalog_fn() -> CatalogFn:
    """Live/cassette LLM cataloguing when configured, else data-grounded local."""
    from analyst.api.app import build_cataloguer
    from analyst.domain.catalog import payload_from_profile

    cataloguer = build_cataloguer()
    if cataloguer is None:
        return _enrich_catalog_fn

    def fn(
        table: FederatedTable,
        relationships: tuple[Relationship, ...],
        context: WorkspaceContext | None = None,
    ) -> CatalogEntry:
        mine = tuple(r for r in relationships if r.child_table == table.name)
        payload = payload_from_profile(table.name, table.profile)
        return cataloguer.catalog(payload, mine, context=context)  # type: ignore[attr-defined]

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


@router.post("/databases/{name}/reconnect")
def reconnect_database(
    name: str, manager: DatabaseManager = Depends(get_manager)
) -> dict:
    """Retry an unreachable remembered connection (feature 011, AC-4)."""
    try:
        return manager.reconnect(name).dump()
    except UnknownConnectionError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FederationError as exc:
        raise HTTPException(502, str(exc)) from exc
