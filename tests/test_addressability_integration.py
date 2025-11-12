"""Integration tests for addressability system via CLI."""

import json

from click.testing import CliRunner

from jn.cli.main import cli


class TestAddressabilityParsing:
    """Test that addresses parse correctly from CLI level."""

    def test_basic_file_address(self):
        """Test basic file addresses work."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create sample CSV
            with open("input.csv", "w") as f:
                f.write("name,age\nAlice,30\nBob,25\n")

            # Read CSV (auto-detect)
            result = runner.invoke(cli, ["cat", "input.csv"])
            assert result.exit_code == 0

            # Verify NDJSON output
            lines = result.output.strip().split("\n")
            assert len(lines) == 2
            record = json.loads(lines[0])
            assert "name" in record
            assert "age" in record

    def test_profile_query_string_parsing(self):
        """Test that query strings in addresses parse correctly."""
        runner = CliRunner()

        # Test that query string syntax is accepted (even if profile doesn't exist)
        result = runner.invoke(
            cli,
            ["cat", "@nonexistent/api?param=value"],
            catch_exceptions=False,
        )

        # Should fail on profile resolution, not address parsing
        assert result.exit_code == 1
        # Error should be about profile not found, not syntax error
        assert (
            "Profile" in result.output or "not found" in result.output.lower()
        )
        assert "Invalid address syntax" not in result.output

    def test_format_override_syntax_accepted(self):
        """Test that format override syntax is accepted."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create test file
            with open("test.txt", "w") as f:
                f.write("name,age\nAlice,30\n")

            # Use format override syntax (even if it doesn't fully work yet)
            result = runner.invoke(cli, ["cat", "test.txt~csv"])

            # Should not fail on syntax, though may fail on execution
            assert "Invalid address syntax" not in result.output

    def test_shorthand_syntax_accepted(self):
        """Test that shorthand syntax is accepted."""
        runner = CliRunner()

        # Use shorthand syntax - just test it doesn't fail on parsing
        result = runner.invoke(
            cli,
            ["put", "-~table.grid"],
            input='{"a":1}\n',
            catch_exceptions=False,
        )

        # Should not fail on syntax (may fail on execution)
        assert "Invalid address syntax" not in result.output
