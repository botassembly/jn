"""Tests for the watchfiles shell plugin via the actual CLI."""

import contextlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.fixture
def jn_cli():
    """Return path to jn CLI (installed in venv)."""
    import shutil

    jn_path = shutil.which("jn")
    if jn_path:
        return [jn_path]
    return [sys.executable, "-m", "jn.cli.main"]


def test_jn_sh_watch_initial_snapshot(jn_cli, tmp_path: Path):
    """watchfiles emits initial snapshot and exits when --exit-after is set."""
    # Create an existing file before starting the watcher
    f = tmp_path / "seed.txt"
    f.write_text("hello")

    result = subprocess.run(
        [
            *jn_cli,
            "sh",
            "watch",
            str(tmp_path),
            "--initial",
            "--exit-after",
            "1",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec.get("event") == "exists"
    assert rec.get("path", "").endswith("seed.txt")
    assert rec.get("is_dir") is False


def test_jn_sh_watch_rejects_files(jn_cli, tmp_path: Path):
    """watchfiles should reject file paths and hint to use tail -F."""
    file_path = tmp_path / "log.txt"
    file_path.write_text("x")

    result = subprocess.run(
        [*jn_cli, "sh", "watch", str(file_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "Path is a file" in result.stdout or "Path is a file" in result.stderr
    )
    # Helpful hint
    assert "tail -F" in (result.stdout + result.stderr)


def test_jn_sh_watch_include_exclude(jn_cli, tmp_path: Path):
    """Include/exclude globs should filter events."""
    # Prepare files
    (tmp_path / "keep.foo").write_text("x")
    (tmp_path / "skip.txt").write_text("x")

    # Include only *.foo
    result = subprocess.run(
        [
            *jn_cli,
            "sh",
            "watch",
            str(tmp_path),
            "--initial",
            "--include",
            "*.foo",
            "--exit-after",
            "1",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) == 1
    import json as _json

    rec = _json.loads(lines[0])
    assert rec["path"].endswith("keep.foo")

    # Exclude *.tmp (create an extra tmp file)
    (tmp_path / "foo.tmp").write_text("x")
    result = subprocess.run(
        [
            *jn_cli,
            "sh",
            "watch",
            str(tmp_path),
            "--initial",
            "--exclude",
            "*.tmp",
            "--exit-after",
            "1",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split("\n") if line]
    assert len(lines) == 1
    rec = _json.loads(lines[0])
    assert not rec["path"].endswith(".tmp")
