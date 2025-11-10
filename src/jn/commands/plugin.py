"""Plugin management commands."""

import json
import re
import subprocess
import sys
from pathlib import Path

import click

from ..context import pass_context
from ..discovery import get_cached_plugins_with_fallback, parse_pep723


def extract_description(plugin_path: str) -> str:
    """Extract plugin description from docstring.

    Args:
        plugin_path: Path to plugin file

    Returns:
        First line of module docstring or empty string
    """
    try:
        with open(plugin_path) as f:
            content = f.read()
            # Match module docstring
            match = re.search(r'"""(.+?)"""', content, re.DOTALL)
            if match:
                # Get first non-empty line
                lines = match.group(1).strip().split('\n')
                return lines[0].strip() if lines else ""
    except Exception:
        pass
    return ""


def detect_plugin_methods(plugin_path: str) -> list[str]:
    """Detect which methods a plugin implements.

    Args:
        plugin_path: Path to plugin file

    Returns:
        List of method names (reads, writes, filters, test)
    """
    try:
        with open(plugin_path) as f:
            content = f.read()
            methods = []
            if re.search(r'^def reads\(', content, re.MULTILINE):
                methods.append('reads')
            if re.search(r'^def writes\(', content, re.MULTILINE):
                methods.append('writes')
            if re.search(r'^def filters\(', content, re.MULTILINE):
                methods.append('filters')
            if re.search(r'^def test\(', content, re.MULTILINE):
                methods.append('test')
            return methods
    except Exception:
        return []


def infer_plugin_type(methods: list[str]) -> str:
    """Infer plugin type from methods.

    Args:
        methods: List of method names

    Returns:
        Plugin type (format, filter, protocol, shell, unknown)
    """
    has_reads = 'reads' in methods
    has_writes = 'writes' in methods
    has_filters = 'filters' in methods

    if has_reads and has_writes:
        return 'format'
    elif has_filters:
        return 'filter'
    elif has_reads:
        return 'protocol'
    else:
        return 'unknown'


@click.group(invoke_without_command=True)
@click.pass_context
def plugin(ctx):
    """Manage and inspect plugins.

    If no subcommand is provided, defaults to 'list'.
    """
    if ctx.invoked_subcommand is None:
        # Default to list command
        ctx.invoke(list_plugins)


@plugin.command(name="list")
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']),
              default='text', help='Output format')
@pass_context
def list_plugins(ctx, output_format):
    """List all available plugins."""
    plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)

    if not plugins:
        click.echo("No plugins found")
        return

    if output_format == 'json':
        # Machine-readable output
        output = {}
        for name, meta in sorted(plugins.items()):
            output[name] = {
                'path': meta.path,
                'matches': meta.matches,
                'description': extract_description(meta.path)
            }
        click.echo(json.dumps(output, indent=2))
    else:
        # Human-readable output
        max_name_len = max(len(name) for name in plugins.keys())

        for name, meta in sorted(plugins.items()):
            description = extract_description(meta.path)
            if not description:
                # Fallback: show patterns
                description = f"Matches: {', '.join(meta.matches[:2])}"
                if len(meta.matches) > 2:
                    description += f" (+{len(meta.matches) - 2} more)"

            click.echo(f"{name:{max_name_len}}  {description}")

        click.echo(f"\nUse 'jn plugin info <name>' for detailed information")


