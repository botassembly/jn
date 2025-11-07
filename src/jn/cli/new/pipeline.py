"""CLI command: jn new pipeline - create pipelines."""

import typer

from jn import ConfigPath, ConfigPathType, config

from . import new_app


@new_app.command()
def pipeline(
    name: str,
    jn: ConfigPathType = ConfigPath,
    source: str = typer.Option(
        ...,
        "--source",
        "-s",
        help="Source name",
    ),
    converter: list[str] = typer.Option(
        [],
        "--converter",
        "-c",
        help="Converter name(s) - can specify multiple",
    ),
    target: str = typer.Option(
        ...,
        "--target",
        "-t",
        help="Target name",
    ),
) -> None:
    """Create a new pipeline (source → converter(s) → target)."""
    config.set_config_path(jn)

    # Build steps in the simple format
    steps = [f"source:{source}"]
    steps.extend(f"converter:{c}" for c in converter)
    steps.append(f"target:{target}")

    result = config.add_pipeline(name, steps)

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(
        f"Created pipeline '{result.name}' with {len(result.steps)} steps"
    )
