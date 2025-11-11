"""Pipeline execution - core streaming and conversion logic.

This module handles the actual execution of data pipelines:
- Reading from sources (files, stdin)
- Writing to destinations (files, stdout)
- Executing plugins as subprocesses
- Managing pipeline stages
"""

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, TextIO, Tuple

from ..plugins.discovery import PluginMetadata, get_cached_plugins_with_fallback
from ..plugins.registry import build_registry
from ..profiles.http import resolve_profile_reference
from ..profiles.http import ProfileError as HTTPProfileError
from ..profiles.resolver import resolve_profile, ProfileError


class PipelineError(Exception):
    """Error during pipeline execution."""
    pass


# Binary formats that require buffering (cannot be streamed)
# BACKPRESSURE EXCEPTION: These formats MUST buffer complete input before parsing
# - XLSX/XLSM: ZIP archives, central directory at EOF, requires random access
# - PDF: Cross-reference table at EOF, requires random access
# - ZIP/GZ: Compression requires full context
# - Parquet: Columnar format with footer metadata
_BINARY_FORMATS = {'.xlsx', '.xlsm', '.pdf', '.zip', '.gz', '.parquet'}


def _is_binary_format_url(url: str) -> bool:
    """Check if URL points to a binary format that needs curl streaming."""
    from urllib.parse import urlparse
    ext = Path(urlparse(url).path).suffix.lower()
    return ext in _BINARY_FORMATS


def _check_uv_available() -> None:
    """Check if UV is available and exit with helpful message if not."""
    if not shutil.which("uv"):
        print("Error: UV is required to run JN plugins", file=sys.stderr)
        print("", file=sys.stderr)
        print("Install UV with one of these methods:", file=sys.stderr)
        print("  curl -LsSf https://astral.sh/uv/install.sh | sh", file=sys.stderr)
        print("  pip install uv", file=sys.stderr)
        print("", file=sys.stderr)
        print("More info: https://docs.astral.sh/uv/", file=sys.stderr)
        sys.exit(1)


def _check_jq_available() -> None:
    """Check if jq is available and raise error if not.

    Raises:
        PipelineError: If jq command not found
    """
    if not shutil.which("jq"):
        raise PipelineError(
            "jq command not found\n"
            "Install from: https://jqlang.github.io/jq/\n"
            "  macOS: brew install jq\n"
            "  Ubuntu/Debian: apt-get install jq\n"
            "  Fedora: dnf install jq"
        )


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


def _resolve_plugin_name(plugin_name: str, plugins: Dict[str, PluginMetadata]) -> Optional[str]:
    """Resolve plugin name with fallback to underscore suffix.

    Strategy:
    1. Try exact match first (highest priority)
    2. Try with underscore suffix as fallback
    3. Return None if neither found

    Args:
        plugin_name: Plugin name requested by user (e.g., 'csv' or 'csv_')
        plugins: Dict of available plugins

    Returns:
        Resolved plugin name, or None if not found

    Examples:
        - User asks for 'csv', 'csv' exists → returns 'csv'
        - User asks for 'csv', only 'csv_' exists → returns 'csv_'
        - User asks for 'csv_', 'csv_' exists → returns 'csv_' (exact match)
    """
    # Try exact match first (highest priority)
    if plugin_name in plugins:
        return plugin_name

    # Try with underscore suffix as fallback
    fallback_name = f"{plugin_name}_"
    if fallback_name in plugins:
        return fallback_name

    # Not found
    return None


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
    except (AttributeError, OSError, io.UnsupportedOperation):
        # Not a real file handle (e.g., Click test runner StringIO)
        input_data = input_stream.read()
        text_mode = isinstance(input_data, str)
        return subprocess.PIPE, input_data, text_mode


