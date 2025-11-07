"""CLI commands: create new project items."""

from pathlib import Path
from typing import List, Literal, Optional

import typer

from ..config import get_config, parse_key_value_pairs
from ..service.new import add_converter, add_pipeline, add_source, add_target
from . import app

# Create a subcommand group for "new"
new_app = typer.Typer(help="Create new project items")
app.add_typer(new_app, name="new")


@new_app.command()
def source(
    name: str,
    driver: Literal["exec", "shell", "curl", "file"],
    argv: Optional[List[str]] = typer.Option(
        None, "--argv", help="Command arguments (exec driver)"
    ),
    cmd: Optional[str] = typer.Option(None, "--cmd", help="Shell command"),
    url: Optional[str] = typer.Option(None, "--url", help="URL (curl driver)"),
    method: str = typer.Option(
        "GET", "--method", help="HTTP method (curl driver)"
    ),
    path: Optional[str] = typer.Option(
        None, "--path", help="File path (file driver)"
    ),
    env: List[str] = typer.Option(
        [], "--env", help="Environment variable (K=V)"
    ),
    cwd: Optional[str] = typer.Option(None, "--cwd", help="Working directory"),
    jn: Optional[Path] = typer.Option(
        None, help="Path to jn.json config file"
    ),
) -> None:
    """Create a new source."""
    env_dict = parse_key_value_pairs(env) if env else None
    config = get_config(jn)

    add_source(
        config=config,
        jn_path=jn,
        name=name,
        driver=driver,
        argv=argv,
        cmd=cmd,
        url=url,
        method=method,
        path=path,
        env=env_dict,
        cwd=cwd,
    )

    typer.echo(f"Created source '{name}' with driver '{driver}'")


@new_app.command()
def target(
    name: str,
    driver: Literal["exec", "shell", "curl", "file"],
    argv: Optional[List[str]] = typer.Option(
        None, "--argv", help="Command arguments (exec driver)"
    ),
    cmd: Optional[str] = typer.Option(None, "--cmd", help="Shell command"),
    url: Optional[str] = typer.Option(None, "--url", help="URL (curl driver)"),
    method: str = typer.Option(
        "POST", "--method", help="HTTP method (curl driver)"
    ),
    path: Optional[str] = typer.Option(
        None, "--path", help="File path (file driver)"
    ),
    env: List[str] = typer.Option(
        [], "--env", help="Environment variable (K=V)"
    ),
    cwd: Optional[str] = typer.Option(None, "--cwd", help="Working directory"),
    jn: Optional[Path] = typer.Option(
        None, help="Path to jn.json config file"
    ),
) -> None:
    """Create a new target."""
    env_dict = parse_key_value_pairs(env) if env else None
    config = get_config(jn)

    add_target(
        config=config,
        jn_path=jn,
        name=name,
        driver=driver,
        argv=argv,
        cmd=cmd,
        url=url,
        method=method,
        path=path,
        env=env_dict,
        cwd=cwd,
    )

    typer.echo(f"Created target '{name}' with driver '{driver}'")


@new_app.command()
def converter(
    name: str,
    expr: Optional[str] = typer.Option(
        None, "--expr", help="jq expression (inline)"
    ),
    file: Optional[str] = typer.Option(
        None, "--file", help="Path to jq filter file"
    ),
    raw: bool = typer.Option(False, "--raw", help="Output raw strings"),
    modules: Optional[str] = typer.Option(
        None, "--modules", help="Path to jq modules directory"
    ),
    jn: Optional[Path] = typer.Option(
        None, help="Path to jn.json config file"
    ),
) -> None:
    """Create a new jq converter."""
    config = get_config(jn)

    add_converter(
        config=config,
        jn_path=jn,
        name=name,
        expr=expr,
        file=file,
        raw=raw,
        modules=modules,
    )

    typer.echo(f"Created converter '{name}'")


@new_app.command()
def pipeline(
    name: str,
    steps: List[str] = typer.Option(
        ...,
        "--steps",
        help="Pipeline steps in format 'type:ref' (e.g., 'source:echo')",
    ),
    jn: Optional[Path] = typer.Option(
        None, help="Path to jn.json config file"
    ),
) -> None:
    """Create a new pipeline."""
    config = get_config(jn)

    add_pipeline(
        config=config,
        jn_path=jn,
        name=name,
        steps=steps,
    )

    typer.echo(f"Created pipeline '{name}' with {len(steps)} steps")
