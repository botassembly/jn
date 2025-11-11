import json


def test_head_from_stdin(invoke, sample_ndjson):
    res = invoke(["head", "1"], input_data=sample_ndjson)
    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "Alice"


def test_head_from_file(invoke, people_csv):
    res = invoke(["head", str(people_csv), "-n", "2"])  # reads via plugin
    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 2

