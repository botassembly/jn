import json
from pathlib import Path


def test_plugin_call_csv_read(invoke, people_csv):
    # Call the csv plugin directly via plugin subcommand
    with open(people_csv) as f:
        res = invoke(
            ["plugin", "call", "csv", "--mode", "read"], input_data=f.read()
        )

    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 5
    first = json.loads(lines[0])
    assert first["name"] == "Alice"


def test_plugin_call_no_args(invoke):
    """Test plugin call with no arguments (missing plugin name)."""
    result = invoke(["plugin", "call"])
    # Click returns exit code 2 for missing required arguments
    assert result.exit_code == 2
    assert "Missing argument" in result.output or "Error" in result.output


def test_plugin_call_not_found(invoke):
    """Test plugin call with non-existent plugin."""
    result = invoke(["plugin", "call", "nonexistent_plugin", "--mode", "read"])
    assert result.exit_code == 1
    assert "Error: Plugin 'nonexistent_plugin' not found" in result.output
    assert "Available plugins:" in result.output
