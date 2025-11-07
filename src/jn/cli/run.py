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
    env: Optional[List[str]] = typer.Option(
        None, "--env", help="Environment variable overrides (K=V format)"
    ),
    unsafe_shell: bool = typer.Option(
        False,
        "--unsafe-shell",
        help="Allow shell driver execution (security risk)",
    ),
) -> None:
    """Execute a pipeline (source → converters → target)."""
    try:
        config.set_config_path(jn)
        params = config.parse_key_value_pairs(param or [])
        env_overrides = config.parse_key_value_pairs(env or [])
        output = config.run_pipeline(
            pipeline,
            params=params,
            env=env_overrides,
            unsafe_shell=unsafe_shell,
        )
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
