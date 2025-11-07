"""CLI command: explain pipeline."""

import typer

from jn import ConfigPath, ConfigPathType, config

from . import app


@app.command()
def explain(
    pipeline: str,
    jn: ConfigPathType = ConfigPath,
    show_commands: bool = typer.Option(
        False,
        "--show-commands",
        help="Show command details (argv/cmd)",
    ),
    show_env: bool = typer.Option(
        False,
        "--show-env",
        help="Show environment variables",
    ),
) -> None:
    """Show the resolved plan for a pipeline without executing it."""
    config.set_config_path(jn)

    plan = config.explain_pipeline(
        pipeline,
        show_commands=show_commands,
        show_env=show_env,
    )

    typer.echo(plan.model_dump_json(indent=2, exclude_none=True))
