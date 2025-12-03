"""Filter command - apply ZQ filter expressions."""

import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

from ...addressing import parse_address
from ...context import get_jn_home, pass_context
from ...process_utils import popen_with_validation
from ...profiles.resolver import ProfileError, resolve_profile


def find_zq_binary() -> str | None:
    """Find the ZQ binary, building from source if needed.

    Resolution order:
    1. $JN_HOME/bin/zq (bundled with jn)
    2. zq/zig-out/bin/zq (development build in repo)
    3. zq in PATH (system install)
    4. Build from source using zig_builder (on-demand compilation)

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

    # 4. Build from source (on-demand compilation via ziglang)
    try:
        from ...zig_builder import get_or_build_zq

        built_zq = get_or_build_zq()
        if built_zq:
            return str(built_zq)
    except ImportError:
        pass  # zig_builder not available

    return None


@click.command()
@click.argument("query")
@click.option(
    "-s",
    "--slurp",
    is_flag=True,
    default=False,
    help="Read entire input into array before filtering (zq -s mode). "
    "Enables aggregations like group_by, sort_by, unique. "
    "WARNING: Loads all data into memory.",
)
@pass_context
def filter(ctx, query, slurp):
    """Filter NDJSON using ZQ expressions or profiles.

    QUERY can be either:
    - A ZQ expression: 'select(.age > 25)'
    - A profile reference: '@sales/by_region?region=East'

    Profile Support:
    - Profiles are stored in profiles/zq/{namespace}/{name}.zq
    - Parameters are substituted: $param → "value"
    - Example: '@sales/by_region?region=East' resolves the profile
      and replaces $region with "East"

    Supported features:
    - Identity: .
    - Field access: .name, .a.b.c
    - Array indexing: .[0], .[-1], .[2:5]
    - Array iteration: .[], .items[]
    - Select: select(.x > 10), select(.a and .b)
    - Pipes: .x | .y, (.field | tonumber) > 10
    - Object construction: {a: .x, b: .y}
    - Arithmetic: .x + .y, .a * .b
    - Builtins: length, keys, values, type, tonumber, tostring
    - Array functions: first, last, sort, unique, reverse, flatten
    - Aggregations: add, min, max, group_by, sort_by, map
    - String functions: split, join, contains, startswith, endswith
    - Object functions: has, del, to_entries, from_entries
    - Optional access: .field?, .[0]?
    - Alternative: .x // .y

    Slurp mode (-s/--slurp):
    - Collects all input into an array before filtering
    - Enables aggregation: group_by, sort_by, unique, length
    - WARNING: Loads entire input into memory (not streaming)

    Examples:
        # Extract field
        jn cat data.csv | jn filter '.name'

        # Filter records
        jn cat data.csv | jn filter 'select(.age > 25)'

        # Complex filter with pipes
        jn cat data.csv | jn filter '.items[] | select(.active) | .name'

        # Using a profile
        jn cat sales.csv | jn filter '@sales/by_region?region=East'

        # Aggregation with slurp mode
        jn cat data.csv | jn filter -s 'group_by(.status) | map({status: .[0].status, count: length})'

        # Count total records
        jn cat data.csv | jn filter -s 'length'
    """
    # Find ZQ binary
    zq_binary = find_zq_binary()

    if zq_binary is None:
        click.echo("Error: ZQ filter engine not available.", err=True)
        click.echo("", err=True)
        click.echo("Options:", err=True)
        click.echo(
            "  1. Install Zig 0.15.2+ to build ZQ automatically:", err=True
        )
        click.echo("     https://ziglang.org/download/", err=True)
        click.echo("  2. Build ZQ manually:", err=True)
        click.echo("     make zq", err=True)
        sys.exit(1)

    # Resolve profile references
    resolved_query = query
    if query.startswith("@"):
        try:
            # Parse as address to extract parameters
            addr = parse_address(query)
            # Resolve profile with string substitution
            resolved_query = resolve_profile(
                addr.base,
                plugin_name="zq_",
                params=addr.parameters,
            )
        except ProfileError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except ValueError as e:
            click.echo(f"Error: Invalid profile syntax: {e}", err=True)
            sys.exit(1)

    # Build ZQ command
    cmd = [zq_binary]
    if slurp:
        cmd.append("-s")
    cmd.append(resolved_query)

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
        # ZQ already prints nice error messages, just forward them
        if err:
            click.echo(err.strip(), err=True)
        sys.exit(proc.returncode)
