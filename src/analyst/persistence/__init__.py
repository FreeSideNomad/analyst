"""Embedded app-state persistence (feature 004).

Per CHARTER §2: transactional app state (users, workspaces, memberships,
sessions) lives in file-backed SQLite; analytical data stays in
DuckDB/Parquet. Single image, no separate DB container.
"""

from analyst.persistence.appstate import AppState, SessionRecord
from analyst.persistence.signing import sign, unsign

__all__ = ["AppState", "SessionRecord", "sign", "unsign"]
