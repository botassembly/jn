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
        [
            "plugin",
            "call",
            "jq_",
            "--query",
            "@builtin/group_count",
            "--by",
            "status",
        ],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed with output: {res.output}"

    lines = [l for l in res.output.strip().split("\n") if l]
    records = [json.loads(line) for line in lines]

    # Should have 2 groups
    assert len(records) == 2

    # Find active and inactive groups
    active = next((r for r in records if r.get("status") == "active"), None)
    inactive = next((r for r in records if r.get("status") == "inactive"), None)

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
        [
            "plugin",
            "call",
            "jq_",
            "--query",
            "@builtin/group_sum",
            "--by",
            "customer",
            "--sum",
            "total",
        ],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed with output: {res.output}"

    lines = [l for l in res.output.strip().split("\n") if l]
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
        ["plugin", "call", "jq_", "--query", "@builtin/stats", "--field", "revenue"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed with output: {res.output}"

    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 1

    stats = json.loads(lines[0])

    assert stats["min"] == 100
    assert stats["max"] == 200
    assert stats["sum"] == 450
    assert stats["avg"] == 150
    assert stats["count"] == 3


def test_jq_builtin_flatten_nested(invoke):
    """Test builtin flatten_nested profile."""
    ndjson = '{"user": {"name": "Alice", "age": 30, "address": {"city": "NYC"}}}\n'
    res = invoke(
        ["plugin", "call", "jq_", "--query", "@builtin/flatten_nested"],
        input_data=ndjson,
    )

    assert res.exit_code == 0, f"Command failed with output: {res.output}"

    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 1

    flattened = json.loads(lines[0])

    assert flattened["user.name"] == "Alice"
    assert flattened["user.age"] == 30
    assert flattened["user.address.city"] == "NYC"
    assert "user" not in flattened or not isinstance(flattened.get("user"), dict)
