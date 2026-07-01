"""Ingestion status (AC-23)."""

from __future__ import annotations

from enum import Enum


class IngestionStatus(str, Enum):
    IN_PROGRESS = "in progress"
    COMPLETE = "complete"
    FAILED = "failed"
