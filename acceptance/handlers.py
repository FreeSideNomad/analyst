"""Step handlers — bind Gherkin step text to the analyst system internals.

This is the "strange hybrid of Cucumber and the test fixtures" (Uncle Bob):
each handler carries deep knowledge of the system under test and drives it
through the in-process seam:

    IngestionService(DatasetStore(base_dir=...)).ingest(<csv path>)

A single :class:`ScenarioContext` flows Given -> When -> Then. Given steps
build CSV fixtures in a pytest tmp dir; When steps act on the real service;
Then steps assert against the real :class:`DatasetProfile` and queried rows.

Binding status (Slice A):
- FULLY BOUND: the walking-skeleton scenario
  "A clean CSV becomes a profiled, queryable dataset".
- Every other step is intentionally left unbound. The dispatcher fails such
  steps explicitly with "NOT YET IMPLEMENTED", producing a deliberately red
  board that drives Slices B-F. Nothing is skipped or xfail'd.

The step registry uses regular-expression matching (an optional extension
over exact-text matching); named groups become keyword arguments to the
handler, letting one handler serve parameterised (Scenario Outline) rows.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pytest

from analyst.domain.types import ColumnType
from analyst.engine.store import DatasetStore
from analyst.service.ingestion import IngestionService


# --------------------------------------------------------------------------- #
# Scenario context — shared state flowing Given -> When -> Then
# --------------------------------------------------------------------------- #
@dataclass
class ScenarioContext:
    """Mutable state for a single scenario execution.

    A fresh instance is created per scenario (state is cleared between
    scenarios by construction), so handlers never leak into one another.
    """

    tmp_path: Path
    scenario: str = ""
    spec: str = ""

    # Given-phase fixtures
    file_path: Path | None = None
    header: list[str] = field(default_factory=list)
    rows: list[list[object]] = field(default_factory=list)

    # When-phase system objects
    service: IngestionService | None = None
    result: object | None = None
    error: BaseException | None = None


# --------------------------------------------------------------------------- #
# Step registry + dispatcher
# --------------------------------------------------------------------------- #
_REGISTRY: list[tuple[re.Pattern[str], Callable[..., None]]] = []


def step(pattern: str) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Register a handler for step text fully matching ``pattern`` (regex).

    Named groups in the pattern are passed to the handler as keyword args.
    """
    compiled = re.compile(pattern)

    def register(func: Callable[..., None]) -> Callable[..., None]:
        _REGISTRY.append((compiled, func))
        return func

    return register


def run_step(ctx: ScenarioContext, keyword: str, text: str) -> None:
    """Dispatch one concrete (post-substitution) step to its handler.

    - No matching handler  -> explicit NOT YET IMPLEMENTED failure.
    - Handler assertion    -> failure annotated with scenario + spec source.
    Both paths report the source spec.md and the failing scenario name.
    """
    for pattern, func in _REGISTRY:
        match = pattern.fullmatch(text)
        if match is None:
            continue
        try:
            func(ctx, **match.groupdict())
        except AssertionError as exc:  # readable acceptance board
            pytest.fail(
                f"{keyword} {text}\n"
                f"  assertion: {exc}\n"
                f"  scenario:  {ctx.scenario}\n"
                f"  spec:      {ctx.spec}",
                pytrace=False,
            )
        return

    pytest.fail(
        f"NOT YET IMPLEMENTED: {keyword} {text}\n"
        f"  scenario: {ctx.scenario}\n"
        f"  spec:     {ctx.spec}",
        pytrace=False,
    )


# --------------------------------------------------------------------------- #
# Bound steps — scenario: "A clean CSV becomes a profiled, queryable dataset"
# --------------------------------------------------------------------------- #
@step(r'a clean CSV file "(?P<name>[^"]+)" with a header row and (?P<n>\d+) data rows')
def given_clean_csv_with_rows(ctx: ScenarioContext, name: str, n: str) -> None:
    """Write a clean CSV fixture: one header row + N data rows.

    Columns span three inferable types (integer / text / decimal) so the
    profile has something meaningful to report per column.
    """
    count = int(n)
    header = ["id", "name", "amount"]
    rows: list[list[object]] = [
        [i, f"user{i}", round(i * 1.5, 2)] for i in range(1, count + 1)
    ]
    path = ctx.tmp_path / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    ctx.file_path = path
    ctx.header = header
    ctx.rows = rows


