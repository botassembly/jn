def test_plugin_call_shows_stderr_on_error(invoke):
    """Calling a plugin that errors should surface stderr to the user."""
    # xlsx_ reads from stdin; with no input it should error
    res = invoke(["plugin", "call", "xlsx_", "--mode", "read"], input_data="")
    assert res.exit_code != 0
    # Click captures both streams; error text should be present in output
    # or stderr depending on environment. Accept either being non-empty.
    has_err_text = bool(res.output.strip())
    if hasattr(res, "stderr"):
        has_err_text = has_err_text or bool(res.stderr.strip())
    assert has_err_text
