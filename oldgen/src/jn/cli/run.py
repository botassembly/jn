"""CLI command: jn run - execute a filter on NDJSON input.

Simplified architecture: Filters replace pipelines.
Filters are jq transformations that read NDJSON from stdin and write NDJSON to stdout.
"""

import shutil
import subprocess
import sys

import typer

from jn import ConfigPath, ConfigPathType, config

from . import app


@app.command()
def run(
    filter_name: str = typer.Argument(..., help="Filter name from registry"),
    jn: ConfigPathType = ConfigPath,
) -> None:
    """Execute a named filter on NDJSON input.

    Reads NDJSON from stdin, applies the filter's jq query, writes NDJSON to stdout.

    Examples:
      # Use filter from registry
      jn cat data.csv | jn run high-value | jn put output.json

      # Chain multiple filters
      jn cat data.csv | jn run filter1 | jn run filter2 | jn put output.csv
    """

    config.set_config_path(jn)

    # Get filter from registry
    filter_obj = config.get_filter(filter_name)
    if not filter_obj:
        typer.echo(
            f"Error: Filter '{filter_name}' not found in registry", err=True
        )
        raise typer.Exit(1)

    # Execute jq with the filter's query
    jq_path = shutil.which("jq")
    if not jq_path:
        typer.echo("Error: jq not found. Please install jq.", err=True)
        raise typer.Exit(1)

    try:
        subprocess.run(  # noqa: S603
            [jq_path, "-c", filter_obj.query],
            stdin=sys.stdin.buffer,
            stdout=sys.stdout.buffer,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        typer.echo(f"Error executing filter: {e.stderr.decode()}", err=True)
        raise typer.Exit(e.returncode)
