"""Tests for the watchfiles shell plugin via the actual CLI."""

import json
import subprocess
import sys
import time
from pathlib import Path
import contextlib

import pytest


@pytest.fixture
def jn_cli():
    """Return path to jn CLI (installed in venv)."""
    import shutil

    jn_path = shutil.which("jn")
    if jn_path:
        return [jn_path]
    return [sys.executable, "-m", "jn.cli.main"]


def test_jn_sh_watchfiles_initial_snapshot(jn_cli, tmp_path: Path):
    """watchfiles emits initial snapshot and exits when --exit-after is set."""
    # Create an existing file before starting the watcher
    f = tmp_path / "seed.txt"
    f.write_text("hello")

    result = subprocess.run(
        [
            *jn_cli,
            "sh",
            "watchfiles",
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


def test_jn_sh_watchfiles_rejects_files(jn_cli, tmp_path: Path):
    """watchfiles should reject file paths and hint to use tail -F."""
    file_path = tmp_path / "log.txt"
    file_path.write_text("x")

    result = subprocess.run(
        [*jn_cli, "sh", "watchfiles", str(file_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "Path is a file" in result.stdout or "Path is a file" in result.stderr
    )
    # Helpful hint
    assert "tail -F" in (result.stdout + result.stderr)


def test_jn_sh_watchfiles_emits_on_change(jn_cli, tmp_path: Path):
    """watchfiles should emit a created event when a new file appears."""
    proc = subprocess.Popen(
        [
            *jn_cli,
            "sh",
            "watchfiles",
            str(tmp_path),
            "--debounce-ms",
            "10",
            "--exit-after",
            "1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Small delay to ensure watcher is running
        time.sleep(0.3)

        # Create a new file to trigger event
        new_file = tmp_path / "new.txt"
        new_file.write_text("x")

        out, err = proc.communicate(timeout=10)
        assert proc.returncode == 0, err
        lines = [line for line in out.strip().split("\n") if line]
        assert len(lines) >= 1
        rec = json.loads(lines[0])
        assert rec.get("event") in {"created", "modified", "exists"}
        # At least ensure it references our directory
        assert rec.get("root") == str(tmp_path)
    finally:
        with contextlib.suppress(Exception):
            proc.kill()
