"""CLI commands: create new project items."""

from pathlib import Path
from typing import List, Literal, Optional

import typer

from ..service.new import add_converter, add_pipeline, add_source, add_target
from . import app

# Create a subcommand group for "new"
new_app = typer.Typer(help="Create new project items")
app.add_typer(new_app, name="new")


def _parse_env_vars(env_list: List[str]) -> dict:
    """Parse --env K=V flags into a dictionary."""
    env = {}
    for e in env_list:
        if "=" not in e:
            raise ValueError(f"Invalid env format: {e} (expected K=V)")
        k, v = e.split("=", 1)
        env[k] = v
    return env


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
    try:
        env_dict = _parse_env_vars(env) if env else None

        jn_path = jn or Path("jn.json")

        add_source(
            jn_path=jn_path,
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

    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


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
    try:
        env_dict = _parse_env_vars(env) if env else None

        jn_path = jn or Path("jn.json")

        add_target(
            jn_path=jn_path,
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

    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


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
    try:
        jn_path = jn or Path("jn.json")

        add_converter(
            jn_path=jn_path,
            name=name,
            expr=expr,
            file=file,
            raw=raw,
            modules=modules,
        )

        typer.echo(f"Created converter '{name}'")

    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


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
    try:
        jn_path = jn or Path("jn.json")

        add_pipeline(
            jn_path=jn_path,
            name=name,
            steps=steps,
        )

        typer.echo(f"Created pipeline '{name}' with {len(steps)} steps")

    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
