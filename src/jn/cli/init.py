"""CLI command: jn init - create a starter jn.json file."""

from pathlib import Path
from typing import Optional

import typer

from ..home import save_json


def register(app: typer.Typer) -> None:
    """Register the init command with the Typer app."""

    @app.command()
    def init(
        jn: Optional[str] = typer.Option(
            None, "--jn", help="Path to jn.json file"
        ),
        force: bool = typer.Option(
            False, "--force", help="Overwrite existing file"
        ),
    ) -> None:
        """Create a starter jn.json configuration file."""
        path = Path(jn) if jn else Path.cwd() / "jn.json"

        if path.exists() and not force:
            typer.echo(
                f"Error: {path} already exists. Use --force to overwrite.",
                err=True,
            )
            raise typer.Exit(code=1)

        starter_project = {
            "version": "0.1",
            "name": "demo",
            "sources": [
                {
                    "name": "echo.ndjson",
                    "driver": "exec",
                    "exec": {
                        "argv": [
                            "python",
                            "-c",
                            "import json; print(json.dumps({'x': 1})); print(json.dumps({'x': 2}))",
                        ]
                    },
                }
            ],
            "converters": [
                {"name": "pass", "engine": "jq", "jq": {"expr": "."}}
            ],
            "targets": [
                {
                    "name": "cat",
                    "driver": "exec",
                    "exec": {
                        "argv": [
                            "python",
                            "-c",
                            "import sys; print(sys.stdin.read(), end='')",
                        ]
                    },
                }
            ],
            "pipelines": [
                {
                    "name": "echo_to_cat",
                    "steps": [
                        {"type": "source", "ref": "echo.ndjson"},
                        {"type": "converter", "ref": "pass"},
                        {"type": "target", "ref": "cat"},
                    ],
                }
            ],
        }

        save_json(path, starter_project)
        typer.echo(f"Created {path}")
