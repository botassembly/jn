"""CLI tests for universal filtering feature.

Tests filtering in cat, head, and tail commands with various operators
and AND/OR logic combinations.
"""

import json
from pathlib import Path


def test_cat_filter_simple_equality(invoke, tmp_path):
    """Test cat with simple equality filter."""
    # Create test data
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue\n"
        "Alice,NYC,1200\n"
        "Bob,SF,950\n"
        "Carol,NYC,1500\n"
        "Dave,LA,800\n"
    )

    # Filter by city=NYC
    result = invoke(["cat", f"{data_file}?city=NYC"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert all(r["city"] == "NYC" for r in records)
    assert records[0]["name"] == "Alice"
    assert records[1]["name"] == "Carol"


def test_cat_filter_or_logic(invoke, tmp_path):
    """Test cat with OR logic (same field multiple times)."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue\n"
        "Alice,NYC,1200\n"
        "Bob,SF,950\n"
        "Carol,NYC,1500\n"
        "Dave,LA,800\n"
    )

    # Filter by city=NYC OR city=SF
    result = invoke(["cat", f"{data_file}?city=NYC&city=SF"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 3

    records = [json.loads(line) for line in lines]
    cities = {r["city"] for r in records}
    assert cities == {"NYC", "SF"}


def test_cat_filter_and_logic(invoke, tmp_path):
    """Test cat with AND logic (different fields)."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue\n"
        "Alice,NYC,1200\n"
        "Bob,SF,950\n"
        "Carol,NYC,1500\n"
        "Dave,LA,800\n"
    )

    # Filter by city=NYC AND revenue>=1200 (URL encoded >=)
    result = invoke(["cat", f"{data_file}?city=NYC&revenue%3E%3D=1200"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert all(r["city"] == "NYC" for r in records)
    assert all(int(r["revenue"]) >= 1200 for r in records)


def test_cat_filter_greater_than(invoke, tmp_path):
    """Test cat with greater than operator."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue\n"
        "Alice,NYC,1200\n"
        "Bob,SF,950\n"
        "Carol,NYC,1500\n"
        "Dave,LA,800\n"
    )

    # Filter by revenue>1000 (URL encoded >)
    result = invoke(["cat", f"{data_file}?revenue%3E=1000"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert all(int(r["revenue"]) > 1000 for r in records)


def test_cat_filter_with_config_param(invoke, tmp_path):
    """Test cat with both config param (limit) and filter."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue\n"
        "Alice,NYC,1200\n"
        "Bob,SF,950\n"
        "Carol,NYC,1500\n"
        "Dave,LA,800\n"
        "Eve,SF,1300\n"
    )

    # Config param (limit=10) + filter (city=SF)
    result = invoke(["cat", f"{data_file}?limit=10&city=SF"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2  # Only 2 SF records

    records = [json.loads(line) for line in lines]
    assert all(r["city"] == "SF" for r in records)


def test_head_filter_simple(invoke, tmp_path):
    """Test head with filtering."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue\n"
        "Alice,NYC,1200\n"
        "Bob,SF,950\n"
        "Carol,NYC,1500\n"
        "Dave,LA,800\n"
        "Eve,SF,1300\n"
        "Frank,NYC,1100\n"
    )

    # Get first 2 records where city=NYC
    result = invoke(["head", f"{data_file}?city=NYC", "-n", "2"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert all(r["city"] == "NYC" for r in records)
    assert records[0]["name"] == "Alice"
    assert records[1]["name"] == "Carol"


def test_tail_filter_simple(invoke, tmp_path):
    """Test tail with filtering."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue\n"
        "Alice,NYC,1200\n"
        "Bob,SF,950\n"
        "Carol,NYC,1500\n"
        "Dave,LA,800\n"
        "Eve,SF,1300\n"
        "Frank,NYC,1100\n"
    )

    # Get last 2 records where city=NYC
    result = invoke(["tail", f"{data_file}?city=NYC", "-n", "2"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert all(r["city"] == "NYC" for r in records)
    # Should be Carol and Frank (last 2 NYC records)
    assert records[0]["name"] == "Carol"
    assert records[1]["name"] == "Frank"


def test_filter_complex_and_or(invoke, tmp_path):
    """Test complex filter with both AND and OR logic."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue,status\n"
        "Alice,NYC,1200,active\n"
        "Bob,SF,950,inactive\n"
        "Carol,NYC,1500,active\n"
        "Dave,LA,800,active\n"
        "Eve,SF,1300,active\n"
        "Frank,NYC,600,inactive\n"
    )

    # Filter: (city=NYC OR city=SF) AND status=active
    result = invoke(["cat", f"{data_file}?city=NYC&city=SF&status=active"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 3  # Alice, Carol, Eve

    records = [json.loads(line) for line in lines]
    assert all(r["city"] in ["NYC", "SF"] for r in records)
    assert all(r["status"] == "active" for r in records)


def test_filter_with_json_input(invoke, tmp_path):
    """Test filtering works with JSON input format."""
    data_file = tmp_path / "test.json"
    data = [
        {"name": "Alice", "city": "NYC", "revenue": 1200},
        {"name": "Bob", "city": "SF", "revenue": 950},
        {"name": "Carol", "city": "NYC", "revenue": 1500},
    ]
    data_file.write_text(json.dumps(data))

    # Filter JSON data
    result = invoke(["cat", f"{data_file}?city=NYC"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert all(r["city"] == "NYC" for r in records)


def test_filter_empty_results(invoke, tmp_path):
    """Test filter that matches no records."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue\n" "Alice,NYC,1200\n" "Bob,SF,950\n"
    )

    # Filter for non-existent city
    result = invoke(["cat", f"{data_file}?city=London"])
    assert result.exit_code == 0

    # Should have no output
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 0


def test_filter_less_than_operator(invoke, tmp_path):
    """Test filter with less than operator."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city,revenue\n"
        "Alice,NYC,1200\n"
        "Bob,SF,950\n"
        "Carol,NYC,1500\n"
        "Dave,LA,800\n"
    )

    # Filter by revenue<1000 (URL encoded <)
    result = invoke(["cat", f"{data_file}?revenue%3C=1000"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 2  # Bob (950) and Dave (800)

    records = [json.loads(line) for line in lines]
    assert all(int(r["revenue"]) < 1000 for r in records)
