"""User entity (feature 004). Pure — no I/O, no framework imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    provider: str | None  # "google" | "microsoft" | "dev" | None (stub)
    is_admin: bool

    @property
    def has_signed_in(self) -> bool:
        """Stub users (added by an admin before their first sign-in) have no
        provider yet; the account is claimed by e-mail match on sign-in."""
        return self.provider is not None
