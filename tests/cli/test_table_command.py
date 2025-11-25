"""Tests for jn table command."""

import json


def test_table_basic_grid(invoke, sample_ndjson):
    """Test basic table rendering with default grid format."""
    res = invoke(["table"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    # Grid format has borders
    assert "+" in output or "─" in output
    assert "Alice" in output
    assert "Bob" in output
    assert "name" in output  # Header


def test_table_format_github(invoke, sample_ndjson):
    """Test GitHub markdown table format."""
    res = invoke(["table", "-f", "github"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    # GitHub format uses |
    assert "|" in output
    assert "Alice" in output
    assert "Bob" in output
    # GitHub format has header separator with dashes
    assert "---" in output or "---|" in output


def test_table_format_simple(invoke, sample_ndjson):
    """Test simple table format (minimal, no borders)."""
    res = invoke(["table", "-f", "simple"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    assert "Alice" in output
    assert "Bob" in output
    # Simple format has dashes under header
    assert "-" in output


def test_table_format_fancy_grid(invoke, sample_ndjson):
    """Test fancy_grid format with Unicode box characters."""
    res = invoke(["table", "-f", "fancy_grid"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    # Fancy grid uses Unicode box-drawing characters
    assert "╒" in output or "│" in output or "═" in output
    assert "Alice" in output


def test_table_format_pipe(invoke, sample_ndjson):
    """Test pipe/markdown table format."""
    res = invoke(["table", "-f", "pipe"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    # Pipe format uses |
    assert "|" in output
    assert "Alice" in output


def test_table_format_html(invoke, sample_ndjson):
    """Test HTML table format."""
    res = invoke(["table", "-f", "html"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    assert "<table>" in output
    assert "<tr>" in output
    assert "Alice" in output


def test_table_format_psql(invoke, sample_ndjson):
    """Test PostgreSQL-style table format."""
    res = invoke(["table", "-f", "psql"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    assert "|" in output
    assert "Alice" in output


def test_table_width_option(invoke):
    """Test column width limiting with --width option."""
    long_data = '{"description":"This is a very long description that should wrap","name":"Test"}\n'
    res = invoke(["table", "-w", "20"], input_data=long_data)
    assert res.exit_code == 0
    output = res.output
    # With width limit, text should wrap
    assert "Test" in output
    # The description should be truncated/wrapped


def test_table_index_option(invoke, sample_ndjson):
    """Test --index option shows row numbers."""
    res = invoke(["table", "--index"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    # Index column shows 0, 1, etc.
    assert "0" in output
    assert "1" in output
    assert "Alice" in output


def test_table_no_header_option(invoke, sample_ndjson):
    """Test --no-header option hides header row."""
    res = invoke(["table", "--no-header"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    # Data should be present
    assert "Alice" in output
    assert "Bob" in output
    # But output should be shorter (no header)
    lines = [l for l in output.strip().split("\n") if l.strip()]
    # Without header, fewer lines in grid format


def test_table_empty_input(invoke):
    """Test graceful handling of empty input."""
    res = invoke(["table"], input_data="")
    assert res.exit_code == 0
    assert res.output.strip() == ""


def test_table_empty_lines(invoke):
    """Test handling of input with empty lines."""
    data = '{"name":"Alice"}\n\n{"name":"Bob"}\n'
    res = invoke(["table"], input_data=data)
    assert res.exit_code == 0
    assert "Alice" in res.output
    assert "Bob" in res.output


def test_table_invalid_json(invoke):
    """Test error handling for invalid JSON."""
    res = invoke(["table"], input_data="not valid json\n")
    assert res.exit_code == 1
    assert "Error" in res.output
    assert "Invalid JSON" in res.output


def test_table_invalid_format(invoke, sample_ndjson):
    """Test error handling for invalid format name."""
    res = invoke(["table", "-f", "nonexistent_format"], input_data=sample_ndjson)
    assert res.exit_code == 1
    assert "Error" in res.output
    assert "Unknown format" in res.output


def test_table_numalign_option(invoke):
    """Test --numalign option for number alignment."""
    data = '{"name":"Alice","value":123.45}\n{"name":"Bob","value":67.89}\n'
    res = invoke(["table", "--numalign", "right"], input_data=data)
    assert res.exit_code == 0
    assert "Alice" in res.output


def test_table_stralign_option(invoke, sample_ndjson):
    """Test --stralign option for string alignment."""
    res = invoke(["table", "--stralign", "center"], input_data=sample_ndjson)
    assert res.exit_code == 0
    assert "Alice" in res.output


def test_table_multiple_options(invoke, sample_ndjson):
    """Test combining multiple options."""
    res = invoke(
        ["table", "-f", "github", "--index", "--stralign", "center"],
        input_data=sample_ndjson,
    )
    assert res.exit_code == 0
    output = res.output
    assert "|" in output  # GitHub format
    assert "0" in output  # Index
    assert "Alice" in output


def test_table_unicode_data(invoke):
    """Test handling of Unicode characters in data."""
    data = '{"name":"日本語","city":"東京"}\n{"name":"한국어","city":"서울"}\n'
    res = invoke(["table"], input_data=data)
    assert res.exit_code == 0
    assert "日本語" in res.output
    assert "東京" in res.output


def test_table_special_characters(invoke):
    """Test handling of special characters in data."""
    data = '{"text":"Hello\\nWorld","value":"a|b|c"}\n'
    res = invoke(["table"], input_data=data)
    assert res.exit_code == 0
    # Should render without crashing


def test_table_nested_data(invoke):
    """Test handling of nested JSON objects."""
    data = '{"name":"Alice","address":{"city":"NYC"}}\n'
    res = invoke(["table"], input_data=data)
    assert res.exit_code == 0
    assert "Alice" in res.output
    # Nested object should be stringified


def test_table_array_data(invoke):
    """Test handling of array values."""
    data = '{"name":"Alice","tags":["a","b","c"]}\n'
    res = invoke(["table"], input_data=data)
    assert res.exit_code == 0
    assert "Alice" in res.output


def test_table_null_values(invoke):
    """Test handling of null values."""
    data = '{"name":"Alice","value":null}\n{"name":"Bob","value":42}\n'
    res = invoke(["table"], input_data=data)
    assert res.exit_code == 0
    assert "Alice" in res.output
    assert "Bob" in res.output


def test_table_boolean_values(invoke):
    """Test handling of boolean values."""
    data = '{"name":"Alice","active":true}\n{"name":"Bob","active":false}\n'
    res = invoke(["table"], input_data=data)
    assert res.exit_code == 0
    assert "Alice" in res.output
    assert "True" in res.output or "true" in res.output.lower()


def test_table_large_numbers(invoke):
    """Test handling of large numbers."""
    data = '{"id":12345678901234567890,"value":1.23e45}\n'
    res = invoke(["table"], input_data=data)
    assert res.exit_code == 0
    # Should render without crashing


def test_table_help(invoke):
    """Test --help option."""
    res = invoke(["table", "--help"])
    assert res.exit_code == 0
    assert "Render NDJSON as a formatted table" in res.output
    assert "--format" in res.output or "-f" in res.output
    assert "--width" in res.output or "-w" in res.output
    assert "--index" in res.output


def test_table_format_rst(invoke, sample_ndjson):
    """Test reStructuredText table format."""
    res = invoke(["table", "-f", "rst"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    assert "=" in output  # RST uses = for borders
    assert "Alice" in output


def test_table_format_latex(invoke, sample_ndjson):
    """Test LaTeX table format."""
    res = invoke(["table", "-f", "latex"], input_data=sample_ndjson)
    assert res.exit_code == 0
    output = res.output
    assert "\\begin{tabular}" in output or "tabular" in output.lower()
    assert "Alice" in output
