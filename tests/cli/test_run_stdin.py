import json


def test_run_stdin_to_json_array(invoke, tmp_path, sample_ndjson):
    """NDJSON from stdin should be consumable by run without an input plugin."""
    out = tmp_path / "out.json"
    res = invoke(["run", "-", str(out)], input_data=sample_ndjson)
    assert res.exit_code == 0, res.output

    data = json.loads(out.read_text())
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "Alice"


def test_cat_stdin_passthrough(invoke, sample_ndjson):
    """cat '-' with NDJSON should pass through unchanged when no format override."""
    res = invoke(["cat", "-"], input_data=sample_ndjson)
    assert res.exit_code == 0
    # Normalize trailing newlines for comparison
    assert res.output.strip().split("\n") == sample_ndjson.strip().split("\n")
