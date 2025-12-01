"""Tests for JQ profile system with named filters."""

import json

import pytest

# These builtin profiles use jq features not supported by ZQ:
# - variable binding (as $var)
# - inputs function
# - recursive descent
# They are skipped until ZQ supports these features or profiles are rewritten.


@pytest.mark.skip(
    reason="Uses jq features not supported by ZQ (variable binding, inputs)"
)
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


@pytest.mark.skip(
    reason="Uses jq features not supported by ZQ (variable binding, inputs)"
)
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


@pytest.mark.skip(
    reason="Uses jq features not supported by ZQ (variable binding, inputs)"
)
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


@pytest.mark.skip(
    reason="Uses jq features not supported by ZQ (recursive descent)"
)
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


def test_jq_profile_string_substitution_simple(invoke, tmp_path, monkeypatch):
    """Test JQ profile with string substitution for string values."""
    # Create a JQ profile that uses $variables
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


def test_jq_profile_string_substitution_numeric(invoke, tmp_path, monkeypatch):
    """Test JQ profile with string substitution for numeric comparison."""
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


def test_jq_profile_string_substitution_direct_expression(invoke):
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
