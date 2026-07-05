"""Step handlers for feature 011 — encrypted-at-rest credentials.

Scenarios bind over the in-process seam: a workspace repository + database
manager over the pytest tmp_path, connecting a synthetic SQLite database whose
ConnectionSpec carries a username/password (unused by SQLite but sealed and
persisted like any credential, so the secret's whole lifecycle is observable
offline). "The service restarts" rebuilds the workspace stack over the same
data directory, resolving the operator key exactly as production does
(ANALYST_SECRET_KEY / ANALYST_SECRET_KEY_FILE via load_operator_key). The
read-only-guidance scenario binds to the shipped connect form's content.
No browser, no live model calls.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from acceptance.e2e_base import ScenarioContext, make_registry

step, run_step = make_registry()

__all__ = ["ScenarioContext", "run_step"]

REPO_ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "s3cret-pw"
PASSPHRASE = "acceptance-key-1"


# --------------------------------------------------------------------------- #
# State + workspace machinery
# --------------------------------------------------------------------------- #
def _state(ctx: ScenarioContext) -> dict[str, Any]:
    if not isinstance(ctx.data, dict):
        ctx.data = {"managers": {}, "repos": {}, "snapshot": None, "log": ""}
    return ctx.data


def _set_key(value: str | None, file_path: Path | None = None) -> None:
    os.environ.pop("ANALYST_SECRET_KEY", None)
    os.environ.pop("ANALYST_SECRET_KEY_FILE", None)
    if file_path is not None:
        os.environ["ANALYST_SECRET_KEY_FILE"] = str(file_path)
    elif value is not None:
        os.environ["ANALYST_SECRET_KEY"] = value


def _data_dir(ctx: ScenarioContext, workspace: str) -> Path:
    return ctx.tmp_path / "workspaces" / workspace


def _build_stack(ctx: ScenarioContext, workspace: str):  # noqa: ANN202
    """A fresh repository + manager for one workspace, keyed by the SAME
    operator-key resolution production uses."""
    from analyst.api.repository import StoreRepository
    from analyst.api.routes.databases import DatabaseManager
    from analyst.engine.credentials import CredentialVault, load_operator_key

    st = _state(ctx)
    repo = StoreRepository(str(_data_dir(ctx, workspace)))
    key = load_operator_key()
    manager = DatabaseManager(repo=repo, vault=CredentialVault(key) if key else None)
    st["repos"][workspace] = repo
    st["managers"][workspace] = manager
    return repo, manager


def _manager(ctx: ScenarioContext, workspace: str = "main"):  # noqa: ANN202
    return _state(ctx)["managers"][workspace]


def _repo(ctx: ScenarioContext, workspace: str = "main"):  # noqa: ANN202
    return _state(ctx)["repos"][workspace]


def _drain(manager) -> None:  # noqa: ANN001
    if manager._pool is not None:
        manager._pool.shutdown(wait=True)
        manager._pool = None


def _crm_db(ctx: ScenarioContext) -> Path:
    path = ctx.tmp_path / "db" / "crm.sqlite"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path)
        con.execute(
            "CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, region TEXT)"
        )
        con.executemany(
            "INSERT INTO customers VALUES (?, ?)", [(10, "North"), (20, "South")]
        )
        con.commit()
        con.close()
    return path


def _connect(ctx: ScenarioContext, workspace: str = "main") -> None:
    from analyst.domain.connection import ConnectionSpec, DatabaseEngine

    repo, manager = _build_stack(ctx, workspace)
    manager.connect(
        ConnectionSpec(
            name="crm",
            engine=DatabaseEngine.SQLITE,
            path=str(_crm_db(ctx)),
            user="reader",
            password=PASSWORD,
        )
    )
    _drain(manager)
    record = repo.get_dataset("crm.customers")
    _state(ctx)["snapshot"] = (
        record.summary.catalog.table_description if record else None
    )


def _restart(ctx: ScenarioContext, workspaces: tuple[str, ...] = ("main",)) -> None:
    st = _state(ctx)
    for manager in st["managers"].values():
        manager.close()
    st["managers"].clear()
    st["repos"].clear()
    handler = logging.Handler()
    lines: list[str] = []
    handler.emit = lambda record: lines.append(record.getMessage())  # type: ignore[method-assign]
    root = logging.getLogger("analyst")
    root.addHandler(handler)
    try:
        for workspace in workspaces:
            _repo_, manager = _build_stack(ctx, workspace)
            manager.restore_persisted()
            _drain(manager)
    finally:
        root.removeHandler(handler)
    st["log"] = "\n".join(lines)


def _vault_file(ctx: ScenarioContext, workspace: str = "main") -> Path:
    return _data_dir(ctx, workspace) / "connections.vault.json"


def _store_files(ctx: ScenarioContext, workspace: str = "main"):  # noqa: ANN202
    return [p for p in _data_dir(ctx, workspace).rglob("*") if p.is_file()]


# --------------------------------------------------------------------------- #
# Given — key configuration + fixtures
# --------------------------------------------------------------------------- #
@step(r"the operator key is configured")
def given_key(ctx: ScenarioContext) -> None:
    _set_key(PASSPHRASE)


@step(r"the operator key is configured as a secret file")
def given_key_file(ctx: ScenarioContext) -> None:
    secret = ctx.tmp_path / "analyst_secret_key"
    secret.write_text(PASSPHRASE + "\n", encoding="utf-8")
    _set_key(None, file_path=secret)


@step(r"the operator key is configured through the environment")
def given_key_env(ctx: ScenarioContext) -> None:
    _set_key(PASSPHRASE)


@step(r"no operator key is configured")
def given_no_key(ctx: ScenarioContext) -> None:
    _set_key(None)


@step(r"a database is connected with credentials")
def given_connected(ctx: ScenarioContext) -> None:
    _connect(ctx, "main")


@step(r'a database is connected with credentials in workspace "alpha"')
def given_connected_alpha(ctx: ScenarioContext) -> None:
    _connect(ctx, "alpha")


@step(r"the database becomes unreachable while the service is down")
def given_db_gone(ctx: ScenarioContext) -> None:
    db = _crm_db(ctx)
    db.rename(ctx.tmp_path / "db" / "crm.hidden")


@step(r"the stored credential record is tampered with")
def given_tampered(ctx: ScenarioContext) -> None:
    import json

    path = _vault_file(ctx)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["crm"] = data["crm"][:-6] + "XXXXXX"
    path.write_text(json.dumps(data), encoding="utf-8")


# --------------------------------------------------------------------------- #
# When — restarts, retries, detach
# --------------------------------------------------------------------------- #
@step(r"the service restarts")
def when_restart(ctx: ScenarioContext) -> None:
    workspaces = tuple(sorted(_state(ctx)["repos"])) or ("main",)
    if "alpha" in workspaces:
        workspaces = ("alpha", "beta")  # AC-11: the other workspace comes up too
    _restart(ctx, workspaces)


@step(r"the service restarts with a different operator key")
def when_restart_other_key(ctx: ScenarioContext) -> None:
    _set_key("a-completely-different-key")
    _restart(ctx)


@step(r"the service restarts with no operator key")
def when_restart_no_key(ctx: ScenarioContext) -> None:
    _set_key(None)
    _restart(ctx)


@step(r"the database becomes reachable again and the user retries the connection")
def when_retry(ctx: ScenarioContext) -> None:
    (ctx.tmp_path / "db" / "crm.hidden").rename(ctx.tmp_path / "db" / "crm.sqlite")
    manager = _manager(ctx)
    manager.reconnect("crm")
    _drain(manager)


@step(r"the user detaches the connection")
def when_detach(ctx: ScenarioContext) -> None:
    _manager(ctx).detach("crm")


# --------------------------------------------------------------------------- #
# Then — reconnect outcomes
# --------------------------------------------------------------------------- #
@step(r"the connection is remembered for the next session")
def then_remembered(ctx: ScenarioContext) -> None:
    from analyst.engine.credentials import VaultStore

    tokens = VaultStore(_data_dir(ctx, "main")).all()
    assert "crm" in tokens, "no sealed record was stored for the connection"


@step(r"the database is connected again without re-entering credentials")
def then_reconnected(ctx: ScenarioContext) -> None:
    schemas = _manager(ctx).list()
    assert [s.name for s in schemas] == ["crm"], f"got {schemas!r}"
    assert schemas[0].status == "connected"


@step(r"its tables are queryable")
def then_queryable(ctx: ScenarioContext) -> None:
    record = _repo(ctx).get_dataset("crm.customers")
    assert record is not None and record.db_queryable


@step(r"its tables show their previously derived descriptions immediately")
def then_descriptions_immediate(ctx: ScenarioContext) -> None:
    record = _repo(ctx).get_dataset("crm.customers")
    assert record.catalog_status == "complete"
    assert record.summary.catalog.table_description == _state(ctx)["snapshot"]


@step(r"the workspace store contains no trace of the operator key")
def then_key_not_at_rest(ctx: ScenarioContext) -> None:
    for path in _store_files(ctx):
        assert PASSPHRASE.encode() not in path.read_bytes(), f"key found in {path}"


# --------------------------------------------------------------------------- #
# Then — degraded states
# --------------------------------------------------------------------------- #
@step(r"the connection is listed as unreachable")
def then_unreachable(ctx: ScenarioContext) -> None:
    (schema,) = _manager(ctx).list()
    assert schema.name == "crm" and schema.status == "unreachable"


@step(r"it still shows its previously derived descriptions")
def then_still_described(ctx: ScenarioContext) -> None:
    record = _repo(ctx).get_dataset("crm.customers")
    assert record is not None, "the unreachable connection lost its tables"
    assert record.summary.catalog.table_description == _state(ctx)["snapshot"]


@step(r"the connection does not reappear")
def then_gone(ctx: ScenarioContext) -> None:
    assert _manager(ctx).list() == []


@step(r"the service is working normally")
def then_service_ok(ctx: ScenarioContext) -> None:
    records = _repo(ctx).ingest("ok.csv", b"a,b\n1,2\n")
    assert records and records[0].summary.profile.row_count == 1


@step(r"the connection works for the session")
def then_works_now(ctx: ScenarioContext) -> None:
    (schema,) = _manager(ctx).list()
    assert schema.name == "crm" and schema.status == "connected"


@step(r"nothing about the connection is persisted")
def then_nothing_persisted(ctx: ScenarioContext) -> None:
    assert not _vault_file(ctx).exists()


# --------------------------------------------------------------------------- #
# Then — security
# --------------------------------------------------------------------------- #
@step(r"no file in the workspace store contains the password")
def then_no_password_at_rest(ctx: ScenarioContext) -> None:
    for path in _store_files(ctx):
        assert PASSWORD.encode() not in path.read_bytes(), (
            f"plaintext password found in {path}"
        )


@step(r"no listed connection carries a password")
def then_no_password_on_wire(ctx: ScenarioContext) -> None:
    for schema in _manager(ctx).list():
        dumped = schema.dump()
        assert "password" not in {k.lower() for k in dumped}
        assert PASSWORD not in str(dumped)


@step(r"no listed connection reveals its sealed credentials")
def then_no_token_on_wire(ctx: ScenarioContext) -> None:
    from analyst.engine.credentials import VaultStore

    tokens = VaultStore(_data_dir(ctx, "main")).all().values()
    listing = str([s.dump() for s in _manager(ctx).list()])
    for token in tokens:
        assert token not in listing


@step(r"the reconnect activity log contains no password")
def then_no_password_in_log(ctx: ScenarioContext) -> None:
    assert PASSWORD not in _state(ctx)["log"]


# --------------------------------------------------------------------------- #
# Then — isolation + guidance
# --------------------------------------------------------------------------- #
@step(r'workspace "alpha" has the connection again')
def then_alpha_has_it(ctx: ScenarioContext) -> None:
    schemas = _manager(ctx, "alpha").list()
    assert [s.name for s in schemas] == ["crm"]


@step(r'workspace "beta" does not see it')
def then_beta_does_not(ctx: ScenarioContext) -> None:
    assert _manager(ctx, "beta").list() == []


@step(r"the connection form offers guidance to use a read-only database account")
def then_read_only_guidance(ctx: ScenarioContext) -> None:
    form = (
        REPO_ROOT / "frontend" / "src" / "components" / "DatabasePanel.tsx"
    ).read_text(encoding="utf-8")
    assert "read-only database account" in form
