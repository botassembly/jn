"""CLI commands: jn new target <driver> - create targets."""

import typer

from jn import ConfigPath, ConfigPathType, config

app = typer.Typer(help="Create a new target")


@app.command()
def exec(
    name: str,
    jn: ConfigPathType = ConfigPath,
    argv: list[str] = typer.Option(
        ...,
        "--argv",
        help="Command arguments",
    ),
    env: list[str] = typer.Option(
        [],
        "--env",
        help="Environment variable (K=V)",
    ),
    cwd: str | None = typer.Option(
        None,
        "--cwd",
        help="Working directory",
    ),
) -> None:
    """Create a new exec target."""
    config.set_config_path(jn)
    env_dict = config.parse_key_value_pairs(env) if env else None

    result = config.add_target(
        name,
        "exec",
        argv=argv,
        env=env_dict,
        cwd=cwd,
    )

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created target '{result.name}' with driver '{result.driver}'")


@app.command()
def shell(
    name: str,
    jn: ConfigPathType = ConfigPath,
    cmd: str = typer.Option(
        ...,
        "--cmd",
        help="Shell command",
    ),
) -> None:
    """Create a new shell target."""
    config.set_config_path(jn)

    result = config.add_target(name, "shell", cmd=cmd)

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created target '{result.name}' with driver '{result.driver}'")


@app.command()
def curl(
    name: str,
    jn: ConfigPathType = ConfigPath,
    url: str = typer.Option(
        ...,
        "--url",
        help="URL",
    ),
    method: str = typer.Option(
        "POST",
        "--method",
        help="HTTP method",
    ),
) -> None:
    """Create a new curl target."""
    config.set_config_path(jn)

    result = config.add_target(name, "curl", url=url, method=method)

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created target '{result.name}' with driver '{result.driver}'")


@app.command()
def file(
    name: str,
    jn: ConfigPathType = ConfigPath,
    path: str = typer.Option(
        ...,
        "--path",
        help="File path",
    ),
) -> None:
    """Create a new file target."""
    config.set_config_path(jn)

    result = config.add_target(name, "file", path=path)

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created target '{result.name}' with driver '{result.driver}'")
