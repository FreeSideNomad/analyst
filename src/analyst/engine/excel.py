"""Excel reader — expands a workbook into one normalized CSV per non-empty sheet.

Each sheet becomes its own dataset (AC-6). By converting sheets to CSV we reuse
the delimited-file materialization path (encoding is moot; openpyxl gives us
unicode rows directly).
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from openpyxl import load_workbook

from analyst.engine.reader import MalformedFileError


def _sheet_has_content(rows: list[list[object]]) -> bool:
    return any(
        any(cell is not None and str(cell).strip() for cell in row) for row in rows
    )


class ExcelReader:
    """Reads an .xlsx/.xls workbook into per-sheet CSV files."""

    def sheets(
        self, path: str | os.PathLike[str], out_dir: Path
    ) -> list[tuple[str, Path]]:
        """Return (sheet_name, csv_path) for each non-empty sheet.

        Raises MalformedFileError if the workbook cannot be parsed.
        """
        try:
            workbook = load_workbook(filename=str(path), read_only=True, data_only=True)
        except Exception as exc:  # openpyxl raises several types on bad files
            raise MalformedFileError(
                f"The Excel file could not be read: {exc}"
            ) from exc

        out: list[tuple[str, Path]] = []
        for sheet in workbook.worksheets:
            rows = [list(r) for r in sheet.iter_rows(values_only=True)]
            if not _sheet_has_content(rows):
                continue
            csv_path = out_dir / f"sheet_{sheet.title}.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                for row in rows:
                    writer.writerow(["" if c is None else c for c in row])
            out.append((sheet.title, csv_path))
        workbook.close()
        return out
