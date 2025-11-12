import json


def test_plugin_call_json_read_array(invoke):
    payload = '[{"name":"Alice"},{"name":"Bob"}]'
    res = invoke(
        ["plugin", "call", "json_", "--mode", "read"], input_data=payload
    )
    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 2
    assert json.loads(lines[0])["name"] == "Alice"


def test_plugin_call_json_write_array(invoke):
    ndjson = '{"name":"Alice"}\n{"name":"Bob"}\n'
    res = invoke(
        ["plugin", "call", "json_", "--mode", "write", "--format", "array"],
        input_data=ndjson,
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert isinstance(data, list)
    assert data[0]["name"] == "Alice"
