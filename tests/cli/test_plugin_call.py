import json
from pathlib import Path


def test_plugin_call_csv_read(invoke, people_csv):
    # Call the csv_ plugin directly via plugin subcommand
    with open(people_csv) as f:
        res = invoke(["plugin", "call", "csv_", "--mode", "read"], input_data=f.read())

    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 5
    first = json.loads(lines[0])
    assert first["name"] == "Alice"

