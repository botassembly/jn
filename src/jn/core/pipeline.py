"""Pipeline execution - core streaming and conversion logic.

This module handles the actual execution of data pipelines:
- Reading from sources (files, stdin)
- Writing to destinations (files, stdout)
- Executing plugins as subprocesses
- Managing pipeline stages
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, TextIO, Tuple

from ..discovery import get_cached_plugins_with_fallback
from ..registry import build_registry
from ..plugins.discovery import PluginMetadata


class PipelineError(Exception):
    """Error during pipeline execution."""
    pass


def _load_plugins_and_registry(
    plugin_dir: Path, cache_path: Optional[Path]
) -> Tuple[Dict[str, PluginMetadata], object]:
    """Load plugins and build registry (helper to reduce duplication).

    Args:
        plugin_dir: Plugin directory
        cache_path: Cache file path

    Returns:
        Tuple of (plugins dict, registry object)
    """
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)
    registry = build_registry(plugins)
    return plugins, registry


def _prepare_stdin_for_subprocess(
    input_stream: TextIO,
) -> Tuple[object, Optional[str], bool]:
    """Prepare stdin for subprocess (file handle or PIPE with data).

    Some environments (e.g., Click test runner) provide non-file streams.
    This helper detects whether we can pass the stream directly to subprocess
    or need to read it and feed via PIPE.

    Args:
        input_stream: Input stream to prepare

    Returns:
        Tuple of (stdin_source, input_data, text_mode)
        - stdin_source: Either the stream itself or subprocess.PIPE
        - input_data: None if stream, or data string if PIPE
        - text_mode: True if text data, False if bytes
    """
    try:
        input_stream.fileno()  # type: ignore[attr-defined]
        return input_stream, None, False
    except Exception:
        input_data = input_stream.read()
        text_mode = isinstance(input_data, str)
        return subprocess.PIPE, input_data, text_mode


def start_reader(
    source: str,
    plugin_dir: Path,
    cache_path: Optional[Path]
) -> subprocess.Popen:
    """Start a reader subprocess for a source file.

    Returns a Popen object with stdout pipe that can be consumed downstream.

    Args:
        source: Path to source file
        plugin_dir: Plugin directory
        cache_path: Cache file path

    Returns:
        subprocess.Popen with stdout=PIPE (text mode)

    Raises:
        PipelineError: If plugin not found
    """
    # Load plugins and find reader
    plugins, registry = _load_plugins_and_registry(plugin_dir, cache_path)

    plugin_name = registry.match(source)
    if not plugin_name:
        raise PipelineError(f"No plugin found for {source}")

    plugin = plugins[plugin_name]

    # Start reader subprocess
    infile = open(source)
    proc = subprocess.Popen(
        [sys.executable, plugin.path, "--mode", "read"],
        stdin=infile,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Attach infile to proc so it gets closed when caller is done
    proc._jn_infile = infile

    return proc


def read_source(
    source: str,
    plugin_dir: Path,
    cache_path: Optional[Path],
    output_stream: TextIO = sys.stdout
) -> None:
    """Read a source file and output NDJSON to stream.

    Args:
        source: Path to source file
        plugin_dir: Plugin directory
        cache_path: Cache file path
        output_stream: Where to write output (default: stdout)

    Raises:
        PipelineError: If plugin not found or execution fails
    """
    proc = start_reader(source, plugin_dir, cache_path)

    # Copy stdout to output_stream
    for line in proc.stdout:
        output_stream.write(line)

    proc.wait()
    proc._jn_infile.close()

    if proc.returncode != 0:
        error_msg = proc.stderr.read()
        raise PipelineError(f"Reader error: {error_msg}")


def write_destination(
    dest: str,
    plugin_dir: Path,
    cache_path: Optional[Path],
    input_stream: TextIO = sys.stdin
) -> None:
    """Read NDJSON from stream and write to destination file.

    Args:
        dest: Path to destination file
        plugin_dir: Plugin directory
        cache_path: Cache file path
        input_stream: Where to read input (default: stdin)

    Raises:
        PipelineError: If plugin not found or execution fails
    """
    # Load plugins and find writer
    plugins, registry = _load_plugins_and_registry(plugin_dir, cache_path)

    plugin_name = registry.match(dest)
    if not plugin_name:
        raise PipelineError(f"No plugin found for {dest}")

    plugin = plugins[plugin_name]

    # Execute writer
    with open(dest, "w") as outfile:
        stdin_source, input_data, text_mode = _prepare_stdin_for_subprocess(
            input_stream
        )

        proc = subprocess.Popen(
            [sys.executable, plugin.path, "--mode", "write"],
            stdin=stdin_source,
            stdout=outfile,
            stderr=subprocess.PIPE,
            text=text_mode,
        )

        if input_data is not None:
            proc.stdin.write(input_data)  # type: ignore[union-attr]
            proc.stdin.close()  # type: ignore[union-attr]

        proc.wait()

        if proc.returncode != 0:
            err = proc.stderr.read()
            if not text_mode and isinstance(err, bytes):
                err = err.decode()
            raise PipelineError(f"Writer error: {err}")


def convert(
    source: str,
    dest: str,
    plugin_dir: Path,
    cache_path: Optional[Path]
) -> None:
    """Convert source file to destination format.

    Two-stage pipeline: read → write with automatic backpressure.

    Args:
        source: Path to source file
        dest: Path to destination file
        plugin_dir: Plugin directory
        cache_path: Cache file path

    Raises:
        PipelineError: If plugin not found or execution fails
    """
    # Load plugins
    plugins, registry = _load_plugins_and_registry(plugin_dir, cache_path)

    # Resolve reader
    reader_name = registry.match(source)
    if not reader_name:
        raise PipelineError(f"No plugin found for {source}")

    reader_plugin = plugins[reader_name]

    # Resolve writer
    writer_name = registry.match(dest)
    if not writer_name:
        raise PipelineError(f"No plugin found for {dest}")

    writer_plugin = plugins[writer_name]

    # Execute two-stage pipeline
    with open(source) as infile, open(dest, "w") as outfile:
        # Start reader
        reader = subprocess.Popen(
            [sys.executable, reader_plugin.path, "--mode", "read"],
            stdin=infile,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Start writer
        writer = subprocess.Popen(
            [sys.executable, writer_plugin.path, "--mode", "write"],
            stdin=reader.stdout,
            stdout=outfile,
            stderr=subprocess.PIPE,
        )

        # Close reader stdout in parent (critical for SIGPIPE backpressure)
        reader.stdout.close()

        # Wait for both processes
        writer.wait()
        reader.wait()

        # Check for errors
        if writer.returncode != 0:
            error_msg = writer.stderr.read().decode()
            raise PipelineError(f"Writer error: {error_msg}")

        if reader.returncode != 0:
            error_msg = reader.stderr.read().decode()
            raise PipelineError(f"Reader error: {error_msg}")


def filter_stream(
    query: str,
    plugin_dir: Path,
    cache_path: Optional[Path],
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout
) -> None:
    """Filter NDJSON stream using jq expression.

    Args:
        query: jq expression
        plugin_dir: Plugin directory
        cache_path: Cache file path
        input_stream: Where to read input (default: stdin)
        output_stream: Where to write output (default: stdout)

    Raises:
        PipelineError: If jq plugin not found or execution fails
    """
    # Load plugins
    plugins, _ = _load_plugins_and_registry(plugin_dir, cache_path)

    # Find jq filter plugin
    if "jq_" not in plugins:
        raise PipelineError("jq filter plugin not found")

    plugin = plugins["jq_"]

    # Execute filter
    stdin_source, input_data, _ = _prepare_stdin_for_subprocess(input_stream)

    proc = subprocess.Popen(
        [sys.executable, plugin.path, "--query", query],
        stdin=stdin_source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if input_data is not None:
        proc.stdin.write(input_data)  # type: ignore[union-attr]
        proc.stdin.close()  # type: ignore[union-attr]

    # Stream output to provided output_stream to respect Click runner
    assert proc.stdout is not None
    for line in proc.stdout:
        output_stream.write(line)

    proc.wait()

    if proc.returncode != 0:
        err = proc.stderr.read()
        raise PipelineError(f"Filter error: {err}")
