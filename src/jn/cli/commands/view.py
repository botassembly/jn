"""View command - display NDJSON in interactive single-record viewer."""

import subprocess
import sys

import click

from ...context import pass_context
from ...process_utils import popen_with_validation
from ..helpers import build_subprocess_env_for_coverage, check_uv_available

JN_CLI = [sys.executable, "-m", "jn.cli.main"]


@click.command()
@click.argument("source", required=False)
@click.option(
    "--depth",
    type=int,
    default=2,
    help="Initial tree expansion depth (default: 2)",
)
@click.option(
    "--start-at",
    type=int,
    default=0,
    help="Start at record N (0-based index)",
)
@pass_context
def view(ctx, source, depth, start_at):
    """Display NDJSON in interactive single-record viewer.

    Opens a terminal UI for viewing JSON records one at a time with tree navigation.
    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # View from file
        jn view data.json

        # View from piped input
        jn cat data.csv | jn view
        jn cat http://api.com/data | jn filter '.active' | jn view

        # With options
        jn view data.json --depth 3 --start-at 10

    Navigation:
        n/p         - Next/previous record
        g/G         - First/last record
        Ctrl+D/U    - Jump forward/back 10 records
        :           - Go to specific record
        Space       - Toggle expand/collapse node
        e/c         - Expand/collapse all nodes
        q           - Quit viewer
        ?           - Show help

    Note:
        When passing addresses that start with '-', use '--' to stop
        option parsing before the argument (e.g., jn view -- "-~json").
    """
    try:
        check_uv_available()

        # Find json_viewer plugin
        from ...plugins.discovery import get_cached_plugins_with_fallback

        plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)

        if "json_viewer" not in plugins:
            click.echo("Error: json_viewer plugin not found", err=True)
            sys.exit(1)

        plugin = plugins["json_viewer"]

        # Build viewer command with options
        viewer_cmd = [
            "uv",
            "run",
            "--script",
            plugin.path,
            "--mode",
            "write",
        ]

        if depth != 2:
            viewer_cmd.extend(["--depth", str(depth)])

        if start_at != 0:
            viewer_cmd.extend(["--start-at", str(start_at)])

        if source:
            # Read from source address using cat, pipe to viewer
            cat_cmd = [*JN_CLI, "cat", source]
            stdin_source = (
                sys.stdin if source.startswith("-") else subprocess.DEVNULL
            )

            cat_proc = popen_with_validation(
                cat_cmd,
                stdin=stdin_source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=build_subprocess_env_for_coverage(),
            )

            # Pipe cat output to viewer
            # Note: viewer is a TUI app that needs direct terminal access
            # Don't redirect stdout/stderr - let it control the terminal
            viewer_proc = popen_with_validation(
                viewer_cmd,
                stdin=cat_proc.stdout,
                text=True,
            )

            # Close our handle so cat gets SIGPIPE if viewer exits
            if cat_proc.stdout:
                cat_proc.stdout.close()

            # Wait for viewer to exit (user quits)
            viewer_proc.wait()

            # Clean up cat process
            cat_proc.wait()

            if cat_proc.returncode != 0:
                if cat_proc.stderr:
                    error_msg = cat_proc.stderr.read()
                    click.echo(error_msg, err=True)
                sys.exit(1)

            if viewer_proc.returncode != 0:
                sys.exit(viewer_proc.returncode)

        else:
            # Read from stdin directly
            # Note: viewer is a TUI app that needs direct terminal access
            # Don't redirect stdout/stderr - let it control the terminal
            viewer_proc = popen_with_validation(
                viewer_cmd,
                stdin=sys.stdin,
                text=True,
            )

            viewer_proc.wait()

            if viewer_proc.returncode != 0:
                sys.exit(viewer_proc.returncode)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
