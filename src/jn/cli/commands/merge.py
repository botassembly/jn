"""Merge command - combine multiple data sources into a single stream."""

import json
import subprocess
import sys
from typing import Iterator, Tuple

import click

from ...context import pass_context
from ...process_utils import popen_with_validation
from ..helpers import check_uv_available


def _parse_source_spec(spec: str) -> Tuple[str, str]:
    """Parse 'source:label=Label' into (source, label).

    Args:
        spec: Source specification, optionally with :label=X suffix

    Returns:
        Tuple of (source_address, label)

    Examples:
        "data.csv:label=MyData" -> ("data.csv", "MyData")
        "data.csv" -> ("data.csv", "data.csv")
        "@api/users:label=Users" -> ("@api/users", "Users")
    """
    if ":label=" in spec:
        # Find the last occurrence of :label= to handle URLs with colons
        idx = spec.rfind(":label=")
        source = spec[:idx]
        label = spec[idx + 7:]  # len(":label=") == 7
        return source, label
    return spec, spec  # Use source as default label


def _stream_source(source: str, label: str) -> Iterator[dict]:
    """Execute source via jn cat and yield records with metadata.

    Args:
        source: Data source address (file, URL, profile)
        label: Label to inject into records

    Yields:
        Records from source with _label and _source metadata
    """
    # Execute jn cat for this source
    proc = popen_with_validation(
        [sys.executable, "-m", "jn.cli.main", "cat", source],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Stream and transform each record
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                # Inject metadata
                record["_label"] = label
                record["_source"] = source
                yield record
            except json.JSONDecodeError:
                # Skip invalid JSON lines
                click.echo(f"Warning: Skipping invalid JSON: {line[:50]}...", err=True)
                continue

        proc.wait()

        if proc.returncode != 0:
            err = proc.stderr.read()
            click.echo(f"Warning: Source '{source}' failed: {err}", err=True)

    finally:
        # Ensure process is cleaned up
        if proc.poll() is None:
            proc.terminate()
            proc.wait()


@click.command()
@click.argument("sources", nargs=-1, required=True)
@click.option(
    "--fail-fast/--no-fail-fast",
    default=False,
    help="Stop on first source error instead of continuing.",
)
@pass_context
def merge(ctx, sources, fail_fast):
    """Merge multiple data sources into a single NDJSON stream.

    Each source can have a label suffix using the :label=X syntax.
    The label and source are injected into each record as _label and _source.

    Use this for comparative analysis across multiple data sources.

    Examples:
        # Compare two CSV files
        jn merge "east.csv:label=East" "west.csv:label=West"

        # Compare profile queries
        jn merge "@sales/q1:label=Q1" "@sales/q2:label=Q2"

        # Merge API endpoints
        jn merge "http://api/users" "http://api/admins:label=Admin"

        # Clinical cohort comparison
        jn merge \\
          "@genie/treatment?regimen=FOLFOX:label=FOLFOX" \\
          "@genie/treatment?regimen=FOLFIRI:label=FOLFIRI"

    Output format:
        {"id": 1, "value": 100, "_label": "East", "_source": "east.csv"}
        {"id": 2, "value": 200, "_label": "West", "_source": "west.csv"}
    """
    try:
        check_uv_available()

        for source_spec in sources:
            source, label = _parse_source_spec(source_spec)

            try:
                for record in _stream_source(source, label):
                    print(json.dumps(record), flush=True)
            except Exception as e:
                if fail_fast:
                    click.echo(f"Error: Failed to process source '{source}': {e}", err=True)
                    sys.exit(1)
                else:
                    click.echo(f"Warning: Skipping source '{source}': {e}", err=True)
                    continue

    except KeyboardInterrupt:
        sys.exit(130)
