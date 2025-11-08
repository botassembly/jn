"""Tests for jn run command (filter execution).

Note: Full stdin/stdout pipeline testing is difficult with CliRunner
because subprocess.run() uses sys.stdin.buffer/sys.stdout.buffer.
These tests focus on filter lookup and error handling.
End-to-end pipeline testing should be done manually or with shell integration tests.
"""

from jn.cli import app
from tests.helpers import add_filter, init_config


def test_run_nonexistent_filter(runner, tmp_path):
    """Test error handling for nonexistent filter."""
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)

    # Note: Can't test with stdin using CliRunner due to sys.stdin.buffer limitations
    # This test verifies the filter lookup error case
    result = runner.invoke(
        app,
        ["run", "nonexistent", "--jn", str(config_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "not found" in result.output


def test_run_filter_exists_lookup(runner, tmp_path):
    """Test that run command can find a registered filter.

    Note: Full execution test with stdin requires shell-level testing.
    This verifies the filter registry lookup works.
    """
    config_path = tmp_path / "jn.json"
    init_config(runner, config_path)
    add_filter(runner, config_path, "test-filter", "select(.x > 5)")

    # Verify the filter was added successfully
    from jn import config as jn_config
    jn_config.set_config_path(config_path)

    filter_obj = jn_config.get_filter("test-filter")
    assert filter_obj is not None
    assert filter_obj.name == "test-filter"
    assert filter_obj.query == "select(.x > 5)"
