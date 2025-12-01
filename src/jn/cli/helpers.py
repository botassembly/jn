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


def build_subprocess_env_for_coverage(home_dir=None) -> dict:
    """Shim to keep CLI code stable; implementation lives in process_utils."""
    from ..process_utils import build_subprocess_env_for_coverage as _impl

    return _impl(home_dir=home_dir)