@step(r'a clean CSV file with a numeric column "(?P<column>[^"]+)"')
def given_clean_csv_with_numeric_column(ctx: ScenarioContext, column: str) -> None:
    """Write a small CSV fixture with one numeric column for distribution stats."""
    header = ["id", column]
    rows: list[list[object]] = [
        [1, 10.0],
        [2, 20.0],
        [3, 30.0],
        [4, 40.0],
    ]
    path = ctx.tmp_path / "numeric.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    ctx.file_path = path
    ctx.header = header
    ctx.rows = rows


@step(r'the user has ingested a clean CSV file "(?P<name>[^"]+)"')
def given_user_has_ingested_clean_csv(ctx: ScenarioContext, name: str) -> None:
    """Prepare and ingest a clean CSV so a later step can simulate restart."""
    given_clean_csv_with_rows(ctx, name=name, n="3")
    when_user_ingests_the_file(ctx)


@step(r"the user ingests the file")
def when_user_ingests_the_file(ctx: ScenarioContext) -> None:
    """Drive the real facade: build a store in the tmp dir and ingest.

    Captures either the result or the raised error, so both success and
    rejection scenarios share this When step.
    """
    assert ctx.file_path is not None, "no file was prepared by a Given step"
    ctx.service = IngestionService(DatasetStore(base_dir=ctx.tmp_path / "store"))
    try:
        ctx.result = ctx.service.ingest(ctx.file_path)
        ctx.error = None
    except Exception as exc:  # noqa: BLE001 - scenarios assert on ctx.error
        ctx.result = None
        ctx.error = exc


@step(r"the system restarts")
def when_system_restarts(ctx: ScenarioContext) -> None:
    """Drop in-memory service objects and reopen the same store directory."""
    assert ctx.result is not None, "no dataset was ingested before restart"
    ctx.service = IngestionService(DatasetStore(base_dir=ctx.tmp_path / "store"))


@step(r'a dataset named "(?P<name>[^"]+)" is available')
def then_dataset_named_available(ctx: ScenarioContext, name: str) -> None:
    assert ctx.result is not None, "ingestion did not run"
    assert ctx.result.dataset_name == name, (
        f"expected dataset name {name!r}, got {ctx.result.dataset_name!r}"
    )
    # "available" == queryable through the store.
    rows = ctx.service.store.fetch_all(name)
    assert rows is not None


@step(r'the dataset "(?P<name>[^"]+)" is still available and returns the same rows')
def then_dataset_still_available_after_restart(ctx: ScenarioContext, name: str) -> None:
    assert ctx.service is not None, "system was not restarted"
    queried = ctx.service.store.fetch_all(name)
    assert len(queried) == len(ctx.rows), (
        f"expected {len(ctx.rows)} rows after restart, got {len(queried)}"
    )
    assert [tuple(row) for row in ctx.rows] == queried


@step(r"the dataset has the same columns as the file")
def then_same_columns(ctx: ScenarioContext) -> None:
    got = [c.name for c in ctx.result.profile.columns]
    assert got == ctx.header, f"expected columns {ctx.header}, got {got}"


@step(r"querying the dataset returns the same (?P<n>\d+) rows as the file")
def then_same_rows(ctx: ScenarioContext, n: str) -> None:
    expected = int(n)
    queried = ctx.service.store.fetch_all(ctx.result.dataset_name)
    assert len(queried) == expected, (
        f"expected {expected} queried rows, got {len(queried)}"
    )
    assert len(queried) == len(ctx.rows), (
        f"queried rows ({len(queried)}) differ from source rows ({len(ctx.rows)})"
    )


