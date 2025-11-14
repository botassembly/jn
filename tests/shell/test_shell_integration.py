"""Integration tests for shell commands via actual CLI (not CliRunner)."""

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def jn_cli():
    """Return path to jn CLI."""
    # Use the jn command from PATH (installed in venv)
    import shutil

    jn_path = shutil.which("jn")
    if jn_path:
        return [jn_path]
    # Fallback: use python -m jn.cli.main
    return [sys.executable, "-m", "jn.cli.main"]


def test_jn_sh_ls(jn_cli, tmp_path):
    """Test jn sh ls -l command."""
    # Create test files
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.txt").write_text("content2")

    result = subprocess.run(
        [*jn_cli, "sh", "ls", "-l", str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 2

    # Verify NDJSON with jc schema
    records = [json.loads(line) for line in lines]
    filenames = [r["filename"] for r in records]
    assert "file1.txt" in filenames
    assert "file2.txt" in filenames

    # Should have jc fields
    assert "flags" in records[0]
    assert "size" in records[0]


def test_jn_sh_ls_simple(jn_cli, tmp_path):
    """Test jn sh ls (without -l) degrades gracefully to filenames-only."""
    # Create test files
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")

    result = subprocess.run(
        [*jn_cli, "sh", "ls", str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 2

    # Should be valid NDJSON with minimal schema (filename only)
    records = [json.loads(line) for line in lines]
    filenames = [r["filename"] for r in records]
    assert "a.txt" in filenames
    assert "b.txt" in filenames

    # Short ls output should not include long listing fields like 'flags'
    assert all("flags" not in r for r in records)


def test_jn_cat_ls(jn_cli, tmp_path):
    """Test jn cat 'ls -l' command."""
    # Create test file
    (tmp_path / "test.txt").write_text("content")

    result = subprocess.run(
        [*jn_cli, "cat", f"ls -l {tmp_path}"], capture_output=True, text=True
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 1

    record = json.loads(lines[0])
    assert "filename" in record
    assert "test.txt" in record["filename"]


def test_jn_sh_ps(jn_cli):
    """Test jn sh ps aux command."""
    result = subprocess.run(
        [*jn_cli, "sh", "ps", "aux"], capture_output=True, text=True
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) > 0

    # Verify ps schema
    record = json.loads(lines[0])
    assert "pid" in record
    assert "user" in record
    assert "command" in record


def test_jn_sh_env(jn_cli):
    """Test jn sh env command."""
    result = subprocess.run(
        [*jn_cli, "sh", "env"], capture_output=True, text=True
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) > 0

    # Verify env schema
    records = [json.loads(line) for line in lines]
    assert all("name" in r and "value" in r for r in records)

    # Should have PATH
    names = [r["name"] for r in records]
    assert "PATH" in names


def test_jn_sh_df(jn_cli):
    """Test jn sh df -h command."""
    result = subprocess.run(
        [*jn_cli, "sh", "df", "-h"], capture_output=True, text=True
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) > 0

    # Verify df schema
    record = json.loads(lines[0])
    assert "filesystem" in record
    assert "mounted_on" in record


def test_jn_sh_unsupported_command(jn_cli):
    """Test that unsupported commands give clear error."""
    result = subprocess.run(
        [*jn_cli, "sh", "totally_fake_command_xyz"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "No plugin or jc parser found" in result.stderr


def test_jn_sh_pipeline_with_head(jn_cli, tmp_path):
    """Test that jc fallback works with Unix pipelines (backpressure)."""
    # Create many files
    for i in range(100):
        (tmp_path / f"file{i:03d}.txt").write_text(f"content{i}")

    # Build the pipeline without shell=True to satisfy security checks.
    # Critical: close reader stdout in parent for SIGPIPE backpressure.
    p_reader = subprocess.Popen(
        [*jn_cli, "sh", "ls", "-l", str(tmp_path)],
        stdout=subprocess.PIPE,
    )
    try:
        p_head = subprocess.Popen(
            ["head", "-n", "5"],
            stdin=p_reader.stdout,
            stdout=subprocess.PIPE,
        )
        # Critical for SIGPIPE propagation per backpressure spec
        if p_reader.stdout is not None:
            p_reader.stdout.close()

        stdout, _ = p_head.communicate()
        returncode = p_head.returncode
        output = stdout.decode()
    finally:
        # Ensure reader process is reaped
        p_reader.wait()

    assert returncode == 0
    lines = [line for line in output.strip().split("\n") if line]
    assert len(lines) == 5  # head should limit to 5

    # All should be valid JSON
    for line in lines:
        record = json.loads(line)
        assert "filename" in record


def test_custom_plugin_takes_priority_over_jc(jn_cli):
    """Test that custom tail plugin is used instead of jc."""
    # Create a test file
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt"
    ) as f:
        f.write("line1\nline2\nline3\n")
        f.flush()
        temp_file = f.name

    try:
        result = subprocess.run(
            [*jn_cli, "sh", "tail", "-n", "2", temp_file],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        lines = [line for line in result.stdout.strip().split("\n") if line]
        assert len(lines) == 2

        # Custom tail plugin wraps with line_number
        record = json.loads(lines[0])
        assert "line" in record
        assert "line_number" in record
    finally:
        Path(temp_file).unlink()


def test_jn_cat_with_shell_command(jn_cli):
    """Test that jn cat works with shell command plugins."""
    # Create a test file
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt"
    ) as f:
        f.write("line1\nline2\nline3\nline4\nline5\n")
        f.flush()
        temp_file = f.name

    try:
        # Test jn cat with tail command (should use tail_shell plugin)
        result = subprocess.run(
            [*jn_cli, "cat", f"tail -n 3 {temp_file}"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed with stderr: {result.stderr}"
        lines = [line for line in result.stdout.strip().split("\n") if line]
        assert len(lines) == 3

        # Verify it's using the custom tail plugin (has line_number field)
        for line in lines:
            record = json.loads(line)
            assert "line" in record
            assert "line_number" in record

        # Verify content
        record = json.loads(lines[0])
        assert "line3" in record["line"]
    finally:
        Path(temp_file).unlink()
