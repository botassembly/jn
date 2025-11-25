"""Profile CLI commands - discover and inspect profiles."""

import json
import sys

import click

from ...context import get_builtin_plugins_dir, pass_context
from ...plugins.discovery import (
    discover_plugins,
    get_cached_plugins_with_fallback,
)
from ...profiles.service import get_profile_info, search_profiles


def _get_builtin_plugins():
    """Get builtin plugins for fallback during profile discovery."""
    builtin_dir = get_builtin_plugins_dir()
    if builtin_dir and builtin_dir.exists():
        builtin_plugins = discover_plugins(builtin_dir)
        # Resolve paths to absolute
        for meta in builtin_plugins.values():
            meta.path = str(builtin_dir / meta.path)
        return builtin_plugins
    return None


def _get_profile_types(home_dir=None, plugin_dir=None, cache_path=None):
    """Get available profile types dynamically from plugins.

    Args:
        home_dir: JN home directory (overrides $JN_HOME)
        plugin_dir: Plugin directory for discovery
        cache_path: Cache file path

    Returns list of profile types that have profiles or support profile management.
    """
    # Start with known profile types as baseline
    types = {"jq", "http", "gmail", "mcp", "duckdb"}

    # Try to add discovered plugins (this enriches the list with custom plugins)
    try:
        if plugin_dir and cache_path:
            plugins = get_cached_plugins_with_fallback(plugin_dir, cache_path)
        else:
            # Fallback to default paths if not provided
            from ...context import get_jn_home

            jn_home = get_jn_home()
            plugins = get_cached_plugins_with_fallback(
                jn_home / "plugins",
                jn_home / "cache.json",
            )

        # Add protocol plugins that manage profiles
        for plugin in plugins.values():
            if plugin.role == "protocol":
                # Derive profile type from plugin name (e.g., "duckdb_" -> "duckdb")
                profile_type = plugin.name.rstrip("_")
                types.add(profile_type)

        # Add filter plugins (jq)
        for plugin in plugins.values():
            if plugin.role == "filter":
                types.add(plugin.name.rstrip("_"))
    except Exception as e:
        # If plugin discovery fails, just use baseline types
        print(f"Warning: Failed to discover plugins: {e}", file=sys.stderr)

    # Return sorted list
    return sorted(types)


@click.group(invoke_without_command=True)
@click.pass_context
def profile(ctx):
    """Manage and inspect profiles.

    If no subcommand is provided, defaults to 'list'.
    """
    if ctx.invoked_subcommand is None:
        # Default to list command
        ctx.invoke(list_cmd)


@profile.command(name="list")
@click.argument("query", required=False)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.option(
    "--type",
    "type_filter",
    type=click.Choice(_get_profile_types(), case_sensitive=False),
    help="Filter by profile type",
)
@pass_context
def list_cmd(ctx, query, output_format, type_filter):
    """List and search profiles.

    Examples:
        jn profile list                  # List all profiles
        jn profile list pivot            # Search for "pivot"
        jn profile list --type jq        # Only JQ profiles
        jn profile list gmail --format json
    """
    # Get discovered plugins for inspect-profiles mode
    plugins = get_cached_plugins_with_fallback(
        ctx.plugin_dir, ctx.cache_path, fallback_to_builtin=True
    )
    builtin_plugins = _get_builtin_plugins()

    profiles = search_profiles(
        query=query,
        type_filter=type_filter,
        discovered_plugins=plugins,
        home_dir=ctx.home,
        builtin_plugins=builtin_plugins,
    )

    if not profiles:
        if query:
            click.echo(f"No profiles found matching '{query}'")
        else:
            click.echo("No profiles found")
        return

    if output_format == "json":
        # Machine-readable output
        output = {}
        for p in profiles:
            output[p.reference] = {
                "type": p.type,
                "namespace": p.namespace,
                "name": p.name,
                "path": str(p.path),
                "description": p.description,
                "params": p.params,
            }
        click.echo(json.dumps(output, indent=2))
    else:
        # Human-readable output - group by type
        by_type = {}
        for p in profiles:
            if p.type not in by_type:
                by_type[p.type] = []
            by_type[p.type].append(p)

        # Sort types
        for profile_type in sorted(by_type.keys()):
            # Type header - generate label dynamically
            type_label = f"{profile_type.upper()} Profiles"

            click.echo(f"\n{type_label}:")

            # List profiles in this type
            type_profiles = sorted(
                by_type[profile_type], key=lambda p: p.reference
            )

            # Calculate max reference length for alignment
            max_ref_len = max(len(p.reference) for p in type_profiles)

            for p in type_profiles:
                if p.description:
                    click.echo(
                        f"  {p.reference:{max_ref_len}}  {p.description}"
                    )
                else:
                    click.echo(f"  {p.reference}")

        click.echo(
            "\nUse 'jn profile info <reference>' for detailed information"
        )


