"""Check command - validate plugins and core code."""

import sys
from importlib import resources
from pathlib import Path

import click

from ...context import pass_context
from ...checker import check_files
from ...checker.scanner import find_plugin_files, find_core_files, find_single_plugin
from ...checker.report import format_text, format_json, format_summary


def _get_bundled_plugins_dir() -> Path:
    """Locate the packaged default plugins under jn_home/plugins.

    Uses importlib.resources to work correctly both in development
    and after installation.
    """
    pkg = resources.files("jn_home").joinpath("plugins")
    # For the checker, we need a persistent path, not a context manager
    # This works because jn_home is a package directory on the filesystem
    return Path(str(pkg))


def _get_core_dir() -> Path:
    """Locate the core jn package directory.

    Uses importlib.resources to work correctly both in development
    and after installation.
    """
    pkg = resources.files("jn")
    return Path(str(pkg))


@click.command()
@click.argument("target", default="plugins")
@click.option("--format", "output_format", type=click.Choice(["text", "json", "summary"]), default="text",
              help="Output format (default: text)")
@click.option("--verbose", "-v", is_flag=True, help="Show all details including INFO violations")
@click.option("--rules", multiple=True, help="Specific rules to check (default: all)")
@pass_context
def check(ctx, target, output_format, verbose, rules):
    """Check plugins or core code for violations.

    TARGET can be:
    - 'plugins' - Check all bundled and custom plugins
    - 'core' - Check core framework code
    - 'all' - Check everything
    - <plugin_name> - Check specific plugin (e.g., 'csv_')

    Examples:
        jn check plugins           # Check all plugins
        jn check core              # Check core code
        jn check csv_              # Check CSV plugin
        jn check plugins --verbose # Show all violations
        jn check plugins --format json  # JSON output for CI
    """
    # Determine files to check
    files_to_check = []

    if target == "plugins":
        # Check bundled plugins
        bundled_dir = _get_bundled_plugins_dir()
        files_to_check.extend(find_plugin_files(bundled_dir))

        # Check custom plugins if they exist
        if ctx.plugin_dir.exists():
            files_to_check.extend(find_plugin_files(ctx.plugin_dir))

    elif target == "core":
        # Check core framework code
        core_dir = _get_core_dir()
        files_to_check.extend(find_core_files(core_dir))

    elif target == "all":
        # Check everything
        bundled_dir = _get_bundled_plugins_dir()
        files_to_check.extend(find_plugin_files(bundled_dir))

        if ctx.plugin_dir.exists():
            files_to_check.extend(find_plugin_files(ctx.plugin_dir))

        core_dir = _get_core_dir()
        files_to_check.extend(find_core_files(core_dir))

    else:
        # Assume it's a plugin name
        bundled_dir = _get_bundled_plugins_dir()
        search_dirs = [bundled_dir]
        if ctx.plugin_dir.exists():
            search_dirs.append(ctx.plugin_dir)

        try:
            plugin_file = find_single_plugin(target, search_dirs)
            files_to_check.append(plugin_file)
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    if not files_to_check:
        click.echo("No files found to check", err=True)
        sys.exit(1)

    # Run checks
    rule_list = list(rules) if rules else None
    results = check_files(files_to_check, rules=rule_list)

    # Format output
    if output_format == "json":
        output = format_json(results)
    elif output_format == "summary":
        output = format_summary(results)
    else:  # text
        output = format_text(results, verbose=verbose)

    click.echo(output)

    # Exit with error code if any errors found
    total_errors = sum(r.error_count for r in results)
    if total_errors > 0:
        sys.exit(1)
    else:
        sys.exit(0)
