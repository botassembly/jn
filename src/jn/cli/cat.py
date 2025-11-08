"""Cat/head/tail commands for exploring sources without configuration."""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path
from typing import Iterator, Optional

# Import JC first
import jc
import typer

# Register our custom parsers with JC
# JC's plugin system expects parsers in jc.parsers namespace
from jn.jcparsers import generic_s, psv_s, toml_s, tsv_s, xml_s, yaml_s

sys.modules["jc.parsers.tsv_s"] = tsv_s
sys.modules["jc.parsers.psv_s"] = psv_s
sys.modules["jc.parsers.generic_s"] = generic_s
sys.modules["jc.parsers.yaml_s"] = yaml_s
sys.modules["jc.parsers.toml_s"] = toml_s
sys.modules["jc.parsers.xml_s"] = xml_s

from jn.cli import app
from jn.drivers import spawn_curl, spawn_exec
from jn.exceptions import JnError


def _is_url(source: str) -> bool:
    """Check if source is a URL pattern."""
    return source.startswith(
        ("http://", "https://", "ftp://", "ftps://", "s3://")
    )


def _detect_file_parser(path: str) -> Optional[str]:
    """Detect JC parser from file extension.

    Returns:
        Parser name (e.g., 'csv_s', 'tsv_s', 'yaml_s') or None for non-delimited files
    """
    ext = Path(path).suffix.lower()
    parser_map = {
        ".csv": "csv_s",
        ".tsv": "tsv_s",
        ".psv": "psv_s",
        ".yaml": "yaml_s",
        ".yml": "yaml_s",
        ".toml": "toml_s",
        ".xml": "xml_s",
    }
    return parser_map.get(ext)


def _is_jc_command(command: str) -> bool:
    """Check if command is in JC's parser registry."""
    try:
        return command in jc.parser_mod_list()
    except Exception:
        return False


def _detect_source_type(
    source: str, args: list[str]
) -> tuple[str, Optional[str], list[str]]:
    """Auto-detect driver and parser from source pattern.

    Returns:
        (driver, parser, full_args)

    Priority:
        1. URL pattern → curl driver
        2. File exists → file driver + extension-based parser
        3. Known jc command → exec driver + jc parser name
        4. Unknown command → exec driver + generic_s parser
    """
    # 1. Check for URL
    if _is_url(source):
        return ("curl", None, [source])

    # 2. Check if file exists
    path = Path(source)
    if path.exists() and path.is_file():
        parser = _detect_file_parser(source)
        return ("file", parser, [source])

    # 3. Check if command is in jc registry
    if _is_jc_command(source):
        return ("exec", source, [source] + args)

    # 4. Fallback: unknown command with generic parser
    return ("exec", "generic_s", [source] + args)


def _execute_source(
    driver: str,
    parser: Optional[str],
    args: list[str],
) -> Iterator[bytes]:
    """Execute source and return byte stream.

    Args:
        driver: Driver type (file, curl, exec)
        parser: Optional JC parser name
        args: Arguments (file path, URL, or command argv)

    Yields:
        Byte chunks from source
    """
    if driver == "curl":
        # Execute curl request
        url = args[0]
        result = spawn_curl(
            method="GET",
            url=url,
            headers={},
            body=None,
            timeout=30,
            follow_redirects=True,
            retry=0,
            retry_delay=2,
            fail_on_error=True,
        )
        if result.returncode != 0:
            raise JnError("source", url, result.returncode, result.stderr.decode("utf-8"))
        yield result.stdout

    elif driver == "file":
        # Read file and optionally apply JC parser
        file_path = Path(args[0]).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {args[0]}")

        if parser:
            # Parse file with JC streaming parser
            with open(file_path, encoding="utf-8") as f:
                for item in jc.parse(parser, f):
                    yield json.dumps(item, ensure_ascii=False).encode("utf-8") + b"\n"
        else:
            # Stream raw file
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk

    elif driver == "exec":
        # Execute command
        if parser and parser != "generic_s":
            # Use JC for known parsers
            argv = ["jc", f"--{parser.replace('_', '-')}", *args]
        else:
            # Run command directly
            argv = args

        result = spawn_exec(argv, env=None, cwd=None)
        if result.returncode != 0:
            raise JnError("source", " ".join(argv), result.returncode, result.stderr.decode("utf-8"))

        # If using generic parser, parse output
        if parser == "generic_s":
            # Parse stdout lines with generic parser
            lines = result.stdout.decode("utf-8").splitlines()
            command = args[0]
            cmd_args = args[1:] if len(args) > 1 else []

            for item in jc.parse("generic_s", lines):
                item["command"] = command
                item["args"] = cmd_args
                yield json.dumps(item, ensure_ascii=False).encode("utf-8") + b"\n"
        else:
            yield result.stdout

    else:
        raise ValueError(f"Unsupported driver: {driver}")


