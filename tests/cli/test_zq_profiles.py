"""Tests for ZQ profile system with named filters.

ZQ is JN's built-in filter engine (a jq-compatible subset implemented in Zig).
Profiles are reusable filter expressions stored in profiles/jq/ directories.
"""

import json

import pytest


def test_zq_direct_query(invoke):
    """Test ZQ with direct query expression (not a profile)."""
    ndjson = """{"name":"Alice","age":30}
{"name":"Bob","age":25}
{"name":"Charlie","age":35}
"""
    res = invoke(
        ["filter", "select(.age > 26)"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed with output: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have Alice and Charlie (ages 30 and 35)
    assert len(records) == 2
    assert any(r["name"] == "Alice" for r in records)
    assert any(r["name"] == "Charlie" for r in records)
    assert not any(r["name"] == "Bob" for r in records)


def test_zq_profile_string_substitution_simple(invoke, tmp_path, monkeypatch):
    """Test ZQ profile with string substitution for string values."""
    # Create a ZQ profile that uses $variables
    profile_dir = tmp_path / "profiles" / "jq" / "test"
    profile_dir.mkdir(parents=True)

    # Create filter that uses $value variable (string substitution wraps in quotes)
    (profile_dir / "filter_by_city.jq").write_text(
        """# Filter by city value
# Parameters: value
select(.city == $value)
"""
    )

    monkeypatch.setenv("JN_HOME", str(tmp_path))

    ndjson = """{"name":"Alice","city":"NYC"}
{"name":"Bob","city":"LA"}
{"name":"Charlie","city":"NYC"}
"""

    # String substitution replaces $value with "NYC"
    res = invoke(
        ["filter", "@test/filter_by_city?value=NYC"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have Alice and Charlie (city=NYC)
    assert len(records) == 2
    names = [r["name"] for r in records]
    assert "Alice" in names
    assert "Charlie" in names
    assert "Bob" not in names


def test_zq_profile_string_substitution_numeric(invoke, tmp_path, monkeypatch):
    """Test ZQ profile with string substitution for numeric comparison."""
    profile_dir = tmp_path / "profiles" / "jq" / "test"
    profile_dir.mkdir(parents=True)

    # Create filter that compares against numeric threshold
    # Note: numeric values are not quoted, so no tonumber needed on threshold
    (profile_dir / "above_threshold.jq").write_text(
        """# Filter items above threshold
# Parameters: threshold (numeric)
select(.revenue > $threshold)
"""
    )

    monkeypatch.setenv("JN_HOME", str(tmp_path))

    ndjson = """{"item":"A","revenue":100}
{"item":"B","revenue":500}
{"item":"C","revenue":250}
"""

    # String substitution replaces $threshold with 200 (unquoted - it's numeric)
    res = invoke(
        ["filter", "@test/above_threshold?threshold=200"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have B and C (revenue > 200)
    assert len(records) == 2
    items = [r["item"] for r in records]
    assert "B" in items
    assert "C" in items
    assert "A" not in items


def test_zq_direct_expression_active_status(invoke):
    """Test that direct ZQ expressions work without profile."""
    ndjson = """{"status":"active"}
{"status":"inactive"}
{"status":"active"}
"""
    # Direct ZQ expression
    res = invoke(
        ["filter", 'select(.status == "active")'],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have 2 active records
    assert len(records) == 2
    assert all(r["status"] == "active" for r in records)
