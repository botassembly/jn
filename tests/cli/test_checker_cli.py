import textwrap


def _write_plugin(path, body):
    body = textwrap.dedent(body)
    shebang = "#!/usr/bin/env -S uv run --script\n"
    if not body.startswith("#!/"):
        body = shebang + body
    path.write_text(body)


def test_check_core_summary_ok(invoke):
    res = invoke(["check", "core", "--format", "summary"])
    assert res.exit_code in (
        0,
        1,
    )  # allow nonzero if warnings are treated as errors
    assert "files" in res.output.lower() or "passed" in res.output.lower()


def test_checker_framework_import_violation(invoke, tmp_path):
    home = tmp_path / "jn_home"
    plugins_dir = home / "plugins"
    plugins_dir.mkdir(parents=True)
    custom = plugins_dir / "badfw.py"
    _write_plugin(
        custom,
        """
        # /// script
        # requires-python = ">=3.11"
        # dependencies = []
        # [tool.jn]
        # matches = ['.*\\.bad$']
        # ///

        import jn  # forbidden framework import

        def reads(config=None):
            pass
        """,
    )

    res = invoke(["--home", str(home), "check", "badfw"])
    assert res.exit_code == 1
    assert "framework import" in res.output.lower()


def test_checker_subprocess_capture_violation(invoke, tmp_path):
    home = tmp_path / "jn_home"
    plugins_dir = home / "plugins"
    plugins_dir.mkdir(parents=True)
    custom = plugins_dir / "badcap.py"
    _write_plugin(
        custom,
        """
        # /// script
        # requires-python = ">=3.11"
        # dependencies = []
        # [tool.jn]
        # matches = ['.*\\.cap$']
        # ///

        import subprocess

        def reads(config=None):
            # Using capture_output=True should be flagged by checker
            subprocess.run(["echo", "hi"], capture_output=True)
        """,
    )

    res = invoke(["--home", str(home), "check", "badcap"])
    assert res.exit_code == 1
    assert "capture_output" in res.output


def test_checker_inline_whitelist_ignore(invoke, tmp_path):
    home = tmp_path / "jn_home"
    plugins_dir = home / "plugins"
    plugins_dir.mkdir(parents=True)
    custom = plugins_dir / "stdinbuf.py"
    _write_plugin(
        custom,
        """
        # /// script
        # requires-python = ">=3.11"
        # dependencies = []
        # [tool.jn]
        # matches = ['.*\\.stdin$']
        # ///

        import sys

        def reads(config=None):
            data = sys.stdin.buffer.read()  # jn:ignore[stdin_buffer_read]
            if not data:
                return
        """,
    )

    res = invoke(["--home", str(home), "check", "stdinbuf"])
    # Whitelist should allow this pattern and return success
    assert res.exit_code == 0
