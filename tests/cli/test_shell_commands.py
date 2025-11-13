"""CLI integration tests for shell command plugins."""

import json


def test_ls_basic(invoke):
    """Test basic ls command through CLI."""
    result = invoke(["cat", "ls"])
    assert result.exit_code == 0

    # Should output NDJSON
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) > 0

    # First record should have filename
    record = json.loads(lines[0])
    assert "filename" in record


def test_ls_with_parameters(invoke, tmp_path):
    """Test ls with query parameters."""
    # Create temp directory with files
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    result = invoke(["cat", f"ls?path={tmp_path}&long=true"])
    assert result.exit_code == 0

    # Should have detailed listing
    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) >= 1

    record = json.loads(lines[0])
    assert "filename" in record
    assert "flags" in record  # Long format includes flags
    assert "test.txt" in record["filename"]


def test_ls_pipeline(invoke, tmp_path):
    """Test ls piped through filter."""
    # Create temp files
    (tmp_path / "foo.txt").write_text("foo")
    (tmp_path / "bar.txt").write_text("bar")
    (tmp_path / "baz.log").write_text("baz")

    # List then filter for .txt files
    cat_result = invoke(["cat", f"ls?path={tmp_path}"])
    assert cat_result.exit_code == 0

    # Filter should work (tested separately, just verify ls output is valid NDJSON)
    lines = [line for line in cat_result.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    filenames = [r["filename"] for r in records]
    assert "foo.txt" in filenames
    assert "bar.txt" in filenames
    assert "baz.log" in filenames
