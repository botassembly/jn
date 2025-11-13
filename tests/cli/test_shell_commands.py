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


def test_ls_with_flags(invoke, tmp_path):
    """Test ls with flags and path."""
    # Create temp directory with files
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    result = invoke(["cat", f"ls -l {tmp_path}"])
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

    # List directory
    cat_result = invoke(["cat", f"ls {tmp_path}"])
    assert cat_result.exit_code == 0

    # Verify ls output is valid NDJSON
    lines = [line for line in cat_result.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    filenames = [r["filename"] for r in records]
    assert "foo.txt" in filenames
    assert "bar.txt" in filenames
    assert "baz.log" in filenames


def test_sh_command_basic(invoke):
    """Test sh command with basic ls."""
    result = invoke(["sh", "ls"])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    assert len(lines) > 0

    record = json.loads(lines[0])
    assert "filename" in record


def test_sh_command_with_flags(invoke, tmp_path):
    """Test sh command with flags - no quoting needed."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    result = invoke(["sh", "ls", "-l", str(tmp_path)])
    assert result.exit_code == 0

    lines = [line for line in result.output.strip().split("\n") if line]
    record = json.loads(lines[0])
    assert "filename" in record
    assert "flags" in record
    assert "test.txt" in record["filename"]


def test_sh_vs_cat_equivalence(invoke):
    """Test that sh and cat produce equivalent output."""
    cat_result = invoke(["cat", "ls -l"])
    sh_result = invoke(["sh", "ls", "-l"])

    assert cat_result.exit_code == 0
    assert sh_result.exit_code == 0

    # Both should produce valid NDJSON
    cat_lines = [l for l in cat_result.output.strip().split("\n") if l]
    sh_lines = [l for l in sh_result.output.strip().split("\n") if l]

    assert len(cat_lines) == len(sh_lines)

    # First records should be equivalent
    cat_record = json.loads(cat_lines[0])
    sh_record = json.loads(sh_lines[0])

    assert cat_record["filename"] == sh_record["filename"]
