"""Subprocess execution utilities.

Harvested from oldgen/src/jn/drivers/ with simplifications.
"""

import subprocess
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ProcessResult:
    """Result of subprocess execution."""
    returncode: int
    stdout: bytes
    stderr: bytes


def run_command(
    argv: list[str],
    *,
    stdin: Optional[bytes] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None
) -> ProcessResult:
    """Execute command with argv (no shell).

    Harvested from oldgen exec.py spawn_exec()

    Args:
        argv: Command and arguments
        stdin: Optional input to pass to process
        env: Additional environment variables (merged with os.environ)
        cwd: Working directory
        timeout: Kill process after N seconds

    Returns:
        ProcessResult with returncode, stdout, stderr
    """
    import os

    final_env = None if env is None else {**os.environ, **env}

    result = subprocess.run(
        argv,
        input=stdin,
        capture_output=True,
        check=False,
        cwd=cwd,
        env=final_env,
        timeout=timeout
    )

    return ProcessResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr
    )


def run_http_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
    timeout: int = 30,
    follow_redirects: bool = True,
    fail_on_error: bool = True
) -> ProcessResult:
    """Execute HTTP request using curl.

    Harvested from oldgen curl.py spawn_curl() with simplifications.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        url: Full URL
        headers: HTTP headers
        body: Request body bytes
        timeout: Request timeout in seconds
        follow_redirects: Follow 3xx redirects
        fail_on_error: Fail on HTTP 4xx/5xx

    Returns:
        ProcessResult with response in stdout
    """
    argv = ["curl", "-sS"]  # Silent but show errors

    # Method
    if method != "GET":
        argv.extend(["-X", method])

    # Headers
    for key, value in (headers or {}).items():
        argv.extend(["-H", f"{key}: {value}"])

    # Body
    if body is not None:
        argv.extend(["--data-binary", "@-"])  # Read from stdin

    # Timeout
    argv.extend(["--max-time", str(timeout)])

    # Redirects
    if follow_redirects:
        argv.append("-L")

    # Fail on errors
    if fail_on_error:
        argv.append("-f")

    # URL
    argv.append(url)

    # Execute
    result = subprocess.run(
        argv,
        input=body,
        capture_output=True,
        check=False
    )

    return ProcessResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr
    )
