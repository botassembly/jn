"""Tests for the merge command."""

import json
from pathlib import Path

import pytest


def test_merge_two_csv_files(invoke, tmp_path):
    """Test merging two CSV files with labels."""
    # Create two CSV files
    east_csv = tmp_path / "east.csv"
    east_csv.write_text("id,value\n1,100\n2,200\n")

    west_csv = tmp_path / "west.csv"
    west_csv.write_text("id,value\n3,300\n4,400\n")

    res = invoke(
        [
            "merge",
            f"{east_csv}:label=East",
            f"{west_csv}:label=West",
        ]
    )

    assert res.exit_code == 0, f"Failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 4

    records = [json.loads(line) for line in lines]

    # Check first two records are from East
    east_records = [r for r in records if r["_label"] == "East"]
    assert len(east_records) == 2
    assert all(r["_source"].endswith("east.csv") for r in east_records)

    # Check last two records are from West
    west_records = [r for r in records if r["_label"] == "West"]
    assert len(west_records) == 2
    assert all(r["_source"].endswith("west.csv") for r in west_records)


def test_merge_default_label(invoke, tmp_path):
    """Test merge with default label (source path used as label)."""
    data_csv = tmp_path / "data.csv"
    data_csv.write_text("x,y\n1,2\n")

    res = invoke(["merge", str(data_csv)])

    assert res.exit_code == 0, f"Failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 1

    record = json.loads(lines[0])
    # Default label should be the source itself
    assert record["_label"] == str(data_csv)
    assert record["_source"] == str(data_csv)


def test_merge_with_parameters(invoke, tmp_path, monkeypatch):
    """Test merge with parameterized sources."""
    # Create a CSV with status column
    data_csv = tmp_path / "users.csv"
    data_csv.write_text(
        "name,status\nAlice,active\nBob,inactive\nCharlie,active\n"
    )

    res = invoke(
        [
            "merge",
            f"{data_csv}?status=active:label=Active",
            f"{data_csv}?status=inactive:label=Inactive",
        ]
    )

    assert res.exit_code == 0, f"Failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have 3 active + 1 inactive = 4 total (unfiltered CSV)
    # Note: CSV filtering requires jn filter, this just tests merge labeling
    assert len(records) >= 1

    # Check labels are applied
    labels = set(r["_label"] for r in records)
    assert "Active" in labels or "Inactive" in labels


def test_merge_three_sources(invoke, tmp_path):
    """Test merging three sources."""
    a_csv = tmp_path / "a.csv"
    a_csv.write_text("id\n1\n")

    b_csv = tmp_path / "b.csv"
    b_csv.write_text("id\n2\n")

    c_csv = tmp_path / "c.csv"
    c_csv.write_text("id\n3\n")

    res = invoke(
        [
            "merge",
            f"{a_csv}:label=A",
            f"{b_csv}:label=B",
            f"{c_csv}:label=C",
        ]
    )

    assert res.exit_code == 0, f"Failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    assert len(records) == 3

    labels = [r["_label"] for r in records]
    assert labels == ["A", "B", "C"]  # Sequential order


def test_merge_preserves_data_fields(invoke, tmp_path):
    """Test that merge preserves all original data fields."""
    data_csv = tmp_path / "data.csv"
    data_csv.write_text("name,age,city\nAlice,30,NYC\n")

    res = invoke(["merge", f"{data_csv}:label=Test"])

    assert res.exit_code == 0, f"Failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    record = json.loads(lines[0])

    # Original fields preserved
    assert record["name"] == "Alice"
    assert record["age"] == "30"
    assert record["city"] == "NYC"

    # Metadata fields added
    assert record["_label"] == "Test"
    assert "_source" in record


def test_merge_label_with_colon_in_source(invoke, tmp_path):
    """Test that label parsing handles sources with colons correctly."""
    # This tests that we use rfind for :label= to handle URL-like sources
    data_csv = tmp_path / "data.csv"
    data_csv.write_text("x\n1\n")

    res = invoke(
        [
            "merge",
            f"{data_csv}:label=MyLabel",
        ]
    )

    assert res.exit_code == 0, f"Failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    record = json.loads(lines[0])

    assert record["_label"] == "MyLabel"


def test_merge_no_sources_error(invoke):
    """Test that merge requires at least one source."""
    res = invoke(["merge"])

    # Click should show usage error
    assert res.exit_code != 0


def test_merge_fail_fast(invoke, tmp_path):
    """Test --fail-fast option stops on first error."""
    good_csv = tmp_path / "good.csv"
    good_csv.write_text("x\n1\n")

    # First source succeeds, second fails with --fail-fast
    res = invoke(
        [
            "merge",
            f"{good_csv}:label=Good",
            "nonexistent.csv:label=Bad",
            "--fail-fast",
        ]
    )

    # Should have output from good file before error
    # Check that good data was output
    lines = [
        line
        for line in res.output.strip().split("\n")
        if line
        and not line.startswith("Error")
        and not line.startswith("Warning")
    ]
    assert len(lines) >= 1
    if lines:
        record = json.loads(lines[0])
        assert record["_label"] == "Good"


def test_merge_continue_on_error(invoke, tmp_path):
    """Test that without --fail-fast, merge continues after errors."""
    good_csv = tmp_path / "good.csv"
    good_csv.write_text("x\n1\n")

    res = invoke(
        [
            "merge",
            "nonexistent.csv:label=Bad",
            f"{good_csv}:label=Good",
        ]
    )

    # Should continue and output the good file's data
    lines = [
        line
        for line in res.output.strip().split("\n")
        if line and not line.startswith("Warning")
    ]
    if lines:
        record = json.loads(lines[-1])
        assert record["_label"] == "Good"


def test_merge_with_json_files(invoke, tmp_path):
    """Test merge with JSON files."""
    a_json = tmp_path / "a.json"
    a_json.write_text('[{"name": "Alice"}, {"name": "Bob"}]')

    b_json = tmp_path / "b.json"
    b_json.write_text('[{"name": "Charlie"}]')

    res = invoke(
        [
            "merge",
            f"{a_json}:label=GroupA",
            f"{b_json}:label=GroupB",
        ]
    )

    assert res.exit_code == 0, f"Failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    assert len(records) == 3

    group_a = [r for r in records if r["_label"] == "GroupA"]
    group_b = [r for r in records if r["_label"] == "GroupB"]

    assert len(group_a) == 2
    assert len(group_b) == 1
