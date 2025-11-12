"""Put command - write NDJSON to file."""

import sys

import click

from ...addressing import AddressResolutionError, parse_address
from ...context import pass_context
from ...core.pipeline import PipelineError, write_destination


@click.command()
@click.argument("output_file")
@click.option(
    "--plugin",
    help="Explicitly specify plugin to use (e.g., 'table', 'csv', 'json'). "
    "DEPRECATED: Use format override syntax instead: -~table or file~format",
)
@click.option(
    "--tablefmt",
    default="simple",
    help="Table format for table plugin. "
    "DEPRECATED: Use query string syntax instead: -~table?tablefmt=grid",
)
@pass_context
def put(ctx, output_file, plugin, tablefmt):
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

        # Legacy syntax (deprecated)
        jn cat data.csv | jn put --plugin table -
        jn cat data.csv | jn put --plugin table --tablefmt grid stdout
    """
    try:
        # Parse address using new addressability system
        addr = parse_address(output_file)

        # Handle legacy --plugin flag
        if plugin:
            click.echo(
                "Warning: --plugin flag is deprecated. Use format override syntax instead: "
                f"-~{plugin} or output.txt~{plugin}",
                err=True,
            )
            # Override format with plugin flag
            addr.format_override = plugin

        # Handle legacy --tablefmt flag
        if tablefmt != "simple":
            click.echo(
                "Warning: --tablefmt flag is deprecated. Use query string syntax instead: "
                f"-~table?tablefmt={tablefmt}",
                err=True,
            )
            # Merge tablefmt into parameters
            addr.parameters["tablefmt"] = tablefmt

        # Build plugin config from address parameters
        plugin_config = None
        if addr.parameters:
            plugin_config = addr.parameters

        # Determine plugin name (from format override or None for auto-detect)
        plugin_name = addr.format_override if addr.format_override else None

        # Use original write_destination function
        write_destination(
            addr.base,  # Use base address (without format/params)
            ctx.plugin_dir,
            ctx.cache_path,
            input_stream=sys.stdin,
            plugin_name=plugin_name,
            plugin_config=plugin_config,
        )
    except ValueError as e:
        # Address parsing error
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
    except AddressResolutionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
