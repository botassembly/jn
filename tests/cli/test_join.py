"""Tests for the join command."""

import json


def test_join_basic_left_join(invoke, tmp_path):
    """Test basic left join with matching and non-matching records."""
    # Create customers (left side)
    customers_csv = tmp_path / "customers.csv"
    customers_csv.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n")

    # Create orders (right side) - Charlie has no orders
    orders_csv = tmp_path / "orders.csv"
    orders_csv.write_text(
        "order_id,customer_id,amount\nO1,1,100\nO2,1,200\nO3,2,150\n"
    )

    # First get left data as NDJSON
    left_result = invoke(["cat", str(customers_csv)])
    assert left_result.exit_code == 0, f"Cat failed: {left_result.output}"

    # Join with right side
    result = invoke(
        [
            "join",
            str(orders_csv),
            "--left-key",
            "id",
            "--right-key",
            "customer_id",
            "--target",
            "orders",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 3

    records = [json.loads(line) for line in lines]

    # Alice has 2 orders
    alice = next(r for r in records if r["name"] == "Alice")
    assert len(alice["orders"]) == 2
    assert all(o["customer_id"] == "1" for o in alice["orders"])

    # Bob has 1 order
    bob = next(r for r in records if r["name"] == "Bob")
    assert len(bob["orders"]) == 1

    # Charlie has no orders (left join keeps record with empty array)
    charlie = next(r for r in records if r["name"] == "Charlie")
    assert charlie["orders"] == []


def test_join_inner_join(invoke, tmp_path):
    """Test inner join filters out non-matching records."""
    left_csv = tmp_path / "left.csv"
    left_csv.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n")

    # Only Alice and Bob have matches
    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value\n1,100\n2,200\n")

    left_result = invoke(["cat", str(left_csv)])
    assert left_result.exit_code == 0

    result = invoke(
        [
            "join",
            str(right_csv),
            "--left-key",
            "id",
            "--right-key",
            "id",
            "--target",
            "data",
            "--inner",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Only 2 records (Charlie filtered out)
    assert len(records) == 2

    names = {r["name"] for r in records}
    assert names == {"Alice", "Bob"}
    assert "Charlie" not in names


def test_join_pick_fields(invoke, tmp_path):
    """Test --pick option filters right record fields."""
    left_csv = tmp_path / "left.csv"
    left_csv.write_text("id,name\n1,Alice\n")

    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value,extra,noise\n1,100,A,X\n")

    left_result = invoke(["cat", str(left_csv)])
    assert left_result.exit_code == 0

    result = invoke(
        [
            "join",
            str(right_csv),
            "--left-key",
            "id",
            "--right-key",
            "id",
            "--target",
            "data",
            "--pick",
            "value",
            "--pick",
            "extra",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    record = json.loads(lines[0])

    assert "data" in record
    assert len(record["data"]) == 1

    # Only picked fields should be present
    assert record["data"][0] == {"value": "100", "extra": "A"}
    assert "noise" not in record["data"][0]
    assert "id" not in record["data"][0]


def test_join_one_to_many(invoke, tmp_path):
    """Test one-to-many join condenses into array."""
    # One function
    functions_csv = tmp_path / "functions.csv"
    functions_csv.write_text("function,coverage_pct\ndo_magic,5\n")

    # Multiple callers for the same function
    callers_csv = tmp_path / "callers.csv"
    callers_csv.write_text(
        "caller,callee\nmain,do_magic\napi_handler,do_magic\nhelper,do_magic\n"
    )

    left_result = invoke(["cat", str(functions_csv)])
    assert left_result.exit_code == 0

    result = invoke(
        [
            "join",
            str(callers_csv),
            "--left-key",
            "function",
            "--right-key",
            "callee",
            "--target",
            "callers",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) == 1  # Still one record

    record = json.loads(lines[0])
    assert record["function"] == "do_magic"
    assert record["coverage_pct"] == "5"
    assert len(record["callers"]) == 3  # All 3 callers embedded

    caller_names = {c["caller"] for c in record["callers"]}
    assert caller_names == {"main", "api_handler", "helper"}


def test_join_preserves_left_fields(invoke, tmp_path):
    """Test that join preserves all original left record fields."""
    left_csv = tmp_path / "left.csv"
    left_csv.write_text("id,name,city,age\n1,Alice,NYC,30\n")

    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value\n1,100\n")

    left_result = invoke(["cat", str(left_csv)])
    assert left_result.exit_code == 0

    result = invoke(
        [
            "join",
            str(right_csv),
            "--left-key",
            "id",
            "--right-key",
            "id",
            "--target",
            "data",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    record = json.loads(lines[0])

    # All original fields preserved
    assert record["id"] == "1"
    assert record["name"] == "Alice"
    assert record["city"] == "NYC"
    assert record["age"] == "30"

    # Plus the target field
    assert "data" in record


def test_join_with_json_files(invoke, tmp_path):
    """Test join with JSON files."""
    left_json = tmp_path / "left.json"
    left_json.write_text(
        '[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]'
    )

    right_json = tmp_path / "right.json"
    right_json.write_text('[{"id": 1, "score": 95}, {"id": 1, "score": 87}]')

    left_result = invoke(["cat", str(left_json)])
    assert left_result.exit_code == 0

    result = invoke(
        [
            "join",
            str(right_json),
            "--left-key",
            "id",
            "--right-key",
            "id",
            "--target",
            "scores",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    alice = next(r for r in records if r["name"] == "Alice")
    assert len(alice["scores"]) == 2

    bob = next(r for r in records if r["name"] == "Bob")
    assert bob["scores"] == []


def test_join_missing_required_options(invoke, tmp_path):
    """Test that join requires all mandatory options."""
    left_csv = tmp_path / "left.csv"
    left_csv.write_text("id,name\n1,Alice\n")

    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value\n1,100\n")

    left_result = invoke(["cat", str(left_csv)])
    assert left_result.exit_code == 0

    # Missing --left-key
    result = invoke(
        [
            "join",
            str(right_csv),
            "--right-key",
            "id",
            "--target",
            "data",
        ],
        input_data=left_result.output,
    )
    assert result.exit_code != 0
    assert (
        "left-key" in result.output.lower()
        or "required" in result.output.lower()
    )

    # Missing --right-key
    result = invoke(
        [
            "join",
            str(right_csv),
            "--left-key",
            "id",
            "--target",
            "data",
        ],
        input_data=left_result.output,
    )
    assert result.exit_code != 0

    # Missing --target
    result = invoke(
        [
            "join",
            str(right_csv),
            "--left-key",
            "id",
            "--right-key",
            "id",
        ],
        input_data=left_result.output,
    )
    assert result.exit_code != 0


def test_join_empty_left_stream(invoke, tmp_path):
    """Test join with empty left stream produces no output."""
    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value\n1,100\n")

    # Empty input
    result = invoke(
        [
            "join",
            str(right_csv),
            "--left-key",
            "id",
            "--right-key",
            "id",
            "--target",
            "data",
        ],
        input_data="",
    )

    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_join_empty_right_source(invoke, tmp_path):
    """Test join with empty right source produces records with empty arrays."""
    left_csv = tmp_path / "left.csv"
    left_csv.write_text("id,name\n1,Alice\n2,Bob\n")

    # Empty right source (header only)
    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value\n")

    left_result = invoke(["cat", str(left_csv)])
    assert left_result.exit_code == 0

    result = invoke(
        [
            "join",
            str(right_csv),
            "--left-key",
            "id",
            "--right-key",
            "id",
            "--target",
            "data",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # All records have empty arrays
    assert len(records) == 2
    assert all(r["data"] == [] for r in records)


def test_join_numeric_key_matching(invoke, tmp_path):
    """Test that numeric keys are matched as strings."""
    # JSON with numeric id
    left_json = tmp_path / "left.json"
    left_json.write_text('[{"id": 1, "name": "Alice"}]')

    # CSV with string id (CSV values are strings)
    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value\n1,100\n")

    left_result = invoke(["cat", str(left_json)])
    assert left_result.exit_code == 0

    result = invoke(
        [
            "join",
            str(right_csv),
            "--left-key",
            "id",
            "--right-key",
            "id",
            "--target",
            "data",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    record = json.loads(lines[0])

    # Should match despite int vs string
    assert len(record["data"]) == 1


def test_join_pick_nonexistent_field(invoke, tmp_path):
    """Test --pick with nonexistent field produces partial record."""
    left_csv = tmp_path / "left.csv"
    left_csv.write_text("id,name\n1,Alice\n")

    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,value\n1,100\n")

    left_result = invoke(["cat", str(left_csv)])
    assert left_result.exit_code == 0

    result = invoke(
        [
            "join",
            str(right_csv),
            "--left-key",
            "id",
            "--right-key",
            "id",
            "--target",
            "data",
            "--pick",
            "value",
            "--pick",
            "nonexistent",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    record = json.loads(lines[0])

    # Only existing picked field should be present
    assert record["data"][0] == {"value": "100"}
    assert "nonexistent" not in record["data"][0]


def test_join_dead_code_hunter_scenario(invoke, tmp_path):
    """Test the dead code hunter use case from the design doc."""
    # Coverage data (left side)
    coverage_csv = tmp_path / "coverage.csv"
    coverage_csv.write_text(
        "function,coverage_pct,file\n"
        "do_magic,5,utils.c\n"
        "unused_helper,0,legacy.c\n"
        "well_tested,95,core.c\n"
    )

    # Call graph (right side) - unused_helper has no callers
    callers_csv = tmp_path / "callers.csv"
    callers_csv.write_text(
        "caller,callee\n"
        "main,do_magic\n"
        "api_handler,do_magic\n"
        "test_core,well_tested\n"
    )

    left_result = invoke(["cat", str(coverage_csv)])
    assert left_result.exit_code == 0

    result = invoke(
        [
            "join",
            str(callers_csv),
            "--left-key",
            "function",
            "--right-key",
            "callee",
            "--target",
            "callers",
        ],
        input_data=left_result.output,
    )

    assert result.exit_code == 0, f"Join failed: {result.output}"

    lines = [line for line in result.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # do_magic: 2 callers
    do_magic = next(r for r in records if r["function"] == "do_magic")
    assert len(do_magic["callers"]) == 2

    # unused_helper: 0 callers (dead code!)
    unused = next(r for r in records if r["function"] == "unused_helper")
    assert unused["callers"] == []

    # well_tested: 1 caller
    well_tested = next(r for r in records if r["function"] == "well_tested")
    assert len(well_tested["callers"]) == 1

    # Now we could filter for dead code:
    # select(.coverage_pct < 10 and (.callers | length) == 0)
    dead_code = [
        r
        for r in records
        if int(r["coverage_pct"]) < 10 and len(r["callers"]) == 0
    ]
    assert len(dead_code) == 1
    assert dead_code[0]["function"] == "unused_helper"
