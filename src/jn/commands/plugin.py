"""Plugin management commands."""

import subprocess
import sys

import click

from ..context import pass_context
from ..discovery import get_cached_plugins


@click.group(
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True)
)
def plugin():
    """Manage and inspect plugins."""
    pass


@plugin.command(
    name="call",
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED, required=True)
@pass_context
def call(ctx, args):
    """Call a plugin directly by name.

    NOTE: Currently has issues with Click option parsing when passing flags to plugins.
    Use plugin executables directly for now:
        python src/jn/plugins/formats/csv_.py --mode read < input.csv

    Examples (not yet working with options):
        jn plugin call csv_ --mode read < input.csv
        jn plugin call jq_ --query '.name'
    """
    # First arg is the plugin name, rest are plugin arguments
    if not args:
        click.echo("Error: Plugin name required", err=True)
        sys.exit(1)

    name = args[0]
    plugin_args = args[1:]

    # Load plugins from cache
    plugins = get_cached_plugins(ctx.plugin_dir, ctx.cache_path)

    # Find plugin by name
    if name not in plugins:
        click.echo(f"Error: Plugin '{name}' not found", err=True)
        click.echo(f"Available plugins: {', '.join(plugins.keys())}", err=True)
        sys.exit(1)

    plugin = plugins[name]

    # Build command
    cmd = [sys.executable, plugin.path] + list(plugin_args)

    # Execute plugin (inherit stdin/stdout/stderr)
    proc = subprocess.Popen(cmd)
    proc.wait()

    sys.exit(proc.returncode)


@plugin.command()
@pass_context
def list(ctx):
    """List all available plugins."""
    plugins = get_cached_plugins(ctx.plugin_dir, ctx.cache_path)

    if not plugins:
        click.echo("No plugins found")
        return

    for name, meta in sorted(plugins.items()):
        matches = ", ".join(meta.matches) if meta.matches else "no patterns"
        click.echo(f"{name:20s} {matches}")
