"""Curl driver: HTTP client using curl binary."""

import subprocess
from typing import Dict, Literal, Optional

from ..models import Completed


def spawn_curl(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Literal["stdin"] | str | None = None,
    stdin: Optional[bytes] = None,
    timeout: int = 30,
    follow_redirects: bool = True,
    retry: int = 0,
    retry_delay: int = 2,
    fail_on_error: bool = True,
) -> Completed:
    """Execute HTTP request using curl binary.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        url: Full URL including query params
        headers: HTTP headers dict
        body: "stdin" to read from stdin, str for literal body, None for no body
        stdin: Bytes to pass to stdin (for body="stdin")
        timeout: Request timeout in seconds
        follow_redirects: Follow 3xx redirects
        retry: Number of retry attempts (exponential backoff)
        retry_delay: Initial delay between retries (seconds)
        fail_on_error: Fail on HTTP 4xx/5xx status codes

    Returns:
        Completed with response body in stdout

    Notes:
        - For sources: method=GET, body=None, stdin=None
        - For targets: method=POST/PUT, body="stdin", stdin=<data>
        - Streaming: curl naturally streams via pipes (O(1) memory)
    """
    argv = ["curl", "-sS"]  # -s silent, -S show errors

    # HTTP method
    if method != "GET":
        argv.extend(["-X", method])

    # Headers
    for key, value in (headers or {}).items():
        argv.extend(["-H", f"{key}: {value}"])

    # Request body
    if body == "stdin":
        argv.extend(["--data-binary", "@-"])  # Read from stdin
    elif body is not None:
        argv.extend(["-d", body])  # Literal body

    # Timeout
    argv.extend(["--max-time", str(timeout)])

    # Follow redirects
    if follow_redirects:
        argv.append("-L")

    # Retry logic (curl handles exponential backoff)
    if retry > 0:
        argv.extend(["--retry", str(retry)])
        argv.extend(["--retry-delay", str(retry_delay)])

    # Fail on HTTP errors (4xx/5xx)
    if fail_on_error:
        argv.append("-f")  # --fail

    # URL (must be last positional arg)
    argv.append(url)

    # Execute
    result = subprocess.run(
        argv,
        input=stdin,
        capture_output=True,
        check=False,
    )

    return Completed(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


__all__ = ["spawn_curl"]
