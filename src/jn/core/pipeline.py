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
from typing import Optional, TextIO

from ..discovery import get_cached_plugins_with_fallback
from ..registry import build_registry


class PipelineError(Exception):
    """Error during pipeline execution."""
    pass


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
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)
    registry = build_registry(plugins)

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
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)
    registry = build_registry(plugins)

    plugin_name = registry.match(dest)
    if not plugin_name:
        raise PipelineError(f"No plugin found for {dest}")

    plugin = plugins[plugin_name]

    # Execute writer
    with open(dest, "w") as outfile:
        proc = subprocess.Popen(
            [sys.executable, plugin.path, "--mode", "write"],
            stdin=input_stream,
            stdout=outfile,
            stderr=subprocess.PIPE,
        )

        proc.wait()

        if proc.returncode != 0:
            error_msg = proc.stderr.read().decode()
            raise PipelineError(f"Writer error: {error_msg}")


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
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)
    registry = build_registry(plugins)

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
    plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)

    # Find jq filter plugin
    if "jq_" not in plugins:
        raise PipelineError("jq filter plugin not found")

    plugin = plugins["jq_"]

    # Execute filter
    proc = subprocess.Popen(
        [sys.executable, plugin.path, "--query", query],
        stdin=input_stream,
        stdout=output_stream,
        stderr=subprocess.PIPE,
    )

    proc.wait()

    if proc.returncode != 0:
        error_msg = proc.stderr.read().decode()
        raise PipelineError(f"Filter error: {error_msg}")
