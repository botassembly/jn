"""CLI commands: jn new source <driver> - create sources."""

from pathlib import Path
from typing import List, Optional

import typer

from ...config import get_config, parse_key_value_pairs
from ...service.new import add_source

app = typer.Typer(help="Create a new source")


@app.command()
def exec(
    name: str,
    argv: List[str] = typer.Option(
        ...,
        "--argv",
        help="Command arguments",
    ),
    env: List[str] = typer.Option(
        [],
        "--env",
        help="Environment variable (K=V)",
    ),
    cwd: Optional[str] = typer.Option(
        None,
        "--cwd",
        help="Working directory",
    ),
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Create a new exec source."""
    config = get_config(jn)
    env_dict = parse_key_value_pairs(env) if env else None

    add_source(
        config=config,
        jn_path=jn,
        name=name,
        driver="exec",
        argv=argv,
        env=env_dict,
        cwd=cwd,
    )

    typer.echo(f"Created source '{name}' with driver 'exec'")


@app.command()
def shell(
    name: str,
    cmd: str = typer.Option(
        ...,
        "--cmd",
        help="Shell command",
    ),
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Create a new shell source."""
    config = get_config(jn)

    add_source(
        config=config,
        jn_path=jn,
        name=name,
        driver="shell",
        cmd=cmd,
    )

    typer.echo(f"Created source '{name}' with driver 'shell'")


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
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Create a new curl source."""
    config = get_config(jn)

    add_source(
        config=config,
        jn_path=jn,
        name=name,
        driver="curl",
        url=url,
        method=method,
    )

    typer.echo(f"Created source '{name}' with driver 'curl'")


@app.command()
def file(
    name: str,
    path: str = typer.Option(
        ...,
        "--path",
        help="File path",
    ),
    jn: Optional[Path] = typer.Option(
        None,
        help="Path to jn.json config file",
    ),
) -> None:
    """Create a new file source."""
    config = get_config(jn)

    add_source(
        config=config,
        jn_path=jn,
        name=name,
        driver="file",
        path=path,
    )

    typer.echo(f"Created source '{name}' with driver 'file'")
