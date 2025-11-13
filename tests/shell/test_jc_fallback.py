"""Tests for jc fallback functionality."""

import json
import subprocess
import sys

import pytest

from jn.shell.jc_fallback import (
    execute_with_jc,
    is_jc_available,
    supports_command,
)


def test_is_jc_available():
    """Test jc availability check."""
    # jc should be available since it's a dependency
    assert is_jc_available() is True


def test_supports_command_for_common_commands():
    """Test that jc supports common Unix commands."""
    if not is_jc_available():
        pytest.skip("jc not available")

    # These are definitely supported by jc
    assert supports_command("ls") is True
    assert supports_command("ps") is True
    assert supports_command("df") is True
    assert supports_command("du") is True
    assert supports_command("env") is True


def test_supports_command_returns_false_for_unsupported():
    """Test that jc correctly reports unsupported commands."""
    if not is_jc_available():
        pytest.skip("jc not available")

    # This command definitely doesn't exist in jc
    assert supports_command("nonexistent_command_xyz") is False


def test_execute_with_jc_ls(tmp_path):
    """Test executing ls command through jc fallback."""
    if not is_jc_available():
        pytest.skip("jc not available")

    # Create test files
    (tmp_path / "test1.txt").write_text("content1")
    (tmp_path / "test2.txt").write_text("content2")

    # Capture output of execute_with_jc
    result = subprocess.run(
        [sys.executable, "-c",
         f"from jn.shell.jc_fallback import execute_with_jc; "
         f"import sys; sys.exit(execute_with_jc('ls -l {tmp_path}'))"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) >= 2  # At least our 2 test files

    # Verify it's valid NDJSON
    records = [json.loads(line) for line in lines]
    filenames = [r["filename"] for r in records]
    assert "test1.txt" in filenames
    assert "test2.txt" in filenames

    # Verify jc schema (should have flags, owner, etc. for -l)
    assert "flags" in records[0]
    assert "owner" in records[0]


def test_execute_with_jc_ps():
    """Test executing ps command through jc fallback."""
    if not is_jc_available():
        pytest.skip("jc not available")

    result = subprocess.run(
        [sys.executable, "-c",
         "from jn.shell.jc_fallback import execute_with_jc; "
         "import sys; sys.exit(execute_with_jc('ps aux'))"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) > 0

    # Verify it's valid NDJSON with ps schema
    record = json.loads(lines[0])
    assert "pid" in record
    assert "user" in record
    assert "command" in record


def test_execute_with_jc_env():
    """Test executing env command through jc fallback."""
    if not is_jc_available():
        pytest.skip("jc not available")

    result = subprocess.run(
        [sys.executable, "-c",
         "from jn.shell.jc_fallback import execute_with_jc; "
         "import sys; sys.exit(execute_with_jc('env'))"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) > 0

    # Verify it's valid NDJSON with env schema
    records = [json.loads(line) for line in lines]
    assert all("name" in r and "value" in r for r in records)

    # Should have PATH
    names = [r["name"] for r in records]
    assert "PATH" in names


def test_execute_with_jc_unsupported_command():
    """Test that unsupported commands return error."""
    if not is_jc_available():
        pytest.skip("jc not available")

    result = subprocess.run(
        [sys.executable, "-c",
         "from jn.shell.jc_fallback import execute_with_jc; "
         "import sys; sys.exit(execute_with_jc('unsupported_xyz'))"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 1
    assert "does not support command" in result.stderr or "not found" in result.stderr
