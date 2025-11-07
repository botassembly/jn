"""CLI command: jn run - execute a pipeline."""

import sys

import typer

from jn import ConfigPath, ConfigPathType, config

from . import app


@app.command()
def run(
    pipeline: str,
    jn: ConfigPathType = ConfigPath,
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
