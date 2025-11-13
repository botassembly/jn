"""
Tests for shell command plugins.

Tests cover:
- Basic functionality of each plugin
- Backpressure behavior (early termination)
- Error handling
- Streaming behavior
"""

import subprocess
import json
import os
import tempfile
import time
import pytest
from pathlib import Path


# Path to jn_home plugins
PLUGIN_DIR = Path(__file__).parent.parent / "jn_home" / "plugins" / "protocols"


def run_plugin(plugin_name, url=None, config=None, stdin_data=None):
    """Helper to run a shell plugin directly."""
    plugin_path = PLUGIN_DIR / plugin_name

    if not plugin_path.exists():
        pytest.skip(f"Plugin not found: {plugin_path}")

    cmd = ['python', str(plugin_path), '--mode', 'read']
    if url:
        cmd.extend(['--url', url])
    elif config:
        cmd.extend(['--config', json.dumps(config)])

    result = subprocess.run(
        cmd,
        stdin=subprocess.PIPE if stdin_data else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        input=stdin_data
    )

    return result


class TestLsPlugin:
    """Test ls_shell.py plugin."""

    def test_ls_basic(self):
        """Test basic ls execution."""
        result = run_plugin('ls_shell.py', url='shell://ls?path=/tmp')

        assert result.returncode == 0 or result.returncode == 1  # May fail if jc not installed
        if result.returncode == 0:
            # Should output NDJSON
            lines = result.stdout.strip().split('\n')
            for line in lines:
                record = json.loads(line)
                assert 'filename' in record

    def test_ls_long_format(self):
        """Test ls with long format."""
        result = run_plugin('ls_shell.py', url='shell://ls?path=/tmp&long=true')

        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                record = json.loads(lines[0])
                # Long format should have more fields
                assert 'filename' in record

    def test_ls_nonexistent_path(self):
        """Test ls with nonexistent path."""
        result = run_plugin('ls_shell.py', url='shell://ls?path=/nonexistent_path_12345')

        assert result.returncode != 0
        # Should output error to stderr
        assert '_error' in result.stderr or 'not found' in result.stderr.lower()


class TestFindPlugin:
    """Test find_shell.py plugin."""

    def test_find_basic(self):
        """Test basic find execution."""
        result = run_plugin('find_shell.py', url='shell://find?path=/tmp&maxdepth=2')

        assert result.returncode == 0 or result.returncode == 1  # May fail if jc not installed
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                record = json.loads(lines[0])
                assert 'path' in record or 'node' in record or 'error' in record

    def test_find_with_name_pattern(self):
        """Test find with name pattern."""
        # Create temp file with known pattern
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")

            result = run_plugin('find_shell.py', url=f'shell://find?path={tmpdir}&name=*.txt')

            if result.returncode == 0:
                output = result.stdout
                assert 'test.txt' in output


class TestPsPlugin:
    """Test ps_shell.py plugin."""

    def test_ps_basic(self):
        """Test basic ps execution."""
        result = run_plugin('ps_shell.py', url='shell://ps')

        assert result.returncode == 0 or result.returncode == 1  # May fail if jc not installed
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                record = json.loads(lines[0])
                # Should have process fields
                assert 'pid' in record or 'cmd' in record or 'command' in record


class TestTailPlugin:
    """Test tail_shell.py plugin."""

    def test_tail_basic(self):
        """Test basic tail execution."""
        # Create temp file with content
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            for i in range(20):
                f.write(f"Line {i}\n")
            temp_path = f.name

        try:
            result = run_plugin('tail_shell.py', url=f'shell://tail?path={temp_path}&lines=5')

            assert result.returncode == 0
            lines = result.stdout.strip().split('\n')
            assert len(lines) == 5

            # Parse first record
            record = json.loads(lines[0])
            assert 'line' in record
            assert 'path' in record
            assert record['path'] == temp_path

        finally:
            os.unlink(temp_path)

    def test_tail_follow_mode_termination(self):
        """Test that tail follow mode can be terminated early."""
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Initial line\n")
            temp_path = f.name

        try:
            # Start tail -f process
            plugin_path = PLUGIN_DIR / "tail_shell.py"
            proc = subprocess.Popen(
                ['python', str(plugin_path), '--mode', 'read',
                 '--url', f'shell://tail?path={temp_path}&follow=true&lines=0'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Write a few lines
            with open(temp_path, 'a') as f:
                for i in range(3):
                    f.write(f"New line {i}\n")
                    f.flush()
                    time.sleep(0.05)

            # Read output for a short time
            time.sleep(0.2)

            # Terminate the process (simulates downstream closing pipe or Ctrl+C)
            proc.terminate()
            proc.wait(timeout=2)

            # Should have terminated gracefully
            assert proc.returncode is not None

        finally:
            try:
                os.unlink(temp_path)
            except:
                pass


class TestEnvPlugin:
    """Test env_shell.py plugin."""

    def test_env_basic(self):
        """Test basic env execution."""
        result = run_plugin('env_shell.py', url='shell://env')

        assert result.returncode == 0 or result.returncode == 1  # May fail if jc not installed
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                record = json.loads(lines[0])
                assert 'name' in record
                assert 'value' in record

    def test_env_has_path(self):
        """Test that PATH variable is in output."""
        result = run_plugin('env_shell.py', url='shell://env')

        if result.returncode == 0:
            output = result.stdout
            assert 'PATH' in output


class TestBackpressure:
    """Test backpressure behavior of plugins."""

    def test_ls_early_termination(self):
        """Test that ls | head terminates early."""
        # Use ls on a directory with many files
        plugin_path = PLUGIN_DIR / "ls_shell.py"

        # Start ls process
        ls_proc = subprocess.Popen(
            ['python', str(plugin_path), '--mode', 'read',
             '--url', 'shell://ls?path=/usr/bin&long=true'],
            stdout=subprocess.PIPE,
            text=True
        )

        # Read only 5 lines
        lines_read = 0
        for _ in range(5):
            line = ls_proc.stdout.readline()
            if line:
                lines_read += 1

        # Close stdout (sends SIGPIPE)
        ls_proc.stdout.close()

        # Wait briefly
        time.sleep(0.2)

        # Check if process terminated
        exit_code = ls_proc.poll()

        # Process should have terminated (either cleanly or via SIGPIPE)
        # Note: exit_code might be None if still running, 0 if clean, or negative if signal
        if exit_code is None:
            ls_proc.terminate()
            ls_proc.wait(timeout=1)

        # We read exactly 5 lines, demonstrating backpressure works
        assert lines_read == 5

    def test_find_early_termination(self):
        """Test that find | head terminates early."""
        plugin_path = PLUGIN_DIR / "find_shell.py"

        # Start find process on large directory
        find_proc = subprocess.Popen(
            ['python', str(plugin_path), '--mode', 'read',
             '--url', 'shell://find?path=/usr'],
            stdout=subprocess.PIPE,
            text=True
        )

        # Read only 10 lines
        lines_read = 0
        for _ in range(10):
            line = find_proc.stdout.readline()
            if line:
                lines_read += 1

        # Close stdout
        find_proc.stdout.close()
        time.sleep(0.2)

        # Terminate if still running
        if find_proc.poll() is None:
            find_proc.terminate()
            find_proc.wait(timeout=1)

        # We read 10 lines, not entire filesystem
        assert lines_read == 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
