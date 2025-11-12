"""CLI helper utilities shared across commands."""

import shutil
import sys

import click


def check_uv_available() -> None:
    """Check if UV is available and exit with error if not.

    Raises:
        SystemExit: If UV is not found
    """
    if not shutil.which("uv"):
        click.echo(
            "Error: UV is required to run JN plugins\n"
            "Install: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            "Or: pip install uv\n"
            "More info: https://docs.astral.sh/uv/",
            err=True,
        )
        sys.exit(1)


def check_jq_available() -> None:
    """Check if jq is available and exit with error if not.

    Raises:
        SystemExit: If jq is not found
    """
    if not shutil.which("jq"):
        click.echo(
            "Error: jq command not found\n"
            "Install from: https://jqlang.github.io/jq/\n"
            "  macOS: brew install jq\n"
            "  Ubuntu/Debian: apt-get install jq\n"
            "  Fedora: dnf install jq",
            err=True,
        )
        sys.exit(1)
