"""Interactive NDJSON viewer command."""

import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path

import click

from ...addressing.parser import parse_address
from ...addressing.resolver import AddressResolver
from ...context import JNContext
from ...plugins.discovery import get_cached_plugins_with_fallback
from ...process_utils import popen_with_validation


@click.command()
@click.argument("source", required=False)
@click.option(
    "--filter",
    "-f",
    "filter_expr",
    help="Pre-filter with jq expression before viewing",
)
@click.option(
    "--depth", type=int, default=2, help="Initial tree expansion depth"
)
@click.option(
    "--start-at", type=int, default=0, help="Start at record N (0-based)"
)
@click.pass_obj
def view(
    ctx: JNContext, source: str, filter_expr: str, depth: int, start_at: int
) -> None:
    """View NDJSON data interactively.

    Opens a TUI viewer for exploring NDJSON records one at a time.

    \b
    Examples:
        # View from stdin
        jn cat data.json | jn view

        # View source directly
        jn view data.json
        jn view https://api.com/data~json

        # With pre-filtering
        jn view data.json --filter '.age > 30'

        # Start at specific record
        jn view data.json --start-at 100 --depth 3
    """
    # Discover plugins
    plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)

    # Find viewer plugin
    viewer_plugin = None
    for plugin in plugins.values():
        # Check if this is the json_viewer plugin
        plugin_path = (
            Path(plugin.path) if isinstance(plugin.path, str) else plugin.path
        )
        if "viewer" in plugin_path.name.lower():
            viewer_plugin = plugin
            break

    if not viewer_plugin:
        click.echo("Error: Viewer plugin not found", err=True)
        sys.exit(1)

    # Build pipeline based on whether source is provided
    if source:
        # Parse source address
        try:
            addr = parse_address(source)
        except Exception as e:
            click.echo(f"Error parsing source address: {e}", err=True)
            sys.exit(1)

        # Resolve source using AddressResolver
        try:
            resolver = AddressResolver(
                ctx.plugin_dir, ctx.cache_path, ctx.home
            )
            resolved = resolver.resolve(addr, mode="read")
        except Exception as e:
            click.echo(f"Error resolving source address: {e}", err=True)
            sys.exit(1)

        # Build command pipeline
        # Phase 1: cat source
        cat_cmd = [
            "uv",
            "run",
            "--script",
            str(resolved.plugin_path),
            "--mode",
            "read",
        ]

        # Add URL argument if this is a protocol plugin
        if resolved.url:
            cat_cmd.append(resolved.url)

        # Phase 2: filter (optional)
        if filter_expr:
            # Find jq filter plugin
            filter_plugin = None
            for plugin in plugins.values():
                plugin_path = (
                    Path(plugin.path)
                    if isinstance(plugin.path, str)
                    else plugin.path
                )
                if "jq" in plugin_path.name.lower():
                    filter_plugin = plugin
                    break

            if not filter_plugin:
                click.echo(
                    "Warning: jq filter plugin not found, skipping filter",
                    err=True,
                )
                filter_cmd = None
            else:
                filter_cmd = [
                    "uv",
                    "run",
                    "--script",
                    str(filter_plugin.path),
                    "--mode",
                    "filter",
                    "--expr",
                    filter_expr,
                ]
        else:
            filter_cmd = None

        # Phase 3: viewer
        viewer_cmd = [
            "uv",
            "run",
            "--script",
            str(viewer_plugin.path),
            "--mode",
            "write",
            "--depth",
            str(depth),
            "--start-at",
            str(start_at),
        ]

        # Execute pipeline
        with ExitStack() as stack:
            try:
                # Start cat process (keep as binary pipes - each script handles encoding)
                if resolved.url:
                    # For protocols, no stdin needed (URL is argument)
                    cat_proc = popen_with_validation(
                        cat_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                else:
                    # For files, open and pass as stdin
                    if addr.base != "-":
                        infile = stack.enter_context(open(addr.base, "rb"))
                    else:
                        infile = sys.stdin.buffer
                    cat_proc = popen_with_validation(
                        cat_cmd,
                        stdin=infile,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )

                # Start filter process if needed
                if filter_cmd:
                    filter_proc = popen_with_validation(
                        filter_cmd,
                        stdin=cat_proc.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    cat_proc.stdout.close()  # Allow cat to receive SIGPIPE
                    viewer_stdin = filter_proc.stdout
                    filter_proc.stdout = None  # Will be closed by viewer
                else:
                    viewer_stdin = cat_proc.stdout
                    cat_proc.stdout = None  # Will be closed by viewer

                # Start viewer process
                viewer_proc = popen_with_validation(
                    viewer_cmd, stdin=viewer_stdin, stderr=sys.stderr
                )

                # Wait for viewer to complete
                # Note: viewer_stdin will be closed automatically when viewer exits
                viewer_proc.wait()

                # Check for errors
                if filter_cmd:
                    filter_proc.wait()
                    if filter_proc.returncode != 0:
                        stderr = (
                            filter_proc.stderr.read()
                            if filter_proc.stderr
                            else b""
                        )
                        click.echo(
                            f"Filter error: {stderr.decode()}", err=True
                        )

                cat_proc.wait()
                if cat_proc.returncode != 0:
                    stderr = cat_proc.stderr.read() if cat_proc.stderr else b""
                    click.echo(f"Source error: {stderr.decode()}", err=True)

                # Exit with viewer's return code
                sys.exit(viewer_proc.returncode)

            except KeyboardInterrupt:
                # Clean shutdown on Ctrl+C
                if "cat_proc" in locals():
                    cat_proc.terminate()
                if "filter_proc" in locals():
                    filter_proc.terminate()
                if "viewer_proc" in locals():
                    viewer_proc.terminate()
                sys.exit(130)  # Standard Unix Ctrl+C exit code
            except Exception as e:
                click.echo(f"Error running viewer pipeline: {e}", err=True)
                sys.exit(1)

    else:
        # Read from stdin (existing behavior)
        viewer_cmd = [
            "uv",
            "run",
            "--script",
            str(viewer_plugin.path),
            "--mode",
            "write",
            "--depth",
            str(depth),
            "--start-at",
            str(start_at),
        ]

        try:
            viewer_proc = popen_with_validation(viewer_cmd, stdin=sys.stdin)
            viewer_proc.wait()
            sys.exit(viewer_proc.returncode)
        except KeyboardInterrupt:
            viewer_proc.terminate()
            sys.exit(130)
        except Exception as e:
            click.echo(f"Error running viewer: {e}", err=True)
            sys.exit(1)
