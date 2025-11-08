"""Integration tests for cat/head/tail commands."""

import json
import os
from pathlib import Path

import pytest

from jn.cli import app


@pytest.fixture
def csv_file(tmp_path):
    """Create a test CSV file."""
    csv_path = tmp_path / "test.csv"
    csv_path.write_text(
        "name,age,city\n"
        "Alice,30,NYC\n"
        "Bob,25,SF\n"
        "Charlie,35,LA\n"
        "Diana,28,Boston\n"
    )
    return csv_path


@pytest.fixture
def tsv_file(tmp_path):
    """Create a test TSV file."""
    tsv_path = tmp_path / "test.tsv"
    tsv_path.write_text(
        "name\tage\tcity\n"
        "Alice\t30\tNYC\n"
        "Bob\t25\tSF\n"
    )
    return tsv_path


@pytest.fixture
def psv_file(tmp_path):
    """Create a test PSV file."""
    psv_path = tmp_path / "test.psv"
    psv_path.write_text(
        "name|age|city\n"
        "Alice|30|NYC\n"
        "Bob|25|SF\n"
    )
    return psv_path


@pytest.fixture
def json_file(tmp_path):
    """Create a test JSON file."""
    json_path = tmp_path / "test.json"
    json_path.write_text('{"name": "Alice", "age": 30}\n{"name": "Bob", "age": 25}\n')
    return json_path


