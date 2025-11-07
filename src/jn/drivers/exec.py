"""Exec driver: spawn processes with argv (no shell)."""

import subprocess
from typing import Dict, Optional

from ..models import Completed


def spawn_exec(
    argv: list[str],
    *,
    stdin: Optional[bytes] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> Completed:
    """Execute a command with argv (no shell)."""
    import os

    final_env = None if env is None else {**os.environ, **env}
    result = subprocess.run(
        argv,
        input=stdin,
        capture_output=True,
        check=False,
        cwd=cwd,
        env=final_env,
    )
    return Completed(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
