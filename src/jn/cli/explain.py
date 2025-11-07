"""CLI command: explain pipeline."""

from pathlib import Path
from typing import List, Optional

import typer

from ..config import get_config, parse_key_value_pairs
from ..service.explain import explain_pipeline
from . import app


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
    config = get_config(jn)
    params = parse_key_value_pairs(param) if param else {}

    plan = explain_pipeline(
        config,
        pipeline,
        params=params,
        show_commands=show_commands,
        show_env=show_env,
    )

    typer.echo(plan.model_dump_json(indent=2, exclude_none=True))
