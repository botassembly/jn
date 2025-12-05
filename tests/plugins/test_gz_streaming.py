"""Streaming behavior tests for the Zig gzip plugin."""

import subprocess
import sys
from pathlib import Path


PLUGIN_DIR = Path(__file__).parent.parent.parent / "plugins" / "zig" / "gz" / "bin"


def _gz_plugin_path() -> str:
    """Get path to Zig gz plugin binary."""
    binary = PLUGIN_DIR / "gz"
    if not binary.exists():
        return None
    return str(binary)


def test_gz_streams_and_handles_broken_pipe(tmp_path: Path):
    """gz plugin should stream and exit cleanly when downstream closes."""
    gz_binary = _gz_plugin_path()
    if not gz_binary:
        import pytest
        pytest.skip("Zig gz plugin not built (run 'make zig-plugins')")

    # Producer: emit compressed bytes for a large payload
    producer = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import gzip,sys; data=(b'a,b\\n'*50000); "
                "sys.stdout.buffer.write(gzip.compress(data))"
            ),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Decompressor: our Zig plugin under test
    gz_proc = subprocess.Popen(
        [gz_binary, "--mode=raw"],
        stdin=producer.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Close our handle to producer stdout to enable proper SIGPIPE propagation
    if producer.stdout:
        producer.stdout.close()

    # Consumer: read only a small amount, then close (simulate head -c 100)
    head_proc = subprocess.Popen(
        ["head", "-c", "100"],
        stdin=gz_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Close our handle to gz stdout so only head holds the pipe
    if gz_proc.stdout:
        gz_proc.stdout.close()

    out, _err = head_proc.communicate(timeout=10)
    assert head_proc.returncode == 0
    assert len(out) <= 100

    # Wait for gz plugin to notice closed pipe and exit cleanly
    gz_proc.wait(timeout=10)
    # Some platforms/tools may exit with a SIGPIPE-ish code; accept 0 or common SIGPIPE codes
    assert gz_proc.returncode in (0, 120, 141)

    # Producer should also exit
    producer.wait(timeout=10)
    assert producer.returncode == 0
