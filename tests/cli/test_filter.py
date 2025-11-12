import json


def test_filter_field_select(invoke, sample_ndjson):
    res = invoke(["filter", ".name"], input_data=sample_ndjson)
    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 2
    # jq returns raw JSON values (strings, numbers, etc.), not just objects
    values = [json.loads(l) for l in lines]
    assert values == ["Alice", "Bob"]


def test_filter_condition(invoke, sample_ndjson):
    res = invoke(["filter", "select(.age > 25)"], input_data=sample_ndjson)
    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["name"] == "Alice"
