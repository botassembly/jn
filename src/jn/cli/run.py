"""CLI command: jn run - execute a pipeline."""

import sys

import typer

from jn import config

from . import ConfigPath, app


@app.command()
def run(
    pipeline: str,
    jn: ConfigPath = None,
) -> None:
    """Execute a pipeline (source → converters → target)."""
    try:
        config.set_config_path(jn)
        output = config.run_pipeline(pipeline)
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
