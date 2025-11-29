"""Filter command - apply jq expressions."""

import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import click

from ...addressing import parse_address
from ...context import get_jn_home, pass_context
from ...process_utils import popen_with_validation
from ...profiles.resolver import (
    ProfileError,
    find_profile_path,
    resolve_profile,
)
from ..helpers import check_jq_available, check_uv_available


def find_zq_binary() -> str | None:
    """Find the ZQ binary.

    Resolution order:
    1. $JN_HOME/bin/zq (bundled with jn)
    2. zq/zig-out/bin/zq (development build in repo)
    3. zq in PATH (system install)

    Returns:
        Path to zq binary or None if not found
    """
    # 1. Check JN_HOME/bin/zq
    jn_home = get_jn_home()
    bundled = jn_home / "bin" / "zq"
    if bundled.exists() and os.access(bundled, os.X_OK):
        return str(bundled)

    # 2. Check development build in repo root
    # Walk up from jn module to find repo root
    current = Path(__file__).parent
    for _ in range(5):  # Max 5 levels up
        dev_build = current / "zq" / "zig-out" / "bin" / "zq"
        if dev_build.exists() and os.access(dev_build, os.X_OK):
            return str(dev_build)
        current = current.parent

    # 3. Check PATH
    path_zq = shutil.which("zq")
    if path_zq:
        return path_zq

    return None


# Patterns that ZQ supports (Sprint 01 features)
# Note: ZQ requires spaces around comparison operators (e.g., ".x > 10" not ".x>10")
ZQ_SUPPORTED_PATTERNS = [
    r"^\.$",  # Identity
    r"^\.[a-zA-Z_][a-zA-Z0-9_]*$",  # Simple field
    r"^\.[a-zA-Z_][a-zA-Z0-9_.]*$",  # Nested path
    r"^\.[a-zA-Z_][a-zA-Z0-9_]*\[\-?\d+\]$",  # Array index
    r"^\.\[\]$",  # Root iteration
    r"^\.[a-zA-Z_][a-zA-Z0-9_.]*\[\]$",  # Nested iteration
    # Select with spaced operators only (ZQ requires spaces around operators)
    r"^select\(\.[a-zA-Z_][a-zA-Z0-9_.]*\)$",  # select(.field) - truthy
    r"^select\(\.[a-zA-Z_][a-zA-Z0-9_.]* (>|<|>=|<=|==|!=) .+\)$",  # select(.x > N)
    r"^select\(.+ (and|or) .+\)$",  # select(.a and .b)
    r"^select\(not \..+\)$",  # select(not .field)
]


def zq_supports_expression(expr: str) -> bool:
    """Check if ZQ supports the given expression.

    ZQ supports a subset of jq for performance-critical operations:
    - Identity (.)
    - Field access (.field, .a.b.c)
    - Array indexing (.[0], .[-1])
    - Array iteration (.[], .items[])
    - Select with comparisons and boolean logic

    Returns:
        True if ZQ can handle this expression
    """
    expr = expr.strip()
    return any(re.match(pattern, expr) for pattern in ZQ_SUPPORTED_PATTERNS)


@click.command()
@click.argument("query")
@click.option(
    "--native-args/--no-native-args",
    default=False,
    help="Use jq native --arg binding instead of string substitution.",
)
@pass_context
def filter(ctx, query, native_args):
    """Filter NDJSON using jq expression or profile.

    QUERY can be either:
    - A jq expression: '.age > 25'
    - A profile reference: '@analytics/pivot?row=product&col=month'

    Supports addressability syntax for profiles: @profile/component[?parameters]

    Two parameter modes for profiles:
    - Default: String substitution ($param -> "value")
    - --native-args: Uses jq's native --arg binding (type-safe)

    Examples:
        # Direct jq expression
        jn cat data.csv | jn filter '.age > 25'

        # Profile with string substitution (default)
        jn cat data.csv | jn filter '@analytics/pivot?row=product&col=month'

        # Profile with native jq arguments
        jn cat data.csv | jn filter '@sales/by_region?region=East' --native-args

        # Force jq instead of ZQ
        JN_USE_JQ=1 jn cat data.csv | jn filter '.age > 25'
    """
    try:
        # Check if we should use ZQ for this expression
        zq_binary = find_zq_binary()
        use_zq_filter = (
            zq_binary is not None
            and not query.startswith("@")  # Profiles require jq
            and zq_supports_expression(query)
            and os.environ.get("JN_USE_JQ") != "1"
        )

        if use_zq_filter:
            # Use ZQ (fast path)
            cmd = [zq_binary, query]
        else:
            # Use jq (fallback for profiles and unsupported expressions)
            check_jq_available()
            check_uv_available()

            # Find jq plugin
            from ...plugins.discovery import get_cached_plugins_with_fallback

            plugins = get_cached_plugins_with_fallback(
                ctx.plugin_dir, ctx.cache_path
            )

            if "jq_" not in plugins:
                click.echo("Error: jq filter plugin not found", err=True)
                sys.exit(1)

            plugin = plugins["jq_"]

            # Build command based on mode
            if query.startswith("@"):
                # Parse as address to extract parameters
                addr = parse_address(query)

                if native_args and addr.parameters:
                    # Native argument mode: pass file path and --jq-arg flags
                    profile_path = find_profile_path(
                        addr.base, plugin_name="jq_"
                    )
                    if profile_path is None:
                        click.echo(
                            f"Error: Profile not found: {addr.base}", err=True
                        )
                        sys.exit(1)

                    cmd = [
                        "uv",
                        "run",
                        "--quiet",
                        "--script",
                        plugin.path,
                        str(profile_path),
                    ]

                    # Add --jq-arg flags for each parameter
                    for key, value in addr.parameters.items():
                        cmd.extend(["--jq-arg", key, str(value)])
                else:
                    # String substitution mode (default, backward compatible)
                    try:
                        resolved_query = resolve_profile(
                            addr.base,
                            plugin_name="jq_",
                            params=addr.parameters,
                        )
                    except ProfileError as e:
                        click.echo(f"Error: {e}", err=True)
                        sys.exit(1)

                    cmd = [
                        "uv",
                        "run",
                        "--quiet",
                        "--script",
                        plugin.path,
                        resolved_query,
                    ]
            else:
                # Direct jq expression
                cmd = ["uv", "run", "--quiet", "--script", plugin.path, query]

        # Prepare stdin for subprocess
        try:
            sys.stdin.fileno()
            stdin_source = sys.stdin
            input_data = None
            text_mode = True
        except (AttributeError, OSError, io.UnsupportedOperation):
            # Not a real file handle (e.g., Click test runner)
            input_data = sys.stdin.read()
            stdin_source = subprocess.PIPE
            text_mode = isinstance(input_data, str)

        # Execute filter
        proc = popen_with_validation(
            cmd,
            stdin=stdin_source,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text_mode,
        )

        if input_data is not None:
            proc.stdin.write(input_data)
            proc.stdin.close()

        # Stream output
        for line in proc.stdout:
            sys.stdout.write(line)

        proc.wait()

        if proc.returncode != 0:
            err = proc.stderr.read()
            click.echo(f"Error: Filter error: {err}", err=True)
            sys.exit(1)

    except ValueError as e:
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
