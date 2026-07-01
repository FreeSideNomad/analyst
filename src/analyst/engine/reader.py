"""CSV reader — inspects a file and produces a ReadPlan for materialization.

Handles the messiness the profiler cannot see once data is in DuckDB:
encoding detection, header detection / synthesis, and duplicate-column
disambiguation (AC-10, AC-11, AC-12, AC-13). Bulk data stays local.
"""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from pathlib import Path


class EmptyFileError(ValueError):
    """Raised when a file has no usable content (AC-11)."""


def _detect_encoding(raw: bytes) -> str:
    """Deterministic encoding detection (AC-13).

    BOM markers are authoritative; otherwise prefer strict UTF-8, then fall
    back to a Western single-byte codec (cp1252 decodes any byte sequence).
    Deterministic beats a probabilistic guesser for single-byte codecs, whose
    bytes are decodable by many codecs and thus inherently ambiguous.
    """
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


@dataclass(frozen=True)
class ReadPlan:
    """How to read a delimited file: encoding, header handling, final columns."""

    encoding: str
    has_header: bool
    column_names: tuple[str, ...]
    synthesized_headers: bool = False
    had_duplicate_columns: bool = False


def _looks_numeric(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    try:
        float(value)
        return True
    except ValueError:
        return False


def _disambiguate(names: list[str]) -> tuple[list[str], bool]:
    """Make column names unique by suffixing (_2, _3, ...). Returns (names, had_dupe)."""
    seen: dict[str, int] = {}
    out: list[str] = []
    had_dupe = False
    for name in names:
        if name in seen:
            had_dupe = True
            seen[name] += 1
            out.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 1
            out.append(name)
    return out, had_dupe


class CsvReader:
    """Inspects a delimited file to plan its ingestion."""

    def plan(self, path: str | os.PathLike[str]) -> ReadPlan:
        raw = Path(path).read_bytes()
        if not raw.strip():
            raise EmptyFileError("The file is empty — there is no data to ingest.")

        encoding = _detect_encoding(raw)
        text = raw.decode(encoding, errors="replace")

        reader = csv.reader(io.StringIO(text))
        first_row = next(reader, [])
        if not first_row:
            raise EmptyFileError("The file has no columns.")

        has_header = not any(_looks_numeric(cell) for cell in first_row)
        if has_header:
            base = [cell.strip() for cell in first_row]
            synthesized = False
        else:
            base = [f"column_{i}" for i in range(1, len(first_row) + 1)]
            synthesized = True

        column_names, had_dupe = _disambiguate(base)
        return ReadPlan(
            encoding=encoding,
            has_header=has_header,
            column_names=tuple(column_names),
            synthesized_headers=synthesized,
            had_duplicate_columns=had_dupe,
        )