@app.command()
def cat(
    source: str = typer.Argument(..., help="Source: URL, file path, or command"),
    source_args: Optional[list[str]] = typer.Argument(
        None, help="Arguments for the source (if command)"
    ),
    driver: Optional[str] = typer.Option(
        None, "--driver", help="Force specific driver (file, curl, exec)"
    ),
    parser: Optional[str] = typer.Option(
        None, "--parser", help="Force specific JC parser"
    ),
) -> None:
    """Output source data as JSON (auto-detects driver and parser).

    Examples:
        jn cat data.csv
        jn cat https://api.github.com/users/octocat
        jn cat dig example.com
        jn cat ps aux
        jn cat --driver exec --parser ls ls -la
    """
    args = source_args or []

    # Auto-detect or use explicit driver/parser
    detected_driver, detected_parser, full_args = _detect_source_type(source, args)
    final_driver = driver or detected_driver
    final_parser = parser or detected_parser

    # Execute source and stream output
    try:
        for chunk in _execute_source(final_driver, final_parser, full_args):
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def head(
    source: str = typer.Argument(..., help="Source: URL, file path, or command"),
    source_args: Optional[list[str]] = typer.Argument(
        None, help="Arguments for the source (if command)"
    ),
    n: int = typer.Option(10, "-n", help="Number of lines to output"),
    driver: Optional[str] = typer.Option(
        None, "--driver", help="Force specific driver (file, curl, exec)"
    ),
    parser: Optional[str] = typer.Option(
        None, "--parser", help="Force specific JC parser"
    ),
) -> None:
    """Output first N records from source.

    Examples:
        jn head data.csv
        jn head -n 5 https://api.github.com/users/octocat/repos
        jn head -n 20 ps aux
    """
    args = source_args or []

    # Auto-detect or use explicit driver/parser
    detected_driver, detected_parser, full_args = _detect_source_type(source, args)
    final_driver = driver or detected_driver
    final_parser = parser or detected_parser

    # Execute source and output first N lines
    try:
        count = 0
        for chunk in _execute_source(final_driver, final_parser, full_args):
            if count >= n:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            count += 1

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def tail(
    source: str = typer.Argument(..., help="Source: URL, file path, or command"),
    source_args: Optional[list[str]] = typer.Argument(
        None, help="Arguments for the source (if command)"
    ),
    n: int = typer.Option(10, "-n", help="Number of lines to output"),
    driver: Optional[str] = typer.Option(
        None, "--driver", help="Force specific driver (file, curl, exec)"
    ),
    parser: Optional[str] = typer.Option(
        None, "--parser", help="Force specific JC parser"
    ),
) -> None:
    """Output last N records from source.

    Examples:
        jn tail data.csv
        jn tail -n 5 /var/log/syslog
        jn tail -n 20 netstat -an
    """
    args = source_args or []

    # Auto-detect or use explicit driver/parser
    detected_driver, detected_parser, full_args = _detect_source_type(source, args)
    final_driver = driver or detected_driver
    final_parser = parser or detected_parser

    # Execute source and buffer last N lines
    try:
        buffer: deque[bytes] = deque(maxlen=n)
        for chunk in _execute_source(final_driver, final_parser, full_args):
            buffer.append(chunk)

        # Output buffered lines
        for chunk in buffer:
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
