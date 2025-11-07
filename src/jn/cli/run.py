"""CLI command: jn run - execute a pipeline."""

import sys
from typing import List, Optional

import typer

from jn import ConfigPath, ConfigPathType, config

from . import app


@app.command()
def run(
    pipeline: str,
    jn: ConfigPathType = ConfigPath,
    param: Optional[List[str]] = typer.Option(
        None, "--param", help="Pipeline parameters (k=v format)"
    ),
) -> None:
    """Execute a pipeline (source → converters → target)."""
    try:
        config.set_config_path(jn)
        params = config.parse_key_value_pairs(param or [])
        output = config.run_pipeline(pipeline, params=params)
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
