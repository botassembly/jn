"""CLI command: explain pipeline."""

import json
from pathlib import Path
from typing import List, Optional

import typer

from ..config import get_config
from ..service.explain import explain_pipeline
from . import app


def _parse_params(param_list: List[str]) -> dict:
    """Parse --param k=v flags into a dictionary."""
    params = {}
    for p in param_list:
        if "=" not in p:
            raise ValueError(f"Invalid param format: {p} (expected k=v)")
        k, v = p.split("=", 1)
        params[k] = v
    return params


@app.command()
def explain(
    pipeline: str,
    param: List[str] = typer.Option(
        [], "--param", help="Parameter override (k=v)"
    ),
    show_commands: bool = typer.Option(
        False, "--show-commands", help="Show command details (argv/cmd)"
    ),
    show_env: bool = typer.Option(
        False, "--show-env", help="Show environment variables"
    ),
    jn: Optional[Path] = typer.Option(
        None, help="Path to jn.json config file"
    ),
) -> None:
    """Show the resolved plan for a pipeline without executing it."""
    try:
        project = get_config(jn)
        params = _parse_params(param)

        plan = explain_pipeline(
            project,
            pipeline,
            params=params,
            show_commands=show_commands,
            show_env=show_env,
        )

        typer.echo(json.dumps(plan, indent=2))

    except KeyError as e:
        typer.echo(f"Error: Pipeline not found - {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
