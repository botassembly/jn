"""CLI command: jn run - execute a pipeline."""

import sys
from typing import List, Optional

import typer

from jn import ConfigPath, ConfigPathType, config

from . import app


def _parse_params(param_list: List[str]) -> dict[str, str]:
    """Parse --param k=v arguments into a dict."""
    params = {}
    for param in param_list:
        if "=" not in param:
            raise ValueError(f"Invalid param format: {param} (expected k=v)")
        key, value = param.split("=", 1)
        params[key] = value
    return params


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
        params = _parse_params(param or [])
        output = config.run_pipeline(pipeline, params=params)
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
