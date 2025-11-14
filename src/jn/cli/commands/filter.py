"""Filter command - apply jq expressions."""

import io
import subprocess
import sys

import click

from ...addressing import parse_address
from ...context import pass_context
from ...process_utils import popen_with_validation
from ...profiles.resolver import ProfileError, resolve_profile
from ..helpers import check_jq_available, check_uv_available


@click.command()
@click.argument("query")
@pass_context
def filter(ctx, query):
    """Filter NDJSON using jq expression or profile.

    QUERY can be either:
    - A jq expression: '.age > 25'
    - A profile reference: '@analytics/pivot?row=product&col=month'

    Supports addressability syntax for profiles: @profile/component[?parameters]

    Examples:
        # Direct jq expression
        jn cat data.csv | jn filter '.age > 25'

        # Profile with query string parameters
        jn cat data.csv | jn filter '@analytics/pivot?row=product&col=month'
    """
    try:
        check_jq_available()
        check_uv_available()

        # If query starts with @, it's a profile or plugin reference
        if query.startswith("@"):
            # Parse as address to extract parameters
            addr = parse_address(query)

            # Resolve profile to get actual jq query
            try:
                query = resolve_profile(
                    addr.base, plugin_name="jq_", params=addr.parameters
                )
            except ProfileError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)

        # Find jq plugin
        from ...plugins.discovery import get_cached_plugins_with_fallback

        plugins = get_cached_plugins_with_fallback(
            ctx.plugin_dir, ctx.cache_path
        )

        if "jq_" not in plugins:
            click.echo("Error: jq filter plugin not found", err=True)
            sys.exit(1)

        plugin = plugins["jq_"]

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

        # Execute filter - pass query as argument
        proc = popen_with_validation(
            ["uv", "run", "--script", plugin.path, query],
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
