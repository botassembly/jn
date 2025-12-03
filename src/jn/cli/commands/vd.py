"""VisiData integration command - open NDJSON in VisiData."""

import json
import shutil
import subprocess
import sys
from contextlib import ExitStack

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
    help="Pre-filter with ZQ expression before viewing",
)
@click.pass_obj
def vd(ctx: JNContext, source: str, filter_expr: str) -> None:
    """Open NDJSON data in VisiData for interactive exploration.

    VisiData is a powerful terminal spreadsheet for exploring and arranging
    tabular data. It supports sorting, filtering, aggregation, and much more.

    Requires VisiData to be installed: uv tool install visidata

    \b
    Examples:
        # View from stdin
        jn cat data.csv | jn vd

        # View source directly
        jn vd data.json
        jn vd https://api.com/data~json

        # With pre-filtering
        jn vd data.csv --filter '.age > 30'

        # Explore large datasets with filtering
        jn head -n 1000 huge_file.csv | jn vd

    \b
    VisiData Quick Reference:
        q       Quit
        j/k     Move down/up
        h/l     Move left/right
        /       Search
        [       Sort ascending
        ]       Sort descending
        Shift+F Frequency table for column
        .       Select row
        g.      Select all matching rows
        "       Open selected rows as new sheet

    For full VisiData documentation: https://visidata.org/man/
    """
    # Check if visidata is available
    vd_path = shutil.which("vd") or shutil.which("visidata")
    if not vd_path:
        click.echo(
            "Error: VisiData not found. Install with: uv tool install visidata",
            err=True,
        )
        sys.exit(1)

    # Discover plugins
    plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)

    # VisiData command to receive NDJSON from stdin
    vd_cmd = [vd_path, "-f", "jsonl", "-"]

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

        # Add configuration parameters from resolved address
        for key, value in resolved.config.items():
            if isinstance(value, bool):
                if value:
                    cat_cmd.append(f"--{key}")
                else:
                    cat_cmd.extend([f"--{key}", "false"])
            else:
                cat_cmd.extend([f"--{key}", str(value)])

        # Add URL and headers if this is a protocol plugin
        if resolved.url:
            if resolved.headers:
                cat_cmd.extend(["--headers", json.dumps(resolved.headers)])
            cat_cmd.append(resolved.url)

        # Phase 2: filter (optional) - use built-in ZQ filter
        if filter_expr:
            filter_cmd = [
                sys.executable,
                "-m",
                "jn.cli.main",
                "filter",
                filter_expr,
            ]
        else:
            filter_cmd = None

        # Execute pipeline
        with ExitStack() as stack:
            try:
                # Start cat process
                if resolved.url:
                    cat_proc = popen_with_validation(
                        cat_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                else:
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
                    vd_stdin = filter_proc.stdout
                    filter_proc.stdout = None
                else:
                    vd_stdin = cat_proc.stdout
                    cat_proc.stdout = None

                # Start VisiData process
                vd_proc = popen_with_validation(
                    vd_cmd, stdin=vd_stdin, stderr=sys.stderr
                )

                # Wait for VisiData to complete
                vd_proc.wait()

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

                sys.exit(vd_proc.returncode)

            except KeyboardInterrupt:
                if "cat_proc" in locals():
                    cat_proc.terminate()
                if "filter_proc" in locals():
                    filter_proc.terminate()
                if "vd_proc" in locals():
                    vd_proc.terminate()
                sys.exit(130)
            except Exception as e:
                click.echo(f"Error running VisiData pipeline: {e}", err=True)
                sys.exit(1)

    else:
        # Read from stdin - pipe directly to VisiData
        try:
            vd_proc = popen_with_validation(vd_cmd, stdin=sys.stdin)
            vd_proc.wait()
            sys.exit(vd_proc.returncode)
        except KeyboardInterrupt:
            vd_proc.terminate()
            sys.exit(130)
        except Exception as e:
            click.echo(f"Error running VisiData: {e}", err=True)
            sys.exit(1)
