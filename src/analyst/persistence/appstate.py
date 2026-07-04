"""AppState — users, workspaces, memberships and sessions in embedded SQLite.

One connection, guarded by a lock (FastAPI sync endpoints run in a thread
pool). Store mode uses ``<data_dir>/app.sqlite3``; fixtures/tests use
``:memory:``. First user ever to sign in becomes admin and receives the
"Default" workspace (PRD FR-15).
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from analyst.domain.user import User
from analyst.domain.workspace import Membership, Workspace

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,
    email      TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    provider   TEXT,
    is_admin   INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
-- SECURITY M2: at most ONE admin, enforced at the DB level so a race between
-- workers (both seeing COUNT==0) can't create two admins — the second INSERT
-- fails the unique index and is retried as a non-admin.
CREATE UNIQUE INDEX IF NOT EXISTS one_admin ON users (is_admin) WHERE is_admin = 1;
CREATE TABLE IF NOT EXISTS workspaces (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    user_id      TEXT NOT NULL REFERENCES users(id),
    role         TEXT NOT NULL DEFAULT 'member',
    PRIMARY KEY (workspace_id, user_id)
);
CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id),
    workspace_id TEXT REFERENCES workspaces(id),
    created_at   REAL NOT NULL,
    expires_at   REAL NOT NULL
);
"""

SESSION_TTL_SECONDS = 7 * 24 * 3600
DEFAULT_WORKSPACE_NAME = "Default"


@dataclass(frozen=True)
class SessionRecord:
    id: str
    user_id: str
    workspace_id: str | None
    expires_at: float


def _new_id() -> str:
    return uuid.uuid4().hex


class AppState:
    """Transactional app state. All methods are thread-safe."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ users
    def sign_in(self, email: str, name: str, provider: str) -> User:
        """Get-or-create the user for a completed sign-in.

        The first user ever becomes admin and gets the Default workspace.
        A stub row (added by an admin via e-mail) is claimed by e-mail match.
        """
        email = email.strip().lower()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
            if row is not None:
                self._conn.execute(
                    "UPDATE users SET name = ?, provider = ? WHERE id = ?",
                    (name, provider, row["id"]),
                )
                self._conn.commit()
                return self._user(self._row("users", row["id"]))
            first = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            user_id = _new_id()
            try:
                self._conn.execute(
                    "INSERT INTO users (id, email, name, provider, is_admin,"
                    " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, email, name, provider, int(first), time.time()),
                )
            except sqlite3.IntegrityError:
                # M2: another worker won the admin race — insert as a non-admin.
                first = False
                self._conn.execute(
                    "INSERT INTO users (id, email, name, provider, is_admin,"
                    " created_at) VALUES (?, ?, ?, ?, 0, ?)",
                    (user_id, email, name, provider, time.time()),
                )
            if first:
                self._create_workspace_locked(DEFAULT_WORKSPACE_NAME, user_id)
            self._conn.commit()
            return self._user(self._row("users", user_id))

    def user_by_id(self, user_id: str) -> User | None:
        with self._lock:
            row = self._row("users", user_id)
        return self._user(row) if row else None

    def user_by_email(self, email: str) -> User | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
        return self._user(row) if row else None

    # ------------------------------------------------------------- workspaces
    def create_workspace(self, name: str, creator_id: str) -> Workspace:
        with self._lock:
            workspace = self._create_workspace_locked(name, creator_id)
            self._conn.commit()
        return workspace

    def _create_workspace_locked(self, name: str, creator_id: str) -> Workspace:
        ws_id = _new_id()
        self._conn.execute(
            "INSERT INTO workspaces (id, name, created_by, created_at)"
            " VALUES (?, ?, ?, ?)",
            (ws_id, name, creator_id, time.time()),
        )
        self._conn.execute(
            "INSERT INTO memberships (workspace_id, user_id, role)"
            " VALUES (?, ?, 'owner')",
            (ws_id, creator_id),
        )
        return Workspace(id=ws_id, name=name, created_by=creator_id)

    def add_member(self, workspace_id: str, email: str, name: str = "") -> Membership:
        """Add a member by e-mail; creates a stub user if they never signed in."""
        email = email.strip().lower()
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if row is None:
                user_id = _new_id()
                self._conn.execute(
                    "INSERT INTO users (id, email, name, provider, is_admin,"
                    " created_at) VALUES (?, ?, ?, NULL, 0, ?)",
                    (user_id, email, name or email.split("@")[0], time.time()),
                )
            else:
                user_id = row["id"]
            self._conn.execute(
                "INSERT OR IGNORE INTO memberships (workspace_id, user_id, role)"
                " VALUES (?, ?, 'member')",
                (workspace_id, user_id),
            )
            self._conn.commit()
        return Membership(workspace_id=workspace_id, user_id=user_id, role="member")

    def workspace_by_id(self, workspace_id: str) -> Workspace | None:
        with self._lock:
            row = self._row("workspaces", workspace_id)
        if row is None:
            return None
        return Workspace(id=row["id"], name=row["name"], created_by=row["created_by"])

    def workspaces_for(self, user_id: str) -> list[Workspace]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT w.* FROM workspaces w JOIN memberships m"
                " ON m.workspace_id = w.id WHERE m.user_id = ?"
                " ORDER BY w.created_at",
                (user_id,),
            ).fetchall()
        return [
            Workspace(id=r["id"], name=r["name"], created_by=r["created_by"])
            for r in rows
        ]

    def members_of(self, workspace_id: str) -> list[User]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT u.* FROM users u JOIN memberships m ON m.user_id = u.id"
                " WHERE m.workspace_id = ? ORDER BY u.created_at",
                (workspace_id,),
            ).fetchall()
        return [self._user(r) for r in rows]

    def is_member(self, user_id: str, workspace_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM memberships WHERE user_id = ? AND workspace_id = ?",
                (user_id, workspace_id),
            ).fetchone()
        return row is not None

    # --------------------------------------------------------------- sessions
    def create_session(self, user_id: str) -> SessionRecord:
        """Open a session; the active workspace defaults to the user's first."""
        workspaces = self.workspaces_for(user_id)
        workspace_id = workspaces[0].id if workspaces else None
        record = SessionRecord(
            id=_new_id(),
            user_id=user_id,
            workspace_id=workspace_id,
            expires_at=time.time() + SESSION_TTL_SECONDS,
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, user_id, workspace_id, created_at,"
                " expires_at) VALUES (?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.user_id,
                    record.workspace_id,
                    time.time(),
                    record.expires_at,
                ),
            )
            self._conn.commit()
        return record

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None or row["expires_at"] < time.time():
            return None
        return SessionRecord(
            id=row["id"],
            user_id=row["user_id"],
            workspace_id=row["workspace_id"],
            expires_at=row["expires_at"],
        )

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self._conn.commit()

    def set_active_workspace(self, session_id: str, workspace_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET workspace_id = ? WHERE id = ?",
                (workspace_id, session_id),
            )
            self._conn.commit()

    # ---------------------------------------------------------------- helpers
    def _row(self, table: str, row_id: str) -> sqlite3.Row | None:
        assert table in ("users", "workspaces")  # nosec - internal, fixed names
        return self._conn.execute(
            f"SELECT * FROM {table} WHERE id = ?",
            (row_id,),  # noqa: S608
        ).fetchone()

    @staticmethod
    def _user(row: sqlite3.Row | None) -> User:
        assert row is not None
        return User(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            provider=row["provider"],
            is_admin=bool(row["is_admin"]),
        )