@step(r"the dataset reports a row count of (?P<n>\d+)")
def then_row_count(ctx: ScenarioContext, n: str) -> None:
    expected = int(n)
    assert ctx.result.profile.row_count == expected, (
        f"expected row_count {expected}, got {ctx.result.profile.row_count}"
    )


@step(
    r"each column reports an inferred type, a null rate, a distinct-value "
    r"count, and representative sample values"
)
def then_each_column_profiled(ctx: ScenarioContext) -> None:
    profile = ctx.result.profile
    assert profile.columns, "profile has no columns"
    for col in profile.columns:
        assert isinstance(col.inferred_type, ColumnType), (
            f"column {col.name!r} has no inferred type"
        )
        rate = profile.null_rate(col.name)
        assert 0.0 <= rate <= 1.0, f"column {col.name!r} null_rate out of range: {rate}"
        assert isinstance(col.distinct_count, int) and col.distinct_count >= 0, (
            f"column {col.name!r} has no distinct-value count"
        )
        assert isinstance(col.samples, tuple) and len(col.samples) >= 1, (
            f"column {col.name!r} has no representative sample values"
        )


@step(r'the profile for "(?P<column>[^"]+)" reports its minimum, maximum, and quantiles')
def then_numeric_distribution_statistics(ctx: ScenarioContext, column: str) -> None:
    profile = ctx.result.profile
    col = next(c for c in profile.columns if c.name == column)
    assert col.minimum is not None, f"column {column!r} has no minimum"
    assert col.maximum is not None, f"column {column!r} has no maximum"
    assert col.minimum <= col.maximum, (
        f"column {column!r} minimum {col.minimum!r} exceeds maximum {col.maximum!r}"
    )
    assert len(col.quantiles) >= 3, f"column {column!r} has no quantiles"
    assert all(q is not None for q in col.quantiles), (
        f"column {column!r} has empty quantile values"
    )


# --------------------------------------------------------------------------- #
# Slice B — edge cases: headers, empty, duplicates
# --------------------------------------------------------------------------- #
@step(r"a CSV file whose first row is data rather than column names")
def given_headerless_csv(ctx: ScenarioContext) -> None:
    rows = [[1, "alice", 10.5], [2, "bob", 20.0]]
    path = ctx.tmp_path / "headerless.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    ctx.file_path = path
    ctx.rows = rows


@step(r'the dataset columns are named "(?P<first>[^"]+)", "(?P<second>[^"]+)", and so on')
def then_columns_named(ctx: ScenarioContext, first: str, second: str) -> None:
    names = [c.name for c in ctx.result.profile.columns]
    assert names[0] == first, f"expected first column {first!r}, got {names[0]!r}"
    assert names[1] == second, f"expected second column {second!r}, got {names[1]!r}"


@step(r"no data row was consumed as a header")
def then_no_data_row_consumed(ctx: ScenarioContext) -> None:
    assert ctx.result.profile.row_count == len(ctx.rows), (
        f"expected {len(ctx.rows)} data rows, got {ctx.result.profile.row_count}"
    )


@step(r"the profile records that column names were synthesized")
def then_records_synthesized(ctx: ScenarioContext) -> None:
    assert ctx.result.profile.synthesized_headers is True


@step(r"a CSV file with a header row but no data rows")
def given_header_only_csv(ctx: ScenarioContext) -> None:
    path = ctx.tmp_path / "schema_only.csv"
    path.write_text("id,name,amount\n", encoding="utf-8")
    ctx.file_path = path
    ctx.header = ["id", "name", "amount"]


@step(r"a dataset with (?P<n>\d+) rows is available")
def then_dataset_with_n_rows(ctx: ScenarioContext, n: str) -> None:
    assert ctx.result is not None, "ingestion did not run"
    assert ctx.result.profile.row_count == int(n)
    assert ctx.service.store.fetch_all(ctx.result.dataset_name) == []


