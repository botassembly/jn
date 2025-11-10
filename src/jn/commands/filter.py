"""Filter command - apply jq expressions."""

import subprocess
import sys

import click

from ..context import pass_context


@click.command()
@click.argument("query")
@pass_context
def filter(ctx, query):
    """Filter NDJSON using jq expression.

    Example:
        jn cat data.csv | jn filter '.age > 25'
    """
    # Find jq plugin
    jq_plugin = ctx.plugin_dir / "filters" / "jq_.py"

    if not jq_plugin.exists():
        click.echo("Error: jq filter plugin not found", err=True)
        sys.exit(1)

    # Run jq filter (inherit stdin/stdout)
    proc = subprocess.Popen(
        [sys.executable, str(jq_plugin), "--query", query],
        stderr=subprocess.PIPE,
    )

    proc.wait()

    if proc.returncode != 0:
        error_msg = proc.stderr.read().decode()
        click.echo(f"Filter error: {error_msg}", err=True)
        sys.exit(1)
