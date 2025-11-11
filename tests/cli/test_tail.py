import json


def test_tail_from_stdin(invoke, sample_ndjson):
    res = invoke(["tail", "1"], input_data=sample_ndjson)
    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "Bob"


def test_tail_from_file(invoke, people_csv):
    res = invoke(["tail", str(people_csv), "-n", "2"])  # reads via plugin
    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]
    assert len(lines) == 2

