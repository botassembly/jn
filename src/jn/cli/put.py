"""CLI command: jn put - write NDJSON to file in various formats.

The put command is the counterpart to cat - where cat reads files and outputs NDJSON,
put reads NDJSON and writes files.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from jn.writers import write_csv, write_json, write_ndjson

from . import app


def detect_output_format(filepath: str) -> str:
    """Detect output format from file extension.

    Args:
        filepath: Output file path

    Returns:
        Format name: csv, tsv, psv, json, ndjson
    """

    ext = Path(filepath).suffix.lower()

    format_map = {
        ".csv": "csv",
        ".tsv": "tsv",
        ".psv": "psv",
        ".json": "json",
        ".jsonl": "ndjson",
        ".ndjson": "ndjson",
    }

    return format_map.get(ext, "json")  # Default to JSON


def read_ndjson_from_stdin():
    """Read NDJSON records from stdin.

    Yields:
        Parsed JSON objects (dicts)
    """

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as e:
            typer.echo(f"Error: Invalid JSON on line: {line[:50]}...", err=True)
            typer.echo(f"  {e}", err=True)
            raise typer.Exit(1)


@app.command()
def put(
    output_file: str = typer.Argument(..., help="Output file path (use '-' for stdout)"),
    format: Optional[str] = typer.Option(None, "--format", help="Output format: csv, tsv, psv, json, ndjson"),
    header: bool = typer.Option(True, "--header/--no-header", help="Include header row (CSV only)"),
    delimiter: str = typer.Option(",", "--delimiter", help="Field delimiter (CSV)"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON"),
    overwrite: bool = typer.Option(True, "--overwrite/--no-overwrite", help="Overwrite existing file"),
    append: bool = typer.Option(False, "--append", help="Append to existing file"),
) -> None:
    """Write NDJSON from stdin to file in specified format.

    Examples:
      # Auto-detect format from extension
      jn cat data.csv | jq 'select(.amount > 100)' | jn put filtered.csv

      # Format conversion
      jn cat data.csv | jn put data.json

      # Write to stdout
      jn cat data.csv | jn put - --format csv

      # Append to existing file
      jn cat new-data.csv | jn put existing.json --append

    Supported formats:
      - csv: Comma-separated values (with header)
      - tsv: Tab-separated values
      - psv: Pipe-separated values
      - json: JSON array (buffered, not streaming)
      - ndjson: Newline-delimited JSON (streaming)
    """

    # Handle stdout
    if output_file == "-":
        if not format:
            typer.echo("Error: --format is required when writing to stdout", err=True)
            raise typer.Exit(1)
        output_path = None
    else:
        output_path = Path(output_file)

        # Check if file exists
        if output_path.exists() and not overwrite and not append:
            typer.echo(
                f"Error: File {output_file} already exists. Use --overwrite or --append",
                err=True,
            )
            raise typer.Exit(1)

    # Detect format
    if format is None:
        format = detect_output_format(output_file)

    # Read NDJSON from stdin
    records = read_ndjson_from_stdin()

    # Write based on format
    try:
        if format == "csv":
            write_csv(records, output_path, delimiter=delimiter, header=header, append=append)
        elif format == "tsv":
            write_csv(records, output_path, delimiter="\t", header=header, append=append)
        elif format == "psv":
            write_csv(records, output_path, delimiter="|", header=header, append=append)
        elif format == "json":
            if append:
                typer.echo("Warning: --append not supported for JSON format (array format)", err=True)
            write_json(records, output_path, pretty=pretty)
        elif format == "ndjson":
            write_ndjson(records, output_path, append=append)
        else:
            typer.echo(f"Error: Unsupported format: {format}", err=True)
            typer.echo("Supported formats: csv, tsv, psv, json, ndjson", err=True)
            raise typer.Exit(1)

    except Exception as e:
        typer.echo(f"Error writing output: {e}", err=True)
        raise typer.Exit(1)

    if output_path:
        typer.echo(f"Wrote {output_path}", err=True)
