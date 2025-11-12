def test_head_negative_lines_errors(invoke, sample_ndjson):
    res = invoke(["head", "-n", "-5"], input_data=sample_ndjson)
    assert res.exit_code == 1
    assert "must be >= 0" in res.output


def test_tail_negative_lines_errors(invoke, sample_ndjson):
    res = invoke(["tail", "-n", "-5"], input_data=sample_ndjson)
    assert res.exit_code == 1
    assert "must be >= 0" in res.output