@plugin.command(name="info")
@click.argument('plugin_name')
@pass_context
def info(ctx, plugin_name):
    """Show detailed information about a plugin."""
    plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)

    if plugin_name not in plugins:
        click.echo(f"Error: Plugin '{plugin_name}' not found", err=True)
        click.echo(f"Available plugins: {', '.join(sorted(plugins.keys()))}", err=True)
        sys.exit(1)

    plugin = plugins[plugin_name]

    # Extract detailed information
    description = extract_description(plugin.path)
    methods = detect_plugin_methods(plugin.path)
    plugin_type = infer_plugin_type(methods)

    # Parse PEP 723 for full metadata
    pep723 = parse_pep723(Path(plugin.path))

    # Display info
    click.echo(f"Plugin: {plugin_name}")
    click.echo(f"Type: {plugin_type.capitalize()}")
    click.echo(f"Path: {plugin.path}")
    if description:
        click.echo(f"Description: {description}")

    click.echo(f"\nMethods:")
    if methods:
        for method in methods:
            # Try to extract method docstring
            try:
                with open(plugin.path) as f:
                    content = f.read()
                    pattern = rf'^def {method}\([^)]*\):[^"]*"""([^"]+)"""'
                    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
                    if match:
                        doc = match.group(1).strip().split('\n')[0]
                        click.echo(f"  {method}()  {doc}")
                    else:
                        click.echo(f"  {method}()")
            except Exception:
                click.echo(f"  {method}()")
    else:
        click.echo("  (none detected)")

    click.echo(f"\nMatches:")
    for pattern in plugin.matches:
        click.echo(f"  {pattern}")

    click.echo(f"\nSchema: Variable (NDJSON output)")

    if plugin.dependencies:
        click.echo(f"\nDependencies:")
        for dep in plugin.dependencies:
            click.echo(f"  {dep}")
    else:
        click.echo(f"\nDependencies: (none)")

    if plugin.requires_python:
        click.echo(f"Requires Python: {plugin.requires_python}")

    # Show usage examples
    click.echo(f"\nUsage:")
    if 'reads' in methods and 'writes' in methods:
        click.echo(f"  jn cat input.ext                    # Read using {plugin_name}")
        click.echo(f"  echo '{{}}' | jn put output.ext     # Write using {plugin_name}")
    elif 'reads' in methods:
        click.echo(f"  jn cat source                       # Read using {plugin_name}")
    elif 'writes' in methods:
        click.echo(f"  echo '{{}}' | jn put output         # Write using {plugin_name}")
    elif 'filters' in methods:
        click.echo(f"  jn cat data.json | jn plugin call {plugin_name} [args]")


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
    plugin_args = args[1:]

    # Load plugins from cache (with fallback)
    plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)

    # Find plugin by name
    if name not in plugins:
        click.echo(f"Error: Plugin '{name}' not found", err=True)
        click.echo(f"Available plugins: {', '.join(sorted(plugins.keys()))}", err=True)
        sys.exit(1)

    plugin = plugins[name]

    # Build command
    cmd = [sys.executable, plugin.path, *list(plugin_args)]

    # Execute plugin (inherit stdin/stdout/stderr)
    proc = subprocess.Popen(cmd)
    proc.wait()

    sys.exit(proc.returncode)


@plugin.command(name="test")
@click.argument('plugin_name', required=False)
@pass_context
def test(ctx, plugin_name):
    """Run plugin self-tests.

    If no plugin name is provided, tests all plugins.
    """
    plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)

    if plugin_name:
        # Test single plugin
        if plugin_name not in plugins:
            click.echo(f"Error: Plugin '{plugin_name}' not found", err=True)
            sys.exit(1)

        plugin = plugins[plugin_name]
        click.echo(f"Testing {plugin_name}...")

        proc = subprocess.run(
            [sys.executable, plugin.path, '--test'],
            capture_output=False
        )
        sys.exit(proc.returncode)
    else:
        # Test all plugins
        failed = []
        passed = []

        for name, plugin in sorted(plugins.items()):
            click.echo(f"Testing {name}...", nl=False)

            proc = subprocess.run(
                [sys.executable, plugin.path, '--test'],
                capture_output=True,
                text=True
            )

            if proc.returncode == 0:
                click.echo(" ✓")
                passed.append(name)
            else:
                click.echo(" ✗")
                failed.append(name)
                if proc.stderr:
                    click.echo(f"  Error: {proc.stderr}", err=True)

        click.echo(f"\nResults: {len(passed)} passed, {len(failed)} failed")

        if failed:
            click.echo(f"Failed: {', '.join(failed)}", err=True)
            sys.exit(1)
