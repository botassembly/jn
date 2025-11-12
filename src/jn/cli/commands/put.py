"""Put command - write NDJSON to file."""

import sys

import click

from ...addressing import parse_address
from ...context import pass_context
from ...core.pipeline import PipelineError, write_destination


@click.command()
@click.argument("output_file")
@pass_context
def put(ctx, output_file):
    """Read NDJSON from stdin, write to file or stdout.

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # Basic files
        jn cat data.csv | jn put output.json          # Auto-detect format
        jn cat data.csv | jn put output.txt~json      # Force JSON format
        jn cat data.json | jn put output.json?indent=4  # Pretty JSON

        # Stdout with format override
        jn cat data.json | jn put "-~table"           # Simple table
        jn cat data.json | jn put "-~table.grid"      # Grid table (shorthand)
        jn cat data.json | jn put "-~json?indent=2"   # Pretty JSON to stdout

        # Table with parameters
        jn cat data.json | jn put "-~table?tablefmt=grid&maxcolwidths=20"
        jn cat data.json | jn put "-~table?tablefmt=markdown&showindex=true"

        # CSV with parameters
        jn cat data.json | jn put "output.csv?delimiter=;&header=false"
    """
    try:
        # Parse address
        addr = parse_address(output_file)

        # Build plugin config from parameters
        plugin_config = addr.parameters if addr.parameters else None

        # Determine plugin name from format override
        plugin_name = addr.format_override if addr.format_override else None

        # Write destination
        write_destination(
            addr.base,
            ctx.plugin_dir,
            ctx.cache_path,
            input_stream=sys.stdin,
            plugin_name=plugin_name,
            plugin_config=plugin_config,
        )
    except ValueError as e:
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
