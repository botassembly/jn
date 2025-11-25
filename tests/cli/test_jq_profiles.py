"""Tests for JQ profile system with named filters."""

import json

import pytest


def test_jq_builtin_group_count(invoke):
    """Test builtin group_count profile."""
    ndjson = """{"status":"active"}
{"status":"inactive"}
{"status":"active"}
{"status":"active"}
"""
    res = invoke(
        ["filter", "@builtin/group_count?by=status"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed with output: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have 2 groups
    assert len(records) == 2

    # Find active and inactive groups
    active = next((r for r in records if r.get("status") == "active"), None)
    inactive = next(
        (r for r in records if r.get("status") == "inactive"), None
    )

    assert active is not None
    assert active["count"] == 3

    assert inactive is not None
    assert inactive["count"] == 1


def test_jq_builtin_group_sum(invoke):
    """Test builtin group_sum profile."""
    ndjson = """{"customer":"Alice","total":100}
{"customer":"Bob","total":50}
{"customer":"Alice","total":75}
"""
    res = invoke(
        ["filter", "@builtin/group_sum?by=customer&sum=total"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed with output: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    assert len(records) == 2

    alice = next((r for r in records if r.get("customer") == "Alice"), None)
    bob = next((r for r in records if r.get("customer") == "Bob"), None)

    assert alice is not None
    assert alice["total"] == 175

    assert bob is not None
    assert bob["total"] == 50


def test_jq_builtin_stats(invoke):
    """Test builtin stats profile."""
    ndjson = """{"revenue":100}
{"revenue":150}
{"revenue":200}
"""
    res = invoke(
        ["filter", "@builtin/stats?field=revenue"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed with output: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 1

    stats = json.loads(lines[0])

    assert stats["min"] == 100
    assert stats["max"] == 200
    assert stats["sum"] == 450
    assert stats["avg"] == 150
    assert stats["count"] == 3


def test_jq_builtin_flatten_nested(invoke):
    """Test builtin flatten_nested profile."""
    ndjson = (
        '{"user": {"name": "Alice", "age": 30, "address": {"city": "NYC"}}}\n'
    )
    res = invoke(
        ["filter", "@builtin/flatten_nested"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed with output: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 1

    flattened = json.loads(lines[0])

    assert flattened["user.name"] == "Alice"
    assert flattened["user.age"] == 30
    assert flattened["user.address.city"] == "NYC"
    assert "user" not in flattened or not isinstance(
        flattened.get("user"), dict
    )


def test_jq_direct_query(invoke):
    """Test jq with direct query expression (not a profile)."""
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


def test_jq_native_args_simple(invoke, tmp_path, monkeypatch):
    """Test JQ profile with native --arg binding."""
    # Create a JQ profile that uses $variables
    profile_dir = tmp_path / "profiles" / "jq" / "test"
    profile_dir.mkdir(parents=True)

    # Create filter that uses $field variable
    (profile_dir / "filter_by.jq").write_text(
        """# Filter by field value
# Parameters: field, value
select(.[$field] == $value)
"""
    )

    monkeypatch.setenv("JN_HOME", str(tmp_path))

    ndjson = """{"name":"Alice","city":"NYC"}
{"name":"Bob","city":"LA"}
{"name":"Charlie","city":"NYC"}
"""

    # Use --native-args to use jq's native --arg binding
    res = invoke(
        ["filter", "@test/filter_by?field=city&value=NYC", "--native-args"],
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


def test_jq_native_args_numeric_comparison(invoke, tmp_path, monkeypatch):
    """Test JQ profile with native args for numeric comparison."""
    profile_dir = tmp_path / "profiles" / "jq" / "test"
    profile_dir.mkdir(parents=True)

    # Create filter that uses tonumber for comparison
    (profile_dir / "above_threshold.jq").write_text(
        """# Filter items above threshold
# Parameters: field, threshold
select(.[$field] > ($threshold | tonumber))
"""
    )

    monkeypatch.setenv("JN_HOME", str(tmp_path))

    ndjson = """{"item":"A","revenue":100}
{"item":"B","revenue":500}
{"item":"C","revenue":250}
"""

    res = invoke(
        ["filter", "@test/above_threshold?field=revenue&threshold=200", "--native-args"],
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


def test_jq_string_substitution_backward_compat(invoke):
    """Test that string substitution mode still works (backward compatibility)."""
    # This tests the default mode (no --native-args)
    ndjson = """{"status":"active"}
{"status":"inactive"}
{"status":"active"}
"""
    # Use builtin profile which uses string substitution
    res = invoke(
        ["filter", "@builtin/group_count?by=status"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed: {res.output}"

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should group by status
    assert len(records) == 2
