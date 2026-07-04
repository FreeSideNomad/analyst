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

import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from analyst.api.deps import get_repository
from analyst.api.repository import DatasetRecord, DatasetRepository
from analyst.api.schemas import Camel
from analyst.domain.connection import (
    ConnectionSpec,
    DatabaseEngine,
    ForeignKey,
    InvalidConnectionError,
    TableKeys,
    catalog_for_table,
)
from analyst.domain.dataset import DatasetSummary
from analyst.domain.status import IngestionStatus
from analyst.engine.federation import (
    DuplicateConnectionError,
    FederatedTable,
    FederationError,
    FederationService,
    UnknownConnectionError,
)

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
@dataclass
class DatabaseManager:
    """Thin orchestration: FederationService ↔ repository dataset records."""

    repo: DatasetRepository
    service: FederationService = field(default_factory=FederationService)

    def connect(self, spec: ConnectionSpec) -> DatabaseSchema:
        spec.validate()
        tables = self.service.connect(spec)
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
            )
            for table in tables
        ]
        self.repo.add_records(records)
        return self._schema(spec)

    def list(self) -> list[DatabaseSchema]:
        return [self._schema(spec) for spec in self.service.list()]

    def detach(self, name: str) -> None:
        tables = self.service.tables(name)  # raises UnknownConnectionError
        self.service.detach(name)
        self.repo.remove_records([f"{name}.{t.name}" for t in tables])

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
        managers[key] = DatabaseManager(repo=repo)
    return managers[key]


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