def start_reader(
    source: str,
    plugin_dir: Path,
    cache_path: Optional[Path]
) -> subprocess.Popen:
    """Start a reader subprocess for a source file or URL.

    Returns a Popen object with stdout pipe that can be consumed downstream.

    Args:
        source: Path to source file or HTTP(S) URL
        plugin_dir: Plugin directory
        cache_path: Cache file path

    Returns:
        subprocess.Popen with stdout=PIPE (text mode)

    Raises:
        PipelineError: If plugin not found
    """
    # Check UV availability
    _check_uv_available()

    # Check if source is a profile reference
    headers_json = None
    if source.startswith("@"):
        try:
            url, headers = resolve_profile_reference(source)
            source = url  # Replace with resolved URL
            headers_json = json.dumps(headers)
        except HTTPProfileError as e:
            raise PipelineError(f"Profile error: {e}")

    # Load plugins and find reader
    plugins, registry = _load_plugins_and_registry(plugin_dir, cache_path)

    # Check if source is a URL (HTTP protocol plugin)
    is_url = source.startswith(("http://", "https://"))

    if is_url:
        # For binary format URLs, match by extension to get format plugin (e.g., xlsx_)
        # For text formats, use http_ plugin
        if _is_binary_format_url(source):
            from urllib.parse import urlparse
            ext = Path(urlparse(source).path).suffix.lower()
            plugin_name = registry.match(f"file{ext}")
            if not plugin_name:
                raise PipelineError(f"No plugin found for {ext} format")
        else:
            plugin_name = registry.match(source)
            if not plugin_name:
                raise PipelineError(f"No plugin found for {source}")
    else:
        # For local files, match normally
        plugin_name = registry.match(source)
        if not plugin_name:
            raise PipelineError(f"No plugin found for {source}")

    plugin = plugins[plugin_name]

    if is_url:
        if _is_binary_format_url(source):
            # Use curl to stream raw bytes directly to format plugin
            # curl streams bytes → format plugin buffers (unavoidable) → streams NDJSON out
            curl_proc = subprocess.Popen(
                ["curl", "-sL", source],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False  # Binary mode
            )

            # Pipe curl output to format plugin (e.g., xlsx_)
            proc = subprocess.Popen(
                ["uv", "run", "--script", plugin.path, "--mode", "read"],
                stdin=curl_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True  # Output is NDJSON (text)
            )
            # Close curl's stdout in parent to enable SIGPIPE
            curl_proc.stdout.close()
            # Attach curl process so caller can check/cleanup
            proc._jn_curl = curl_proc
            proc._jn_infile = None
        else:
            # Text/JSON formats: use http_ plugin for smart parsing
            cmd = ["uv", "run", "--script", plugin.path, "--mode", "read"]

            # Add headers from profile if available
            if headers_json:
                cmd.extend(["--headers", headers_json])

            cmd.append(source)

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # No file to attach
            proc._jn_infile = None
    else:
        # For files, open and pass as stdin
        infile = open(source)
        proc = subprocess.Popen(
            ["uv", "run", "--script", plugin.path, "--mode", "read"],
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
    """Read a source file or URL and output NDJSON to stream.

    Args:
        source: Path to source file or HTTP(S) URL
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

    # Close input file if it exists (URLs don't have one)
    if proc._jn_infile is not None:
        proc._jn_infile.close()

    # Wait for curl subprocess if it exists (binary format downloads)
    if hasattr(proc, '_jn_curl') and proc._jn_curl is not None:
        proc._jn_curl.wait()
        if proc._jn_curl.returncode != 0:
            curl_error = proc._jn_curl.stderr.read()
            raise PipelineError(f"Download error: {curl_error.decode('utf-8')}")

    if proc.returncode != 0:
        error_msg = proc.stderr.read()
        raise PipelineError(f"Reader error: {error_msg}")


def write_destination(
    dest: str,
    plugin_dir: Path,
    cache_path: Optional[Path],
    input_stream: TextIO = sys.stdin,
    plugin_name: Optional[str] = None,
    plugin_config: Optional[Dict] = None
) -> None:
    """Read NDJSON from stream and write to destination file or stdout.

    Args:
        dest: Path to destination file, or '-'/'stdout' for stdout
        plugin_dir: Plugin directory
        cache_path: Cache file path
        input_stream: Where to read input (default: stdin)
        plugin_name: Optional explicit plugin name (overrides registry matching)
        plugin_config: Optional config dict to pass to plugin

    Raises:
        PipelineError: If plugin not found or execution fails
    """
    # Check UV availability
    _check_uv_available()

    # Load plugins
    plugins, registry = _load_plugins_and_registry(plugin_dir, cache_path)

    # Resolve plugin
    if plugin_name:
        # Explicit plugin specified - try exact match, then fallback to underscore suffix
        resolved_name = _resolve_plugin_name(plugin_name, plugins)
        if not resolved_name:
            raise PipelineError(
                f"Plugin '{plugin_name}' not found. "
                f"Available plugins: {', '.join(sorted(plugins.keys()))}"
            )
        plugin = plugins[resolved_name]
    else:
        # Auto-detect from destination
        matched_name = registry.match(dest)
        if not matched_name:
            raise PipelineError(f"No plugin found for {dest}")
        plugin = plugins[matched_name]

    # Check if writing to stdout
    write_to_stdout = dest in ("-", "stdout")

    # Build command with config options
    cmd = ["uv", "run", "--script", plugin.path, "--mode", "write"]

    # Add plugin-specific config args
    if plugin_config:
        for key, value in plugin_config.items():
            cmd.extend([f"--{key}", str(value)])

    # Prepare stdin
    stdin_source, input_data, text_mode = _prepare_stdin_for_subprocess(input_stream)

    if write_to_stdout:
        # Write to stdout
        proc = subprocess.Popen(
            cmd,
            stdin=stdin_source,
            stdout=sys.stdout,
            stderr=subprocess.PIPE,
            text=text_mode,
        )
    else:
        # Write to file
        with open(dest, "w") as outfile:
            proc = subprocess.Popen(
                cmd,
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
            return

    # For stdout case
    if input_data is not None:
        proc.stdin.write(input_data)  # type: ignore[union-attr]
        proc.stdin.close()  # type: ignore[union-attr]

    proc.wait()

    if proc.returncode != 0:
        err = proc.stderr.read()
        if text_mode:
            pass  # Already text
        elif isinstance(err, bytes):
            err = err.decode()
        raise PipelineError(f"Writer error: {err}")


def convert(
    source: str,
    dest: str,
    plugin_dir: Path,
    cache_path: Optional[Path]
) -> None:
    """Convert source file or URL to destination format.

    Two-stage pipeline: read → write with automatic backpressure.

    Args:
        source: Path to source file or HTTP(S) URL
        dest: Path to destination file
        plugin_dir: Plugin directory
        cache_path: Cache file path

    Raises:
        PipelineError: If plugin not found or execution fails
    """
    # Check UV availability
    _check_uv_available()

    # Check if source is a profile reference
    headers_json = None
    if source.startswith("@"):
        try:
            url, headers = resolve_profile_reference(source)
            source = url  # Replace with resolved URL
            headers_json = json.dumps(headers)
        except HTTPProfileError as e:
            raise PipelineError(f"Profile error: {e}")

    # Load plugins
    plugins, registry = _load_plugins_and_registry(plugin_dir, cache_path)

    # Check if source is a URL
    is_url = source.startswith(("http://", "https://"))

    # Resolve reader - for URLs with binary formats, match by extension
    if is_url and _is_binary_format_url(source):
        from urllib.parse import urlparse
        ext = Path(urlparse(source).path).suffix.lower()
        reader_name = registry.match(f"file{ext}")
        if not reader_name:
            raise PipelineError(f"No plugin found for {ext} format")
    else:
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
    with open(dest, "w") as outfile:
        curl_proc = None  # Track curl subprocess for cleanup
        if is_url and _is_binary_format_url(source):
            # Use curl to stream raw bytes to format plugin
            curl_proc = subprocess.Popen(
                ["curl", "-sL", source],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False  # Binary mode
            )

            reader = subprocess.Popen(
                ["uv", "run", "--script", reader_plugin.path, "--mode", "read"],
                stdin=curl_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Close curl's stdout in parent for SIGPIPE
            curl_proc.stdout.close()
        elif is_url:
            # Text formats: use http_ plugin
            cmd = ["uv", "run", "--script", reader_plugin.path, "--mode", "read"]

            # Add headers from profile if available
            if headers_json:
                cmd.extend(["--headers", headers_json])

            cmd.append(source)

            reader = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        else:
            # For files, open and pass as stdin
            infile = open(source)
            reader = subprocess.Popen(
                ["uv", "run", "--script", reader_plugin.path, "--mode", "read"],
                stdin=infile,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        # Start writer using UV to respect PEP 723 dependencies
        writer = subprocess.Popen(
            ["uv", "run", "--script", writer_plugin.path, "--mode", "write"],
            stdin=reader.stdout,
            stdout=outfile,
            stderr=subprocess.PIPE,
        )

        # Close reader stdout in parent (critical for SIGPIPE backpressure)
        reader.stdout.close()

        # Wait for both processes
        writer.wait()
        reader.wait()

        # Wait for curl subprocess if it exists
        if curl_proc is not None:
            curl_proc.wait()
            if curl_proc.returncode != 0:
                curl_error = curl_proc.stderr.read()
                raise PipelineError(f"Download error: {curl_error.decode('utf-8')}")

        # Close input file if it exists (URLs don't have one)
        if not is_url:
            infile.close()

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
    params: Optional[Dict[str, str]] = None,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout
) -> None:
    """Filter NDJSON stream using jq expression or profile.

    Args:
        query: jq expression or @profile/name reference
        plugin_dir: Plugin directory
        cache_path: Cache file path
        params: Optional parameters for profile substitution (e.g., {"row": "product"})
        input_stream: Where to read input (default: stdin)
        output_stream: Where to write output (default: stdout)

    Raises:
        PipelineError: If jq plugin not found or execution fails

    Examples:
        # Direct query
        filter_stream(".", plugin_dir, cache_path)

        # Profile with parameters
        filter_stream("@analytics/pivot", plugin_dir, cache_path,
                     params={"row": "product", "col": "month"})
    """
    # Check dependencies
    _check_uv_available()
    _check_jq_available()

    # Resolve profile if query is a reference
    if query.startswith("@"):
        try:
            # Use generic profile resolution - works for any plugin
            query = resolve_profile(query, plugin_name="jq_", params=params or {})
        except ProfileError as e:
            raise PipelineError(str(e))

    # Load plugins
    plugins, _ = _load_plugins_and_registry(plugin_dir, cache_path)

    # Find jq filter plugin
    if "jq_" not in plugins:
        raise PipelineError("jq filter plugin not found")

    plugin = plugins["jq_"]

    # Execute filter - pass query as argument (not --query flag)
    # Plugin is now simple: just takes query and runs jq
    stdin_source, input_data, _ = _prepare_stdin_for_subprocess(input_stream)

    proc = subprocess.Popen(
        ["uv", "run", "--script", plugin.path, query],
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
