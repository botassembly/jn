def test_plugin_call_yaml_read_multi_doc(invoke):
    yaml = "name: Alice\n---\nname: Bob\n"
    res = invoke(
        ["plugin", "call", "yaml_", "--mode", "read"], input_data=yaml
    )
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 2


def test_plugin_call_yaml_write_multi_doc(invoke):
    ndjson = '{"name":"Alice"}\n{"name":"Bob"}\n'
    res = invoke(
        ["plugin", "call", "yaml_", "--mode", "write"], input_data=ndjson
    )
    assert res.exit_code == 0
    out = res.output
    assert "---" in out
    assert "Alice" in out and "Bob" in out
