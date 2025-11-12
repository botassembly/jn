"""Filter command - apply jq expressions."""

import io
import shutil
import subprocess
import sys

import click

from ...addressing import parse_address
from ...context import pass_context
from ...profiles.resolver import ProfileError, resolve_profile


@click.command()
@click.argument("query")
@click.option(
    "--param",
    "-p",
    multiple=True,
    help="Profile parameter (format: key=value, can be used multiple times). Deprecated: use query string syntax instead.",
)
@pass_context
def filter(ctx, query, param):
    """Filter NDJSON using jq expression or profile.

    QUERY can be either:
    - A jq expression: '.age > 25'
    - A profile reference: '@analytics/pivot?row=product&col=month'

    Supports addressability syntax for profiles: @profile/component[?parameters]

    Examples:
        # Direct jq expression
        jn cat data.csv | jn filter '.age > 25'

        # Profile with query string parameters (recommended)
        jn cat data.csv | jn filter '@analytics/pivot?row=product&col=month'

        # Profile with --param flags (deprecated but supported)
        jn cat data.csv | jn filter '@analytics/pivot' -p row=product -p col=month
    """
    try:
        # Check jq availability
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

        # Check UV availability
        if not shutil.which("uv"):
            click.echo(
                "Error: UV is required to run JN plugins\n"
                "Install: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
                "Or: pip install uv\n"
                "More info: https://docs.astral.sh/uv/",
                err=True,
            )
            sys.exit(1)

        # If query starts with @, it's a profile or plugin reference
        if query.startswith("@"):
            # Parse as address to extract parameters
            addr = parse_address(query)

            # Merge --param flags with query string parameters
            params = {}
            for p in param:
                if "=" not in p:
                    click.echo(
                        f"Error: Invalid parameter format '{p}'. Use: key=value",
                        err=True,
                    )
                    sys.exit(1)
                key, value = p.split("=", 1)
                params[key] = value

            # Query string parameters take precedence
            params.update(addr.parameters)

            # Resolve profile to get actual jq query
            try:
                query = resolve_profile(addr.base, plugin_name="jq_", params=params)
            except ProfileError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)

        # Find jq plugin
        from ...plugins.discovery import get_cached_plugins_with_fallback

        plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)

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
        proc = subprocess.Popen(
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
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
