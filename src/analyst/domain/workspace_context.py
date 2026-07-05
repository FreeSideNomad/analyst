"""WorkspaceContext (feature 010) — the metadata a table is catalogued WITH.

The context a cataloguer receives about the rest of the workspace: the other
tables' names + descriptions, the columns of tables the target is directly
related to, and the relationship graph. Metadata-only BY CONSTRUCTION — the
types can hold names, descriptions, roles and relationships, never rows — so
the governance bound (AC-8) is structural, not policed at call sites.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from analyst.domain.catalog import CatalogEntry, ColumnDescription
from analyst.domain.relationships import Relationship


@dataclass(frozen=True)
class TableContext:
    """One already-catalogued sibling table, as seen by the cataloguer."""

    name: str
    description: str
    columns: tuple[ColumnDescription, ...] = ()


@dataclass(frozen=True)
class WorkspaceContext:
    """The rest of the workspace, for cataloguing one table in context."""

    tables: tuple[TableContext, ...] = ()
    relationships: tuple[Relationship, ...] = ()

    def describe(self, table: str) -> str | None:
        for t in self.tables:
            if t.name == table:
                return t.description
        return None

    def _linked_to(self, table: str) -> set[str]:
        linked: set[str] = set()
        for r in self.relationships:
            if r.child_table == table:
                linked.add(r.parent_table)
            elif r.parent_table == table:
                linked.add(r.child_table)
        return linked

    def for_table(self, table: str) -> "WorkspaceContext":
        """The context as the cataloguer of ``table`` should see it: the table
        itself excluded, sibling columns kept only for direct links (the
        approved deep-context depth)."""
        linked = self._linked_to(table)
        return WorkspaceContext(
            tables=tuple(
                t if t.name in linked else replace(t, columns=())
                for t in self.tables
                if t.name != table
            ),
            relationships=self.relationships,
        )


def build_workspace_context(
    catalogs: Mapping[str, CatalogEntry | None],
    relationships: tuple[Relationship, ...] = (),
) -> WorkspaceContext:
    """Assemble the context from the workspace's catalogs (pure, deterministic:
    tables sorted by name; not-yet-catalogued tables are skipped)."""
    return WorkspaceContext(
        tables=tuple(
            TableContext(
                name=name,
                description=entry.table_description,
                columns=entry.columns,
            )
            for name, entry in sorted(catalogs.items())
            if entry is not None
        ),
        relationships=relationships,
    )
