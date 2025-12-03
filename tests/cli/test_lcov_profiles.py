"""Tests for LCOV plugin for coverage analysis."""

import json
from pathlib import Path

import pytest


def test_lcov_plugin_read_functions_mode(invoke, test_data):
    """Test LCOV plugin reads in default functions mode."""
    lcov_file = test_data / "sample.lcov"
    with open(lcov_file) as f:
        lcov_content = f.read()

    res = invoke(
        ["plugin", "call", "lcov_", "--mode", "read"], input_data=lcov_content
    )
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
        [
            "plugin",
            "call",
            "lcov_",
            "--mode",
            "read",
            "--output-mode",
            "files",
        ],
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
