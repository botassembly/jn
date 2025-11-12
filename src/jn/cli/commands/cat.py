"""Cat command - read files and output NDJSON."""

import sys

import click

from ...addressing import parse_address
from ...context import pass_context
from ...core.pipeline import PipelineError, read_source


@click.command()
@click.argument("input_file")
@pass_context
def cat(ctx, input_file):
    """Read file and output NDJSON to stdout.

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # Basic files
        jn cat data.csv                        # Auto-detect format
        jn cat data.txt~csv                    # Force CSV format
        jn cat data.csv~csv?delimiter=;        # CSV with semicolon delimiter

        # Stdin
        cat data.csv | jn cat "-~csv"          # Read stdin as CSV
        cat data.tsv | jn cat "-~csv?delimiter=%09"  # Tab-delimited (%09 = tab)

        # Profiles with query strings
        jn cat "@api/source?gene=BRAF&limit=100"
        jn cat "@gmail/inbox?from=boss&is=unread"

        # Protocol URLs
        jn cat "http://example.com/data.json"
        jn cat "s3://bucket/data.csv"
    """
    try:
        # Parse address
        addr = parse_address(input_file)

        # Extract parameters for profile resolution
        params = addr.parameters if addr.parameters else None

        # Read source
        read_source(
            addr.base,
            ctx.plugin_dir,
            ctx.cache_path,
            output_stream=sys.stdout,
            params=params,
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
