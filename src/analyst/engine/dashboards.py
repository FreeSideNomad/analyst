"""Dashboard filter machinery — feature 015 (engine layer).

Widget SQL must carry the literal ``/*FILTERS*/`` marker inside its WHERE
clause (``WHERE /*FILTERS*/ 1=1``). Applying filters substitutes the marker
with equality clauses — values escaped by quote-doubling — so filters
re-scope the data BEFORE aggregation, the only semantically correct place.
The substituted SELECT is re-guarded by the caller before execution, so a
hostile filter value can never escape its string literal AND never reach
execution unvalidated.
"""

from __future__ import annotations

FILTER_MARKER = "/*FILTERS*/"


class InvalidWidgetSQLError(ValueError):
    """A widget query without the filter marker cannot join a dashboard."""


def validate_widget_sql(sql: str) -> None:
    if FILTER_MARKER not in sql:
        raise InvalidWidgetSQLError(
            "A widget query must contain the /*FILTERS*/ marker in its WHERE "
            "clause so dashboard filters can re-scope it."
        )


def _escape(value: str) -> str:
    return value.replace("'", "''")


def apply_filters(sql: str, filters: list[tuple[str, str]]) -> str:
    """Substitute the marker with AND-ed equality clauses (or nothing)."""
    validate_widget_sql(sql)
    clauses = "".join(
        f"(\"{column}\" = '{_escape(str(value))}') AND " for column, value in filters
    )
    return sql.replace(FILTER_MARKER, clauses, 1).replace(FILTER_MARKER, "")
