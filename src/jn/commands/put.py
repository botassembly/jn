"""Put command - write NDJSON to file."""

import sys
import subprocess
import click
from ..cli import pass_context
from ..discovery import get_cached_plugins
from ..registry import build_registry


@click.command()
@click.argument('output_file')
@pass_context
def put(ctx, output_file):
    """Read NDJSON from stdin, write to file.

    Example:
        jn cat data.csv | jn put output.json
    """
    # Load plugins
    plugins = get_cached_plugins(ctx.plugin_dir, ctx.cache_path)
    registry = build_registry(plugins)

    # Resolve output plugin
    output_plugin_name = registry.match(output_file)
    if not output_plugin_name:
        click.echo(f"Error: No plugin found for {output_file}", err=True)
        sys.exit(1)

    output_plugin = plugins[output_plugin_name]

    # Write from stdin to file
    with open(output_file, 'w') as outfile:
        writer = subprocess.Popen(
            [sys.executable, output_plugin.path, '--mode', 'write'],
            stdout=outfile,
            stderr=subprocess.PIPE
        )

        writer.wait()

        if writer.returncode != 0:
            error_msg = writer.stderr.read().decode()
            click.echo(f"Error: {error_msg}", err=True)
            sys.exit(1)
