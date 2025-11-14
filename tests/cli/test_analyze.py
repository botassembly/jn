"""CLI tests for analyze command.

Tests streaming analysis with schema inference, statistics, facets, and sampling.
"""

import json


def test_analyze_basic_csv(invoke, tmp_path):
    """Test analyze with basic CSV data."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,age,city\n" "Alice,30,NYC\n" "Bob,25,SF\n" "Carol,35,NYC\n"
    )

    invoke(["cat", str(data_file), "|", "jn", "analyze", "--format", "json"])
    # Note: pipe doesn't work in Click runner, so test directly
    cat_result = invoke(["cat", str(data_file)])
    assert cat_result.exit_code == 0

    analyze_result = invoke(
        ["analyze", "--format", "json"], input_data=cat_result.output
    )
    assert analyze_result.exit_code == 0

    data = json.loads(analyze_result.output)
    assert data["rows"] == 3
    assert data["columns"] == 3
    assert "name" in data["schema"]
    assert "age" in data["schema"]
    assert "city" in data["schema"]


def test_analyze_schema_detection(invoke, tmp_path):
    """Test schema type detection."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,age,active\n" "Alice,30,true\n" "Bob,25,false\n"
    )

    cat_result = invoke(["cat", str(data_file)])
    analyze_result = invoke(
        ["analyze", "--format", "json"], input_data=cat_result.output
    )
    assert analyze_result.exit_code == 0

    data = json.loads(analyze_result.output)
    schema = data["schema"]

    assert "name" in schema
    assert "age" in schema
    assert schema["name"]["type"] == "string"
    assert schema["age"]["type"] == "string"  # CSV reads as strings


def test_analyze_facets(invoke, tmp_path):
    """Test facet generation (categorical value distributions)."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,city\n"
        "Alice,NYC\n"
        "Bob,SF\n"
        "Carol,NYC\n"
        "Dave,LA\n"
        "Eve,SF\n"
    )

    cat_result = invoke(["cat", str(data_file)])
    analyze_result = invoke(
        ["analyze", "--format", "json"], input_data=cat_result.output
    )
    assert analyze_result.exit_code == 0

    data = json.loads(analyze_result.output)
    facets = data["facets"]

    assert "city" in facets
    assert facets["city"]["NYC"] == 2
    assert facets["city"]["SF"] == 2
    assert facets["city"]["LA"] == 1


def test_analyze_statistics(invoke, tmp_path):
    """Test numeric statistics computation."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,revenue\n" "Alice,1200\n" "Bob,950\n" "Carol,1500\n"
    )

    cat_result = invoke(["cat", str(data_file)])
    analyze_result = invoke(
        ["analyze", "--format", "json"], input_data=cat_result.output
    )
    assert analyze_result.exit_code == 0

    data = json.loads(analyze_result.output)
    stats = data["stats"]

    assert "revenue" in stats
    assert stats["revenue"]["count"] == 3
    assert stats["revenue"]["min"] == 950.0
    assert stats["revenue"]["max"] == 1500.0
    assert stats["revenue"]["mean"] > 1000  # Roughly 1216.67


def test_analyze_samples(invoke, tmp_path):
    """Test sample collection (first/last/random)."""
    data_file = tmp_path / "test.csv"
    data_file.write_text(
        "name,value\n" "A,1\n" "B,2\n" "C,3\n" "D,4\n" "E,5\n"
    )

    cat_result = invoke(["cat", str(data_file)])
    analyze_result = invoke(
        ["analyze", "--format", "json", "--sample-size", "3"],
        input_data=cat_result.output,
    )
    assert analyze_result.exit_code == 0

    data = json.loads(analyze_result.output)
    samples = data["samples"]

    assert "first" in samples
    assert "last" in samples
    assert "random" in samples

    # Check first samples
    assert len(samples["first"]) <= 3
    if samples["first"]:
        assert samples["first"][0]["name"] == "A"

    # Check last samples
    assert len(samples["last"]) <= 3


def test_analyze_text_format(invoke, tmp_path):
    """Test analyze with text output format."""
    data_file = tmp_path / "test.csv"
    data_file.write_text("name,city\n" "Alice,NYC\n" "Bob,SF\n")

    cat_result = invoke(["cat", str(data_file)])
    analyze_result = invoke(
        ["analyze", "--format", "text"], input_data=cat_result.output
    )
    assert analyze_result.exit_code == 0

    output = analyze_result.output
    assert "Rows:" in output
    assert "Columns:" in output
    assert "Schema:" in output


def test_analyze_empty_input(invoke):
    """Test analyze with empty input."""
    result = invoke(["analyze", "--format", "json"], input_data="")
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data["rows"] == 0
    assert data["columns"] == 0


def test_analyze_single_record(invoke):
    """Test analyze with single record."""
    ndjson = '{"name": "Alice", "age": 30}\n'

    result = invoke(["analyze", "--format", "json"], input_data=ndjson)
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data["rows"] == 1
    assert data["columns"] == 2
    assert "name" in data["schema"]
    assert "age" in data["schema"]


def test_analyze_custom_sample_size(invoke, tmp_path):
    """Test analyze with custom sample size."""
    data_file = tmp_path / "test.csv"
    lines = ["name,value\n"]
    for i in range(20):
        lines.append(f"Name{i},{i}\n")
    data_file.write_text("".join(lines))

    cat_result = invoke(["cat", str(data_file)])
    analyze_result = invoke(
        ["analyze", "--format", "json", "--sample-size", "5"],
        input_data=cat_result.output,
    )
    assert analyze_result.exit_code == 0

    data = json.loads(analyze_result.output)
    assert len(data["samples"]["first"]) <= 5
    assert len(data["samples"]["last"]) <= 5
    assert len(data["samples"]["random"]) <= 5


def test_analyze_with_nulls(invoke):
    """Test analyze with null/missing values."""
    ndjson = (
        '{"name": "Alice", "age": 30}\n'
        '{"name": "Bob", "age": null}\n'
        '{"name": "Carol"}\n'
    )

    result = invoke(["analyze", "--format", "json"], input_data=ndjson)
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data["rows"] == 3

    # Age field should show nullable
    if "age" in data["schema"]:
        assert data["schema"]["age"]["nullable"] is True


def test_analyze_unique_counts(invoke, tmp_path):
    """Test unique value counting in schema."""
    data_file = tmp_path / "test.csv"
    data_file.write_text("name,city\n" "Alice,NYC\n" "Bob,NYC\n" "Carol,SF\n")

    cat_result = invoke(["cat", str(data_file)])
    analyze_result = invoke(
        ["analyze", "--format", "json"], input_data=cat_result.output
    )
    assert analyze_result.exit_code == 0

    data = json.loads(analyze_result.output)
    schema = data["schema"]

    # Name should have 3 unique values, city should have 2
    assert schema["name"]["unique"] == 3
    assert schema["city"]["unique"] == 2
