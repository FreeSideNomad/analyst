"""Workspace & membership entities (feature 004). Pure — no I/O."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    created_by: str  # user id


@dataclass(frozen=True)
class Membership:
    workspace_id: str
    user_id: str
    role: str  # "owner" | "member"