@profile.command(name="info")
@click.argument("reference")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@pass_context
def info(ctx, reference, output_format):
    """Show detailed information about a profile.

    Examples:
        jn profile info @gmail/inbox
        jn profile info @builtin/pivot
        jn profile info @gmail/inbox --format json
    """
    # Get discovered plugins for inspect-profiles mode
    plugins = get_cached_plugins_with_fallback(
        ctx.plugin_dir, ctx.cache_path, fallback_to_builtin=True
    )
    builtin_plugins = _get_builtin_plugins()

    profile = get_profile_info(
        reference,
        discovered_plugins=plugins,
        home_dir=ctx.home,
        builtin_plugins=builtin_plugins,
    )

    if profile is None:
        click.echo(f"Error: Profile '{reference}' not found", err=True)
        click.echo("\nAvailable profiles:", err=True)
        all_profiles = search_profiles(
            discovered_plugins=plugins,
            home_dir=ctx.home,
            builtin_plugins=builtin_plugins,
        )
        for p in sorted(all_profiles, key=lambda x: x.reference)[:10]:
            click.echo(f"  {p.reference}", err=True)
        if len(all_profiles) > 10:
            click.echo(f"  ... and {len(all_profiles) - 10} more", err=True)
        click.echo("\nRun 'jn profile list' to see all profiles", err=True)
        sys.exit(1)

    if output_format == "json":
        # Machine-readable output
        output = {
            "reference": profile.reference,
            "type": profile.type,
            "namespace": profile.namespace,
            "name": profile.name,
            "path": str(profile.path),
            "description": profile.description,
            "params": profile.params,
            "examples": profile.examples,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        # Human-readable output
        click.echo(f"Profile: {profile.reference}")
        click.echo(f"Type: {profile.type.upper()}")
        click.echo(f"Location: {profile.path}")

        if profile.description:
            click.echo("\nDescription:")
            click.echo(f"  {profile.description}")

        if profile.params:
            click.echo("\nParameters:")
            for param in profile.params:
                click.echo(f"  {param}")
        else:
            click.echo("\nParameters: (none)")

        # Show examples if available
        if profile.examples:
            click.echo("\nExamples:")
            for ex in profile.examples:
                desc = ex.get("description", "")
                cmd = ex.get("command", "")
                if desc:
                    click.echo(f"  # {desc}")
                click.echo(f"  {cmd}")
                click.echo()

        # Generic usage examples based on type
        elif profile.type == "jq":
            click.echo("\nUsage:")
            click.echo(f"  jn cat data.json | jn filter '{profile.reference}'")
            if profile.params:
                param_examples = " ".join(
                    f"-p {p}=value" for p in profile.params[:2]
                )
                click.echo(
                    f"  jn cat data.json | jn filter '{profile.reference}' {param_examples}"
                )
        else:
            # All protocol profiles (http, gmail, mcp, duckdb, etc.) use jn cat
            click.echo("\nUsage:")
            click.echo(f"  jn cat {profile.reference}")
            if profile.params:
                param_examples = " ".join(
                    f"-p {p}=value" for p in profile.params[:2]
                )
                click.echo(f"  jn cat {profile.reference} {param_examples}")


@profile.command(name="tree")
@click.option(
    "--type",
    "type_filter",
    type=click.Choice(_get_profile_types(), case_sensitive=False),
    help="Filter by profile type",
)
@pass_context
def tree(ctx, type_filter):
    """Show profiles as a tree hierarchy.

    Examples:
        jn profile tree
        jn profile tree --type jq
    """
    # Get discovered plugins for inspect-profiles mode
    plugins = get_cached_plugins_with_fallback(
        ctx.plugin_dir, ctx.cache_path, fallback_to_builtin=True
    )
    builtin_plugins = _get_builtin_plugins()

    profiles = search_profiles(
        type_filter=type_filter,
        discovered_plugins=plugins,
        home_dir=ctx.home,
        builtin_plugins=builtin_plugins,
    )

    if not profiles:
        click.echo("No profiles found")
        return

    # Build tree structure
    tree = {}
    for p in profiles:
        if p.type not in tree:
            tree[p.type] = {}
        if p.namespace not in tree[p.type]:
            tree[p.type][p.namespace] = []
        tree[p.type][p.namespace].append(p)

    # Display tree
    click.echo("profiles/")

    for profile_type in sorted(tree.keys()):
        type_label = profile_type
        click.echo(f"├── {type_label}/")

        namespaces = sorted(tree[profile_type].keys())
        for i, namespace in enumerate(namespaces):
            is_last_namespace = i == len(namespaces) - 1
            namespace_prefix = "└──" if is_last_namespace else "├──"
            click.echo(f"│   {namespace_prefix} {namespace}/")

            namespace_profiles = sorted(
                tree[profile_type][namespace], key=lambda p: p.name
            )
            for j, p in enumerate(namespace_profiles):
                is_last_profile = j == len(namespace_profiles) - 1
                profile_prefix = "└──" if is_last_profile else "├──"

                # Adjust indentation based on namespace position
                indent = "    " if is_last_namespace else "│   "

                desc = f" - {p.description}" if p.description else ""
                click.echo(f"│   {indent}    {profile_prefix} {p.name}{desc}")