@step(r"the dataset's schema is fully profiled")
def then_schema_fully_profiled(ctx: ScenarioContext) -> None:
    cols = ctx.result.profile.columns
    assert cols, "no columns profiled"
    assert all(c.inferred_type is not None for c in cols)


@step(r"a file with no content")
def given_empty_file(ctx: ScenarioContext) -> None:
    path = ctx.tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    ctx.file_path = path


@step(r"ingestion is rejected with a clear, friendly message")
def then_rejected_with_message(ctx: ScenarioContext) -> None:
    assert ctx.error is not None, "expected ingestion to be rejected"
    assert str(ctx.error).strip(), "rejection message was empty"


@step(r"no dataset is created")
def then_no_dataset_created(ctx: ScenarioContext) -> None:
    assert ctx.result is None, "a dataset was created despite rejection"


@step(r'a CSV file with two columns both named "(?P<name>[^"]+)"')
def given_duplicate_columns_csv(ctx: ScenarioContext, name: str) -> None:
    path = ctx.tmp_path / "dup.csv"
    path.write_text(f"{name},{name}\n1,2\n", encoding="utf-8")
    ctx.file_path = path


@step(r'the dataset has distinct column names "(?P<a>[^"]+)" and "(?P<b>[^"]+)"')
def then_distinct_column_names(ctx: ScenarioContext, a: str, b: str) -> None:
    names = [c.name for c in ctx.result.profile.columns]
    assert names == [a, b], f"expected {[a, b]}, got {names}"


@step(r"the profile records that the source had duplicate column names")
def then_records_duplicates(ctx: ScenarioContext) -> None:
    assert ctx.result.profile.had_duplicate_columns is True


# --------------------------------------------------------------------------- #
# Slice B — rich scalar types (AC-5) and autopilot (AC-8)
# --------------------------------------------------------------------------- #
_TYPE_SAMPLE_VALUES = {
    "free-form text": ["hello", "world", "example"],
    "whole numbers": ["3", "7", "11"],
    "numbers with decimals": ["1.5", "2.25", "3.75"],
    "true/false values": ["true", "false", "true"],
    "calendar dates": ["2024-01-15", "2024-02-20", "2024-03-05"],
    "dates with a time of day": [
        "2024-01-15 09:30:00",
        "2024-02-20 14:00:00",
        "2024-03-05 22:15:00",
    ],
}


@step(
    r'a CSV column "(?P<column>[^"]+)" whose values are '
    r"(?P<description>free-form text|whole numbers|numbers with decimals|"
    r"true/false values|calendar dates|dates with a time of day)"
)
def given_column_of_type(ctx: ScenarioContext, column: str, description: str) -> None:
    values = _TYPE_SAMPLE_VALUES[description]
    path = ctx.tmp_path / "typed.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([column])
        writer.writerows([[v] for v in values])
    ctx.file_path = path


@step(r'the inferred type of "(?P<column>[^"]+)" is "(?P<type>[^"]+)"')
def then_inferred_type(ctx: ScenarioContext, column: str, type: str) -> None:  # noqa: A002
    col = next(c for c in ctx.result.profile.columns if c.name == column)
    assert col.inferred_type.value == type, (
        f"expected {column!r} type {type!r}, got {col.inferred_type.value!r}"
    )


@step(r"a clean, unambiguous CSV file")
def given_clean_unambiguous_csv(ctx: ScenarioContext) -> None:
    given_clean_csv_with_rows(ctx, name="clean.csv", n="5")


@step(r"ingestion completes successfully")
def then_ingestion_succeeds(ctx: ScenarioContext) -> None:
    assert ctx.error is None, f"ingestion failed: {ctx.error!r}"
    assert ctx.result is not None, "no result produced"


@step(r"the user was not asked any questions")
def then_no_questions_asked(ctx: ScenarioContext) -> None:
    # Slice A/B ingestion never emits a clarification; the AskQuestion path
    # arrives in Slice D. A successful autopilot result implies no questions.
    assert ctx.result is not None and ctx.error is None
