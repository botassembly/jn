"""Cat command - read files and output NDJSON."""

import sys

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
        jn cat @api/source -p gene=BRAF        # HTTP source with parameters
        jn run data.csv output.json            # Direct conversion (read→write)
    """
    try:
        # Parse parameters into dict
        params = {}
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
            input_file,
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
