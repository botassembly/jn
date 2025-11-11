def test_plugin_info(invoke):
    res = invoke(["plugin", "info", "csv_"])
    assert res.exit_code == 0
    # Basic fields
    assert "Plugin: csv_" in res.output
    assert "Type:" in res.output
    assert "Methods:" in res.output
    assert "Matches:" in res.output

