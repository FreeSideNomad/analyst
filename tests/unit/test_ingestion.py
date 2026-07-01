"""Integration tests for the IngestionService facade (Slice A walking skeleton)."""
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
    result = _service(tmp_path).ingest(_write_csv(tmp_path))
    assert result.dataset_name == "sales"


def test_ingest_reports_matching_columns(tmp_path):
    result = _service(tmp_path).ingest(_write_csv(tmp_path))
    assert [c.name for c in result.profile.columns] == ["id", "name", "amount"]


def test_ingest_reports_row_count(tmp_path):
    result = _service(tmp_path).ingest(_write_csv(tmp_path))
    assert result.profile.row_count == 3


def test_ingested_dataset_is_queryable(tmp_path):
    service = _service(tmp_path)
    service.ingest(_write_csv(tmp_path))
    rows = service.store.fetch_all("sales")
    assert len(rows) == 3


def test_query_returns_faithful_values(tmp_path):
    service = _service(tmp_path)
    service.ingest(_write_csv(tmp_path))
    names = {r[1] for r in service.store.fetch_all("sales")}
    assert "alice" in names and "bob" in names
