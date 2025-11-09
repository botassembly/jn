"""Shell driver: spawn processes with shell=True (requires --unsafe-shell)."""

import subprocess
from typing import Dict, Optional

from ..models import Completed


def spawn_shell(
    cmd: str,
    *,
    stdin: Optional[bytes] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    unsafe: bool = False,
) -> Completed:
    """Execute a shell command (requires unsafe=True for safety)."""
    if not unsafe:
        raise RuntimeError("shell driver requires --unsafe-shell flag")

    import os

    final_env = None if env is None else {**os.environ, **env}
    result = subprocess.run(
        cmd,
        shell=True,
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
