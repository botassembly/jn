import json


def test_put_writes_json_array(invoke, sample_ndjson, tmp_path):
    out_file = tmp_path / "out.json"
    res = invoke(["put", str(out_file)], input_data=sample_ndjson)
    assert res.exit_code == 0

    data = json.loads(out_file.read_text())
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "Alice"


def test_put_unsupported_format(invoke, sample_ndjson, tmp_path):
    """Test put with unsupported output format (no matching plugin)."""
    out_file = tmp_path / "out.unknownext"
    result = invoke(["put", str(out_file)], input_data=sample_ndjson)
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_put_directory_not_found(invoke, sample_ndjson):
    """Test put with non-existent output directory."""
    result = invoke(
        ["put", "/nonexistent/dir/out.json"], input_data=sample_ndjson
    )
    assert result.exit_code == 1
    assert "Error:" in result.output
