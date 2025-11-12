"""CLI helper utilities shared across commands."""

import shutil
import sys
import os
from pathlib import Path

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


def _repo_root() -> Path:
    """Locate repository root by searching for sitecustomize.py above this file."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "sitecustomize.py").exists():
            return parent
    # Fallback to current working directory
    return Path.cwd()


def build_subprocess_env_for_coverage() -> dict:
    """Return an env dict that enables coverage in subprocesses.

    - If COVERAGE_PROCESS_START is set, ensure sitecustomize.py is importable by
      prepending the repo root to PYTHONPATH.
    - Force coverage data files to land in repo root so combine finds them.
    """
    env = os.environ.copy()

    if env.get("COVERAGE_PROCESS_START"):
        root = _repo_root()
        py_path = env.get("PYTHONPATH", "")
        root_str = str(root)
        if py_path:
            if root_str not in py_path.split(os.pathsep):
                env["PYTHONPATH"] = root_str + os.pathsep + py_path
        else:
            env["PYTHONPATH"] = root_str

        # Centralize coverage data output
        env.setdefault("COVERAGE_RCFILE", str(root / ".coveragerc"))
        env.setdefault("COVERAGE_FILE", str(root / ".coverage"))

    return env
