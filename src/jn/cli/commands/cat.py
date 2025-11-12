"""Cat command - read files and output NDJSON."""

import sys
from urllib.parse import parse_qs

import click

from ...context import pass_context
from ...core.pipeline import PipelineError, read_source


@click.command()
@click.argument("input_file")
@click.option(
    "--param",
    "-p",
    multiple=True,
    help="Profile parameter (format: key=value, can be used multiple times)",
)
@pass_context
def cat(ctx, input_file, param):
    """Read file and output NDJSON to stdout only.

    Examples:
        jn cat data.csv                        # Output NDJSON to stdout
        jn cat data.csv | jn put output.json   # Pipe to put for conversion
        jn cat "@api/source?gene=BRAF"         # HTTP source with query string
        jn cat @api/source -p gene=BRAF        # HTTP source with -p parameter
        jn cat "@gmail/inbox?from=boss"        # Gmail with query string
        jn run data.csv output.json            # Direct conversion (read→write)
    """
    try:
        # Parse query string from reference if present (e.g., @gmail/inbox?from=boss)
        params = {}
        source_ref = input_file

        if "?" in input_file and input_file.startswith("@"):
            # Split reference and query string
            source_ref, query_string = input_file.split("?", 1)
            # Parse query string
            parsed_params = parse_qs(query_string)
            for key, values in parsed_params.items():
                # Flatten single values
                params[key] = values[0] if len(values) == 1 else values

        # Parse -p parameters and merge (override query string)
        for p in param:
            if "=" not in p:
                click.echo(
                    f"Error: Invalid parameter format '{p}'. Use: key=value",
                    err=True,
                )
                sys.exit(1)
            key, value = p.split("=", 1)

            # Support multiple values for same key (becomes list)
            if key in params:
                if not isinstance(params[key], list):
                    params[key] = [params[key]]
                params[key].append(value)
            else:
                params[key] = value

        # Pass the current stdout so Click's runner can capture it
        read_source(
            source_ref,  # Use reference without query string
            ctx.plugin_dir,
            ctx.cache_path,
            output_stream=sys.stdout,
            params=params if params else None,
        )
    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