class TestCatCommand:
    """Test jn cat command."""

    def test_cat_csv_file(self, runner, csv_file):
        """Test cat with CSV file auto-detection."""
        result = runner.invoke(app, ["cat", str(csv_file)])

        assert result.exit_code == 0

        # Parse NDJSON output
        lines = result.output.strip().split("\n")
        assert len(lines) == 4

        first = json.loads(lines[0])
        assert first["name"] == "Alice"
        assert first["age"] == "30"
        assert first["city"] == "NYC"

        last = json.loads(lines[3])
        assert last["name"] == "Diana"

    def test_cat_tsv_file(self, runner, tsv_file):
        """Test cat with TSV file auto-detection."""
        result = runner.invoke(app, ["cat", str(tsv_file)])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["name"] == "Alice"
        assert first["age"] == "30"
        assert first["city"] == "NYC"

    def test_cat_psv_file(self, runner, psv_file):
        """Test cat with PSV file auto-detection."""
        result = runner.invoke(app, ["cat", str(psv_file)])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["name"] == "Alice"

    def test_cat_yaml_file(self, runner, tmp_path):
        """Test cat with YAML file auto-detection."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(
            "- name: Alice\n"
            "  age: 30\n"
            "- name: Bob\n"
            "  age: 25\n"
        )

        result = runner.invoke(app, ["cat", str(yaml_file)])
        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["name"] == "Alice"
        assert first["age"] == 30

    def test_cat_toml_file(self, runner, tmp_path):
        """Test cat with TOML file auto-detection."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text(
            "[[items]]\n"
            'name = "Alice"\n'
            "age = 30\n"
        )

        result = runner.invoke(app, ["cat", str(toml_file)])
        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        parsed = json.loads(lines[0])
        assert parsed["name"] == "Alice"

    def test_cat_xml_file(self, runner, tmp_path):
        """Test cat with XML file auto-detection."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(
            '<?xml version="1.0"?>\n'
            "<root>\n"
            "  <item>value</item>\n"
            "</root>\n"
        )

        result = runner.invoke(app, ["cat", str(xml_file)])
        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        parsed = json.loads(lines[0])
        assert "root" in parsed

    def test_cat_json_file_passthrough(self, runner, json_file):
        """Test cat with JSON file (no parsing, just passthrough)."""
        result = runner.invoke(app, ["cat", str(json_file)])

        assert result.exit_code == 0
        # JSON file should be passed through as-is
        assert '{"name": "Alice", "age": 30}' in result.output

    def test_cat_generic_parser_echo(self, runner):
        """Test cat with generic parser for unknown command (echo)."""
        result = runner.invoke(app, ["cat", "echo", "Hello World"])

        assert result.exit_code == 0

        data = json.loads(result.output.strip())
        assert data["line"] == 1
        assert data["text"] == "Hello World"
        assert data["command"] == "echo"
        assert data["args"] == ["Hello World"]

    def test_cat_generic_parser_multiline(self, runner):
        """Test generic parser with multi-line output."""
        result = runner.invoke(app, ["cat", "printf", "line1\\nline2\\nline3"])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 3

        first = json.loads(lines[0])
        assert first["line"] == 1
        assert first["text"] == "line1"

        third = json.loads(lines[2])
        assert third["line"] == 3
        assert third["text"] == "line3"

    def test_cat_nonexistent_file(self, runner):
        """Test cat with nonexistent file."""
        result = runner.invoke(app, ["cat", "/tmp/nonexistent.csv"])

        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_cat_force_driver_file(self, runner, csv_file):
        """Test cat with forced driver override."""
        result = runner.invoke(
            app, ["cat", "--driver", "file", str(csv_file)]
        )

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 4

    @pytest.mark.skipif(
        os.getenv("JN_OFFLINE") == "1",
        reason="Network test disabled in offline mode",
    )
    def test_cat_url_httpbin(self, runner):
        """Test cat with URL (curl driver auto-detection)."""
        result = runner.invoke(app, ["cat", "https://httpbin.org/json"])

        # Network test may fail in some environments
        # Accept success (exit 0) or network error (exit 1)
        if result.exit_code == 0:
            # httpbin.org/json returns a JSON document
            assert "slideshow" in result.output
        else:
            # Network error is acceptable
            assert result.exit_code == 1
            assert "Error:" in result.output


class TestHeadCommand:
    """Test jn head command."""

    def test_head_default_10_lines(self, runner, csv_file):
        """Test head with default 10 lines (file has only 4)."""
        result = runner.invoke(app, ["head", str(csv_file)])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 4  # File has only 4 records

    def test_head_limit_2_lines(self, runner, csv_file):
        """Test head with -n 2."""
        result = runner.invoke(app, ["head", "-n", "2", str(csv_file)])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["name"] == "Alice"

        second = json.loads(lines[1])
        assert second["name"] == "Bob"

    def test_head_zero_lines(self, runner, csv_file):
        """Test head with -n 0."""
        result = runner.invoke(app, ["head", "-n", "0", str(csv_file)])

        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_head_generic_command(self, runner):
        """Test head with generic parser command."""
        result = runner.invoke(
            app, ["head", "-n", "1", "printf", "a\\nb\\nc"]
        )

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["text"] == "a"

    def test_head_tsv_file(self, runner, tsv_file):
        """Test head with TSV file."""
        result = runner.invoke(app, ["head", "-n", "1", str(tsv_file)])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["name"] == "Alice"


class TestTailCommand:
    """Test jn tail command."""

    def test_tail_default_10_lines(self, runner, csv_file):
        """Test tail with default 10 lines (file has only 4)."""
        result = runner.invoke(app, ["tail", str(csv_file)])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 4  # File has only 4 records

    def test_tail_limit_2_lines(self, runner, csv_file):
        """Test tail with -n 2."""
        result = runner.invoke(app, ["tail", "-n", "2", str(csv_file)])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 2

        # Should get last 2 records: Charlie and Diana
        first = json.loads(lines[0])
        assert first["name"] == "Charlie"

        second = json.loads(lines[1])
        assert second["name"] == "Diana"

    def test_tail_one_line(self, runner, csv_file):
        """Test tail with -n 1."""
        result = runner.invoke(app, ["tail", "-n", "1", str(csv_file)])

        assert result.exit_code == 0

        data = json.loads(result.output.strip())
        assert data["name"] == "Diana"  # Last record

    def test_tail_generic_command(self, runner):
        """Test tail with generic parser command."""
        result = runner.invoke(
            app, ["tail", "-n", "2", "printf", "a\\nb\\nc\\nd"]
        )

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 2

        # Should get last 2 lines: c and d
        first = json.loads(lines[0])
        assert first["text"] == "c"

        second = json.loads(lines[1])
        assert second["text"] == "d"

    def test_tail_tsv_file(self, runner, tsv_file):
        """Test tail with TSV file."""
        result = runner.invoke(app, ["tail", "-n", "1", str(tsv_file)])

        assert result.exit_code == 0

        data = json.loads(result.output.strip())
        assert data["name"] == "Bob"  # Last record in TSV


class TestCatWithJqPipeline:
    """Test cat commands piped through jq (simulated)."""

    def test_cat_csv_output_structure(self, runner, csv_file):
        """Test that cat CSV output is valid NDJSON for jq."""
        result = runner.invoke(app, ["cat", str(csv_file)])

        assert result.exit_code == 0

        # Verify each line is valid JSON
        lines = result.output.strip().split("\n")
        for line in lines:
            data = json.loads(line)  # Should not raise
            assert isinstance(data, dict)
            assert "name" in data
            assert "age" in data
            assert "city" in data

    def test_head_preserves_json_structure(self, runner, csv_file):
        """Test that head output is valid NDJSON."""
        result = runner.invoke(app, ["head", "-n", "2", str(csv_file)])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 2

        for line in lines:
            data = json.loads(line)
            assert isinstance(data, dict)


class TestAutoDetection:
    """Test auto-detection logic for different source types."""

    def test_detects_csv_by_extension(self, runner, csv_file):
        """Verify .csv extension triggers CSV parser."""
        result = runner.invoke(app, ["cat", str(csv_file)])

        assert result.exit_code == 0
        # Should parse as CSV (NDJSON output)
        first_line = result.output.strip().split("\n")[0]
        data = json.loads(first_line)
        assert data["name"] == "Alice"

    def test_detects_tsv_by_extension(self, runner, tsv_file):
        """Verify .tsv extension triggers TSV parser."""
        result = runner.invoke(app, ["cat", str(tsv_file)])

        assert result.exit_code == 0
        first_line = result.output.strip().split("\n")[0]
        data = json.loads(first_line)
        assert data["name"] == "Alice"

    def test_detects_url_pattern(self, runner):
        """Verify http:// triggers curl driver."""
        # This will fail without network, but we can check it tries curl
        result = runner.invoke(app, ["cat", "http://localhost:9999/fake"])

        # Will likely fail (connection error), but should attempt curl
        # Exit code 1 is expected for network error
        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_generic_parser_for_unknown_command(self, runner):
        """Verify unknown commands use generic parser."""
        result = runner.invoke(app, ["cat", "echo", "test"])

        assert result.exit_code == 0

        data = json.loads(result.output.strip())
        # Generic parser output structure
        assert "line" in data
        assert "text" in data
        assert "command" in data
        assert data["command"] == "echo"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_cat_empty_file(self, runner, tmp_path):
        """Test cat with empty file."""
        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("")

        result = runner.invoke(app, ["cat", str(empty_file)])

        # Empty file should succeed but produce no output
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_head_with_empty_output(self, runner, tmp_path):
        """Test head when command produces no output."""
        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("")

        result = runner.invoke(app, ["head", str(empty_file)])

        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_tail_with_fewer_lines_than_n(self, runner, tmp_path):
        """Test tail when file has fewer lines than -n."""
        small_csv = tmp_path / "small.csv"
        small_csv.write_text("name,age\nAlice,30\n")

        result = runner.invoke(app, ["tail", "-n", "10", str(small_csv)])

        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        assert len(lines) == 1  # Only 1 record
