"""Tests for LCOV JQ profile system for coverage analysis."""

import json
from pathlib import Path


def test_lcov_uncovered_functions(invoke, test_data):
    """Test @lcov/uncovered-functions profile finds 0% coverage functions."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    # First convert LCOV to NDJSON
    res = invoke(["plugin", "call", "lcov_", "--mode", "read"], input_data=lcov_content)
    assert res.exit_code == 0

    # Then filter with the profile
    res = invoke(
        ["filter", "@lcov/uncovered-functions"],
        input_data=res.output,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # sample.lcov has function_two with 0% coverage
    assert len(records) >= 1
    assert any(r.get("function") == "function_two" for r in records)


def test_lcov_functions_below_threshold(invoke, test_data):
    """Test @lcov/functions-below-threshold profile with parameter."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    # First convert LCOV to NDJSON
    res = invoke(["plugin", "call", "lcov_", "--mode", "read"], input_data=lcov_content)
    assert res.exit_code == 0

    # Then filter with threshold parameter
    res = invoke(
        ["filter", "@lcov/functions-below-threshold?threshold=90"],
        input_data=res.output,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should find functions below 90% coverage
    assert len(records) >= 1
    for r in records:
        assert r.get("coverage", 100) < 90


def test_lcov_files_by_coverage(invoke, test_data):
    """Test @lcov/files-by-coverage profile tags files with coverage ranges."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    # First convert LCOV to NDJSON
    res = invoke(["plugin", "call", "lcov_", "--mode", "read"], input_data=lcov_content)
    assert res.exit_code == 0

    # Then filter with the profile
    res = invoke(
        ["filter", "@lcov/files-by-coverage"],
        input_data=res.output,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have records with coverage range tags
    assert len(records) >= 1
    for r in records:
        assert "range" in r
        assert r["range"] in ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]


def test_lcov_summary_by_module(invoke, test_data):
    """Test @lcov/summary-by-module profile extracts module paths."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    # First convert LCOV to NDJSON
    res = invoke(["plugin", "call", "lcov_", "--mode", "read"], input_data=lcov_content)
    assert res.exit_code == 0

    # Then filter with the profile
    res = invoke(
        ["filter", "@lcov/summary-by-module"],
        input_data=res.output,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have module paths extracted from file paths
    assert len(records) >= 1
    modules = {r.get("module") for r in records}
    assert "src/module" in modules or "src/other" in modules


def test_lcov_largest_gaps(invoke, test_data):
    """Test @lcov/largest-gaps profile finds functions with missing lines."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    # First convert LCOV to NDJSON
    res = invoke(["plugin", "call", "lcov_", "--mode", "read"], input_data=lcov_content)
    assert res.exit_code == 0

    # Then filter with min_missing parameter
    res = invoke(
        ["filter", "@lcov/largest-gaps?min_missing=3"],
        input_data=res.output,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should find functions with 3+ missing lines
    for r in records:
        assert r.get("missing", 0) >= 3


def test_lcov_hotspots(invoke, test_data):
    """Test @lcov/hotspots profile identifies large under-tested functions."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    # First convert LCOV to NDJSON
    res = invoke(["plugin", "call", "lcov_", "--mode", "read"], input_data=lcov_content)
    assert res.exit_code == 0

    # Then filter - use low threshold to get results from sample data
    res = invoke(
        ["filter", "@lcov/hotspots?min_lines=5&max_coverage=90"],
        input_data=res.output,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Check hotspot structure has priority field
    for r in records:
        assert "priority" in r
        assert r["priority"] in ["critical", "high", "medium", "low"]
        assert "complexity_score" in r


def test_lcov_poor_branch_coverage(invoke, test_data):
    """Test @lcov/poor-branch-coverage profile."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    # First convert LCOV to NDJSON
    res = invoke(["plugin", "call", "lcov_", "--mode", "read"], input_data=lcov_content)
    assert res.exit_code == 0

    # Then filter with threshold
    res = invoke(
        ["filter", "@lcov/poor-branch-coverage?threshold=80"],
        input_data=res.output,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # All returned records should have branch coverage below threshold
    for r in records:
        assert r.get("branch_coverage", 100) < 80


def test_lcov_plugin_read_functions_mode(invoke, test_data):
    """Test LCOV plugin reads in default functions mode."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    res = invoke(["plugin", "call", "lcov_", "--mode", "read"], input_data=lcov_content)
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have function records
    assert len(records) == 6  # 3 from file_a, 2 from file_b, 1 from file_c

    # Check record structure
    for r in records:
        assert "file" in r
        assert "function" in r
        assert "coverage" in r
        assert "start_line" in r
        assert "end_line" in r


def test_lcov_plugin_read_files_mode(invoke, test_data):
    """Test LCOV plugin reads in files mode."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    res = invoke(
        ["plugin", "call", "lcov_", "--mode", "read", "--output-mode", "files"],
        input_data=lcov_content,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should have 3 file records
    assert len(records) == 3

    files = [r["filename"] for r in records]
    assert "file_a.py" in files
    assert "file_b.py" in files
    assert "file_c.py" in files
