"""Integration tests for the IngestionService facade (Slice A walking skeleton)."""

import pytest

from analyst.service.ingestion import IngestionService
from analyst.engine.store import DatasetStore


def _service(tmp_path):
    return IngestionService(DatasetStore(base_dir=tmp_path / "store"))


def _write_csv(tmp_path, name="sales.csv"):
    csv = tmp_path / name
    csv.write_text(
        "id,name,amount\n1,alice,10.5\n2,bob,20.0\n3,,30.25\n",
        encoding="utf-8",
    )
    return csv


def test_ingest_names_dataset_from_filename(tmp_path):
    # Feature 006: unified source.entity.ext naming — a single delimited file
    # is named "<file>.<ext>".
    result = _service(tmp_path).ingest(_write_csv(tmp_path))
    assert result.dataset_name == "sales.csv"


def test_ingest_reports_matching_columns(tmp_path):
    result = _service(tmp_path).ingest(_write_csv(tmp_path))
    assert [c.name for c in result.profile.columns] == ["id", "name", "amount"]


def test_ingest_reports_row_count(tmp_path):
    result = _service(tmp_path).ingest(_write_csv(tmp_path))
    assert result.profile.row_count == 3


def test_ingested_dataset_is_queryable(tmp_path):
    service = _service(tmp_path)
    service.ingest(_write_csv(tmp_path))
    rows = service.store.fetch_all("sales.csv")
    assert len(rows) == 3


def test_query_returns_faithful_values(tmp_path):
    service = _service(tmp_path)
    service.ingest(_write_csv(tmp_path))
    names = {r[1] for r in service.store.fetch_all("sales.csv")}
    assert "alice" in names and "bob" in names


def test_ingested_dataset_is_queryable_after_reopening_store(tmp_path):
    service = _service(tmp_path)
    service.ingest(_write_csv(tmp_path))
    expected_rows = service.store.fetch_all("sales.csv")

    reopened = DatasetStore(base_dir=tmp_path / "store")

    assert reopened.fetch_all("sales.csv") == expected_rows


def test_ingest_empty_file_raises(tmp_path):
    from analyst.engine.reader import EmptyFileError

    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(EmptyFileError):
        _service(tmp_path).ingest(empty)


def test_ingest_records_synthesized_headers(tmp_path):
    headerless = tmp_path / "raw.csv"
    headerless.write_text("1,alice,10.5\n2,bob,20.0\n", encoding="utf-8")
    result = _service(tmp_path).ingest(headerless)
    assert result.profile.synthesized_headers is True
    assert [c.name for c in result.profile.columns] == [
        "column_1",
        "column_2",
        "column_3",
    ]


def test_ingest_records_duplicate_columns(tmp_path):
    dup = tmp_path / "dup.csv"
    dup.write_text("total,total\n1,2\n", encoding="utf-8")
    result = _service(tmp_path).ingest(dup)
    assert result.profile.had_duplicate_columns is True
    assert [c.name for c in result.profile.columns] == ["total", "total_2"]


def test_ingest_records_encoding(tmp_path):
    latin = tmp_path / "latin.csv"
    latin.write_bytes("id,city\n1,café\n2,Zürich\n".encode("latin-1"))
    result = _service(tmp_path).ingest(latin)
    assert result.profile.encoding == "cp1252"


def test_header_only_file_becomes_zero_row_dataset(tmp_path):
    header_only = tmp_path / "schema.csv"
    header_only.write_text("id,name,amount\n", encoding="utf-8")
    result = _service(tmp_path).ingest(header_only)
    assert result.profile.row_count == 0
    assert [c.name for c in result.profile.columns] == ["id", "name", "amount"]


def test_infers_rich_scalar_types_end_to_end(tmp_path):
    from analyst.domain.types import ColumnType

    typed = tmp_path / "typed.csv"
    typed.write_text(
        "note,quantity,price,active,order_date,created_at\n"
        "hello,3,10.5,true,2024-01-15,2024-01-15 09:30:00\n"
        "world,5,20.0,false,2024-02-20,2024-02-20 14:00:00\n",
        encoding="utf-8",
    )
    result = _service(tmp_path).ingest(typed)
    t = {c.name: c.inferred_type for c in result.profile.columns}
    assert t["note"] == ColumnType.TEXT
    assert t["quantity"] == ColumnType.INTEGER
    assert t["price"] == ColumnType.DECIMAL
    assert t["active"] == ColumnType.BOOLEAN
    assert t["order_date"] == ColumnType.DATE
    assert t["created_at"] == ColumnType.DATETIME


def test_ingestion_result_exposes_datasets_list(tmp_path):
    result = _service(tmp_path).ingest(_write_csv(tmp_path))
    assert len(result.datasets) == 1
    assert result.datasets[0].name == "sales.csv"
    assert result.datasets[0].profile.row_count == 3
    # backward-compat single-dataset accessors still work
    assert result.dataset_name == "sales.csv"
    assert result.profile.row_count == 3


# --------------------------------------------------------------------------- #
# Feature 006 — unified source.entity.ext dataset naming.
# --------------------------------------------------------------------------- #
def test_dataset_name_single_file():
    from analyst.service.ingestion import _dataset_name

    assert _dataset_name("orders", None, ".csv") == "orders.csv"
    assert _dataset_name("data", None, ".tsv") == "data.tsv"
    assert _dataset_name("orders", None, "json") == "orders.json"


def test_dataset_name_excel_sheet():
    from analyst.service.ingestion import _dataset_name

    assert _dataset_name("company", "employees", "xlsx") == "company.employees.xlsx"
    assert (
        _dataset_name("company", "departments", ".XLSX") == "company.departments.xlsx"
    )


def test_dataset_name_sanitizes_each_segment_but_keeps_dots():
    from analyst.service.ingestion import _dataset_name

    # Spaces/punctuation within a segment collapse to underscores; the dot
    # separators between segments and before the extension are preserved.
    assert _dataset_name("Q4 Sales", "Head Count", "xlsx") == "q4_sales.head_count.xlsx"


def test_json_file_is_named_with_extension(tmp_path):
    import json

    path = tmp_path / "orders.json"
    path.write_text(json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8")
    result = _service(tmp_path).ingest(path)
    assert result.dataset_name == "orders.json"
