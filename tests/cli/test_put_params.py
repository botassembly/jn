def test_put_indent_nan_reports_writer_error(invoke, tmp_path, sample_ndjson):
    # Use stdout with format override so plugin argparse handles --indent
    res = invoke(["put", "--", "-~json?indent=nan"], input_data=sample_ndjson)
    # Expect a writer error from plugin, not an address syntax error
    assert res.exit_code == 1
    assert "Writer error" in res.output
    assert "indent" in res.output or "invalid" in res.output.lower()
