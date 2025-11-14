import json


def test_plugin_call_csv_read(invoke):
    csv = "name,age\nAlice,30\nBob,25\n"
    res = invoke(["plugin", "call", "csv_", "--mode", "read"], input_data=csv)
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 2
    assert json.loads(lines[0])["name"] == "Alice"


def test_plugin_call_csv_write(invoke):
    ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'
    res = invoke(
        ["plugin", "call", "csv_", "--mode", "write"], input_data=ndjson
    )
    assert res.exit_code == 0
    out = res.output.strip().splitlines()
    assert out[0] == "name,age"
    assert "Alice,30" in out[1]
