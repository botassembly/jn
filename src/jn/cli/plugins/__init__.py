"""Plugin CLI commands - presentation layer only."""

import json
import sys

import click

from ...context import pass_context
from ...plugins.service import (
    call_plugin,
    find_plugin,
    list_plugins,
)


@click.group(invoke_without_command=True)
@click.pass_context
def plugin(ctx):
    """Manage and inspect plugins.

    If no subcommand is provided, defaults to 'list'.
    """
    if ctx.invoked_subcommand is None:
        # Default to list command
        ctx.invoke(list_cmd)


@plugin.command(name="list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@pass_context
def list_cmd(ctx, output_format):
    """List all available plugins."""
    plugins = list_plugins(ctx.plugin_dir, ctx.cache_path)

    if not plugins:
        click.echo("No plugins found")
        return

    if output_format == "json":
        # Machine-readable output
        output = {}
        for name, info in sorted(plugins.items()):
            output[name] = {
                "path": info.path,
                "type": info.plugin_type,
                "description": info.description,
                "methods": info.methods,
                "matches": info.matches,
            }
        click.echo(json.dumps(output, indent=2))
    else:
        # Human-readable output
        max_name_len = max(len(name) for name in plugins.keys())

        for name, info in sorted(plugins.items()):
            description = info.description
            if not description:
                # Fallback: show patterns
                description = f"Matches: {', '.join(info.matches[:2])}"
                if len(info.matches) > 2:
                    description += f" (+{len(info.matches) - 2} more)"

            click.echo(f"{name:{max_name_len}}  {description}")

        click.echo("\nUse 'jn plugin info <name>' for detailed information")


@plugin.command(name="info")
@click.argument("plugin_name")
@pass_context
def info(ctx, plugin_name):
    """Show detailed information about a plugin."""
    plugin_info = find_plugin(plugin_name, ctx.plugin_dir, ctx.cache_path)

    if plugin_info is None:
        # Get available plugins for error message
        plugins = list_plugins(ctx.plugin_dir, ctx.cache_path)
        click.echo(f"Error: Plugin '{plugin_name}' not found", err=True)
        click.echo(
            f"Available plugins: {', '.join(sorted(plugins.keys()))}", err=True
        )
        sys.exit(1)

    # Display info
    click.echo(f"Plugin: {plugin_info.name}")
    click.echo(f"Type: {plugin_info.plugin_type.capitalize()}")
    click.echo(f"Path: {plugin_info.path}")
    if plugin_info.description:
        click.echo(f"Description: {plugin_info.description}")

    click.echo("\nMethods:")
    if plugin_info.methods:
        for method in plugin_info.methods:
            doc = plugin_info.method_docs.get(method, "")
            if doc:
                click.echo(f"  {method}()  {doc}")
            else:
                click.echo(f"  {method}()")
    else:
        click.echo("  (none detected)")

    click.echo("\nMatches:")
    for pattern in plugin_info.matches:
        click.echo(f"  {pattern}")

    click.echo("\nSchema: Variable (NDJSON output)")

    if plugin_info.dependencies:
        click.echo("\nDependencies:")
        for dep in plugin_info.dependencies:
            click.echo(f"  {dep}")
    else:
        click.echo("\nDependencies: (none)")

    if plugin_info.requires_python:
        click.echo(f"Requires Python: {plugin_info.requires_python}")

    # Show usage examples
    click.echo("\nUsage:")
    if "reads" in plugin_info.methods and "writes" in plugin_info.methods:
        click.echo(
            f"  jn cat input.ext                    # Read using {plugin_info.name}"
        )
        click.echo(
            f"  echo '{{}}' | jn put output.ext     # Write using {plugin_info.name}"
        )
    elif "reads" in plugin_info.methods:
        click.echo(
            f"  jn cat source                       # Read using {plugin_info.name}"
        )
    elif "writes" in plugin_info.methods:
        click.echo(
            f"  echo '{{}}' | jn put output         # Write using {plugin_info.name}"
        )
    elif "filters" in plugin_info.methods:
        click.echo(
            f"  jn cat data.json | jn plugin call {plugin_info.name} [args]"
        )


@plugin.command(
    name="call",
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED, required=True)
@pass_context
def call(ctx, args):
    """Call a plugin directly by name.

    Useful for testing plugins standalone or debugging.

    Examples:
        jn plugin call csv_ --mode read < input.csv
        jn plugin call csv_ --test
        jn plugin call jq_ --query '.name'
    """
    # First arg is the plugin name, rest are plugin arguments
    if not args:
        click.echo("Error: Plugin name required", err=True)
        sys.exit(1)

    name = args[0]
    plugin_args = list(args[1:])

    # Find plugin
    plugin_info = find_plugin(name, ctx.plugin_dir, ctx.cache_path)

    if plugin_info is None:
        plugins = list_plugins(ctx.plugin_dir, ctx.cache_path)
        click.echo(f"Error: Plugin '{name}' not found", err=True)
        click.echo(
            f"Available plugins: {', '.join(sorted(plugins.keys()))}", err=True
        )
        sys.exit(1)

    # Call plugin
    exit_code = call_plugin(plugin_info.path, plugin_args)
    sys.exit(exit_code)


# Note: plugin self-tests have been removed. Use outside-in CLI tests instead.
