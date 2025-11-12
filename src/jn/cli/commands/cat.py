"""Cat command - read files and output NDJSON."""

import sys

import click

from ...addressing import AddressResolutionError, AddressResolver, parse_address
from ...context import pass_context
from ...core.pipeline import PipelineError, read_source


@click.command()
@click.argument("input_file")
@click.option(
    "--param",
    "-p",
    multiple=True,
    help="Profile parameter (format: key=value, can be used multiple times). "
    "DEPRECATED: Use query string syntax instead: @api/source?key=value",
)
@pass_context
def cat(ctx, input_file, param):
    """Read file and output NDJSON to stdout.

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # Basic files
        jn cat data.csv                        # Auto-detect format
        jn cat data.txt~csv                    # Force CSV format
        jn cat data.csv~csv?delimiter=;        # CSV with semicolon delimiter

        # Stdin/stdout
        cat data.csv | jn cat "-~csv"          # Read stdin as CSV
        cat data.tsv | jn cat "-~csv?delimiter=%09"  # Tab-delimited (%09 = tab)

        # Profiles with query strings
        jn cat "@api/source?gene=BRAF&limit=100"
        jn cat "@gmail/inbox?from=boss&is=unread"

        # Protocol URLs
        jn cat "http://example.com/data.json"
        jn cat "s3://bucket/data.csv"

        # Legacy -p syntax (deprecated, use query strings)
        jn cat @api/source -p gene=BRAF -p limit=100
    """
    try:
        # Parse address using new addressability system
        addr = parse_address(input_file)

        # Handle legacy -p parameters (merge with query string params)
        if param:
            click.echo(
                "Warning: -p flags are deprecated. Use query string syntax instead: "
                f"@api/source?key=value",
                err=True,
            )
            # Merge -p params into address parameters
            for p in param:
                if "=" not in p:
                    click.echo(
                        f"Error: Invalid parameter format '{p}'. Use: key=value",
                        err=True,
                    )
                    sys.exit(1)
                key, value = p.split("=", 1)
                # Legacy -p params override query string params
                addr.parameters[key] = value

        # For backward compatibility, also support old read_source path
        # Build params dict from address parameters
        params = addr.parameters if addr.parameters else None

        # Use original read_source function (no changes needed for now)
        # The addressability refactor can be completed incrementally
        read_source(
            addr.base,  # Use base address (without format/params)
            ctx.plugin_dir,
            ctx.cache_path,
            output_stream=sys.stdout,
            params=params,
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
