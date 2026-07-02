"""Unit tests for the CSV reader's inspection plan (Slice B)."""

import pytest

from analyst.engine.reader import CsvReader, EmptyFileError


def _write(tmp_path, content, name="f.csv", encoding="utf-8"):
    path = tmp_path / name
    data = content.encode(encoding) if isinstance(content, str) else content
    path.write_bytes(data)
    return path


def test_empty_file_raises_clear_error(tmp_path):
    path = _write(tmp_path, "")
    with pytest.raises(EmptyFileError):
        CsvReader().plan(path)


def test_whitespace_only_file_raises(tmp_path):
    path = _write(tmp_path, "   \n  \n")
    with pytest.raises(EmptyFileError):
        CsvReader().plan(path)


def test_detects_header_row(tmp_path):
    path = _write(tmp_path, "id,name\n1,alice\n2,bob\n")
    plan = CsvReader().plan(path)
    assert plan.has_header is True
    assert plan.column_names == ("id", "name")
    assert plan.synthesized_headers is False


def test_headerless_file_synthesizes_names(tmp_path):
    path = _write(tmp_path, "1,alice,10.5\n2,bob,20.0\n")
    plan = CsvReader().plan(path)
    assert plan.has_header is False
    assert plan.column_names == ("column_1", "column_2", "column_3")
    assert plan.synthesized_headers is True


def test_disambiguates_duplicate_columns(tmp_path):
    path = _write(tmp_path, "total,total\n1,2\n")
    plan = CsvReader().plan(path)
    assert plan.column_names == ("total", "total_2")
    assert plan.had_duplicate_columns is True


def test_header_only_file_is_valid(tmp_path):
    path = _write(tmp_path, "id,name\n")
    plan = CsvReader().plan(path)
    assert plan.has_header is True
    assert plan.column_names == ("id", "name")


def test_detects_non_utf8_encoding(tmp_path):
    # A representative amount of non-ASCII text so detection is reliable.
    body = "id,city\n" + "".join(
        f"{i},{city}\n"
        for i, city in enumerate(["café", "Zürich", "façade", "naïve", "Málaga"] * 4)
    )
    path = _write(tmp_path, body, encoding="latin-1")
    plan = CsvReader().plan(path)
    assert plan.encoding.lower().replace("_", "-") in {
        "latin-1",
        "iso-8859-1",
        "windows-1252",
        "cp1252",
    }
