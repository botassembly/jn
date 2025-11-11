import json


def test_put_writes_json_array(invoke, sample_ndjson, tmp_path):
    out_file = tmp_path / "out.json"
    res = invoke(["put", str(out_file)], input_data=sample_ndjson)
    assert res.exit_code == 0

    data = json.loads(out_file.read_text())
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "Alice"

