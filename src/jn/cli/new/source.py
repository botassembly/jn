"""CLI commands: jn new source <driver> - create sources."""

import typer

from jn import config

from .. import ConfigPath

app = typer.Typer(help="Create a new source")


@app.command()
def exec(
    name: str,
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
    jn: ConfigPath = None,
) -> None:
    """Create a new exec source."""
    config.set_config_path(jn)
    env_dict = config.parse_key_value_pairs(env) if env else None

    result = config.add_source(
        name,
        "exec",
        argv=argv,
        env=env_dict,
        cwd=cwd,
    )

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created source '{result.name}' with driver '{result.driver}'")


@app.command()
def shell(
    name: str,
    cmd: str = typer.Option(
        ...,
        "--cmd",
        help="Shell command",
    ),
    jn: ConfigPath = None,
) -> None:
    """Create a new shell source."""
    config.set_config_path(jn)

    result = config.add_source(name, "shell", cmd=cmd)

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created source '{result.name}' with driver '{result.driver}'")


@app.command()
def curl(
    name: str,
    url: str = typer.Option(
        ...,
        "--url",
        help="URL",
    ),
    method: str = typer.Option(
        "GET",
        "--method",
        help="HTTP method",
    ),
    jn: ConfigPath = None,
) -> None:
    """Create a new curl source."""
    config.set_config_path(jn)

    result = config.add_source(name, "curl", url=url, method=method)

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created source '{result.name}' with driver '{result.driver}'")


@app.command()
def file(
    name: str,
    path: str = typer.Option(
        ...,
        "--path",
        help="File path",
    ),
    jn: ConfigPath = None,
) -> None:
    """Create a new file source."""
    config.set_config_path(jn)

    result = config.add_source(name, "file", path=path)

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created source '{result.name}' with driver '{result.driver}'")
