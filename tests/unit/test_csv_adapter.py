"""Unit tests for CSV adapter (no files required)."""

import json

import pytest

from jn.adapters.csv import csv_to_ndjson
from jn.models import CsvConfig


def test_csv_to_ndjson_basic():
    """Test basic CSV parsing with headers."""
    csv_bytes = b"name,age\nAlice,30\nBob,25"
    result = csv_to_ndjson(csv_bytes)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}
    assert json.loads(lines[1]) == {"name": "Bob", "age": "25"}


def test_csv_to_ndjson_with_default_config():
    """Test CSV parsing with explicit default config."""
    csv_bytes = b"product,price\nWidget,19.99\nGadget,29.99"
    config = CsvConfig()  # Use defaults
    result = csv_to_ndjson(csv_bytes, config)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"product": "Widget", "price": "19.99"}
    assert json.loads(lines[1]) == {"product": "Gadget", "price": "29.99"}


def test_csv_to_ndjson_tsv():
    """Test TSV (tab-separated) parsing."""
    tsv_bytes = b"name\tage\nAlice\t30\nBob\t25"
    config = CsvConfig(delimiter="\t")
    result = csv_to_ndjson(tsv_bytes, config)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}
    assert json.loads(lines[1]) == {"name": "Bob", "age": "25"}


def test_csv_to_ndjson_custom_delimiter():
    """Test pipe-separated values."""
    psv_bytes = b"name|age\nAlice|30\nBob|25"
    config = CsvConfig(delimiter="|")
    result = csv_to_ndjson(psv_bytes, config)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}


def test_csv_to_ndjson_with_quotes():
    """Test CSV with quoted fields containing delimiters."""
    csv_bytes = b'name,city\n"Smith, John","New York, NY"\n"Doe, Jane","Los Angeles, CA"'
    result = csv_to_ndjson(csv_bytes)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0]) == {
        "name": "Smith, John",
        "city": "New York, NY",
    }
    assert json.loads(lines[1]) == {
        "name": "Doe, Jane",
        "city": "Los Angeles, CA",
    }


def test_csv_to_ndjson_with_unicode():
    """Test CSV with Unicode characters."""
    csv_text = "name,city\nJürgen,München\nFrançois,Paris\n"
    csv_bytes = csv_text.encode("utf-8")
    result = csv_to_ndjson(csv_bytes)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"name": "Jürgen", "city": "München"}
    assert json.loads(lines[1]) == {"name": "François", "city": "Paris"}


def test_csv_to_ndjson_empty_file():
    """Test CSV with only headers (no data rows)."""
    csv_bytes = b"name,age\n"
    result = csv_to_ndjson(csv_bytes)

    # Should return empty string or just newline
    assert result == b"" or result == b"\n"


def test_csv_to_ndjson_single_row():
    """Test CSV with single data row."""
    csv_bytes = b"name,age\nAlice,30"
    result = csv_to_ndjson(csv_bytes)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 1
    assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}


def test_csv_to_ndjson_preserves_newlines_in_output():
    """Test that output ends with newline."""
    csv_bytes = b"x,y\n1,2"
    result = csv_to_ndjson(csv_bytes)

    # Should end with newline for NDJSON format
    assert result.endswith(b"\n")


def test_csv_to_ndjson_encoding_utf16():
    """Test CSV with UTF-16 encoding."""
    csv_text = "name,city\nJürgen,München\n"
    csv_bytes = csv_text.encode("utf-16")
    config = CsvConfig(encoding="utf-16")
    result = csv_to_ndjson(csv_bytes, config)

    # Decode result
    output = result.decode("utf-16")
    lines = output.strip().split("\n")

    assert len(lines) == 1
    assert "Jürgen" in lines[0]
    assert "München" in lines[0]


def test_csv_to_ndjson_invalid_encoding_raises_error():
    """Test that invalid encoding raises ValueError."""
    csv_bytes = b"\xff\xfe"  # Invalid UTF-8
    config = CsvConfig(encoding="utf-8")

    with pytest.raises(ValueError, match="Encoding error"):
        csv_to_ndjson(csv_bytes, config)


def test_csv_to_ndjson_no_header_with_fieldnames():
    """Test CSV without header row using explicit fieldnames."""
    csv_bytes = b"Alice,30\nBob,25"
    config = CsvConfig(has_header=False, fieldnames=["name", "age"])
    result = csv_to_ndjson(csv_bytes, config)
    lines = result.decode().strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}
    assert json.loads(lines[1]) == {"name": "Bob", "age": "25"}
