"""Inspect command - list tools and resources from protocol servers."""

import json
import subprocess
import sys

import click

from ...context import pass_context
from ..helpers import check_uv_available


def _format_text_output(result: dict) -> str:
    """Format inspect result as human-readable text."""
    if "_error" in result:
        return f"Error: {result['message']}"

    lines = []
    transport = result.get("transport", "unknown")

    # MCP server format
    if transport == "stdio":
        lines.append(f"Server: {result.get('server', 'unknown')}")
        lines.append(f"Transport: {transport}")
        lines.append("")

        # Tools section
        tools = result.get("tools", [])
        lines.append(f"Tools ({len(tools)}):")
        if tools:
            for tool in tools:
                lines.append(f"  • {tool['name']}")
                if tool.get("description"):
                    lines.append(f"    {tool['description']}")

                # Show input schema
                schema = tool.get("inputSchema", {})
                properties = schema.get("properties", {})
                required = schema.get("required", [])

                if properties:
                    lines.append("    Parameters:")
                    for param_name, param_info in properties.items():
                        param_type = param_info.get("type", "any")
                        param_desc = param_info.get("description", "")
                        req_marker = "*" if param_name in required else " "
                        lines.append(
                            f"      {req_marker} {param_name} ({param_type}): {param_desc}"
                        )
                lines.append("")
        else:
            lines.append("  (none)")
            lines.append("")

        # Resources section
        resources = result.get("resources", [])
        lines.append(f"Resources ({len(resources)}):")
        if resources:
            for resource in resources:
                lines.append(f"  • {resource['name']}")
                if resource.get("description"):
                    lines.append(f"    {resource['description']}")
                lines.append(f"    URI: {resource['uri']}")
                if resource.get("mimeType"):
                    lines.append(f"    Type: {resource['mimeType']}")
                lines.append("")
        else:
            lines.append("  (none)")

    # HTTP API format
    elif transport == "http":
        if "api" in result:
            # Profile-based HTTP API
            lines.append(f"API: {result.get('api', 'unknown')}")
            lines.append(f"Base URL: {result.get('base_url', 'unknown')}")
            lines.append(f"Transport: {transport}")
            lines.append("")

            sources = result.get("sources", [])
            lines.append(f"Sources ({len(sources)}):")
            if sources:
                for source in sources:
                    lines.append(f"  • {source['name']}")
                    if source.get("description"):
                        lines.append(f"    {source['description']}")
                    lines.append(f"    Path: {source.get('path', '')}")
                    lines.append(f"    Method: {source.get('method', 'GET')}")
                    params = source.get("params", [])
                    if params:
                        lines.append(f"    Parameters: {', '.join(params)}")
                    lines.append("")
            else:
                lines.append("  (none)")
        else:
            # Naked HTTP URL
            lines.append(f"URL: {result.get('url', 'unknown')}")
            lines.append(f"Host: {result.get('host', 'unknown')}")
            lines.append(f"Scheme: {result.get('scheme', 'http')}")
            lines.append(f"Transport: {transport}")
            lines.append("")
            lines.append(result.get("description", "No description"))

    # Gmail format
    elif transport == "gmail":
        lines.append(f"Account: {result.get('account', 'unknown')}")
        if result.get("email"):
            lines.append(f"Email: {result['email']}")
        lines.append(f"Transport: {transport}")
        lines.append(f"Messages Total: {result.get('messagesTotal', 0)}")
        lines.append(f"Threads Total: {result.get('threadsTotal', 0)}")
        lines.append("")

        labels = result.get("labels", [])
        lines.append(f"Labels ({len(labels)}):")
        if labels:
            for label in labels:
                lines.append(f"  • {label['name']} (ID: {label['id']})")
                lines.append(f"    Type: {label.get('type', 'user')}")
                lines.append(
                    f"    Messages: {label.get('messagesTotal', 0)} ({label.get('messagesUnread', 0)} unread)"
                )
                lines.append("")
        else:
            lines.append("  (none)")

    else:
        # Generic format (fallback)
        lines.append(f"Transport: {transport}")
        lines.append("")
        for key, value in result.items():
            if key not in ["transport", "_error"]:
                lines.append(f"{key}: {value}")

    return "\n".join(lines)


@click.command()
@click.argument("server")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format (json or text)",
)
@pass_context
def inspect(ctx, server, output_format):
    """List tools, resources, or sources from protocol servers.

    Supports multiple protocols:
    - MCP: mcp+uvx://package/command or @biomcp
    - HTTP: https://api.example.com or @genomoncology
    - Gmail: gmail://me

    Examples:
        # Inspect MCP server
        jn inspect "mcp+uvx://biomcp-python/biomcp"
        jn inspect "@biomcp"

        # Inspect HTTP API
        jn inspect "https://api.example.com"
        jn inspect "@genomoncology"

        # Inspect Gmail account
        jn inspect "gmail://me"

        # JSON output
        jn inspect "@genomoncology" --format json
    """
    try:
        check_uv_available()

        # Detect which plugin to use based on URL pattern
        from ...plugins.discovery import get_cached_plugins_with_fallback

        plugins = get_cached_plugins_with_fallback(ctx.plugin_dir, ctx.cache_path)

        # Determine plugin based on URL pattern
        plugin_name = None
        if server.startswith("mcp+"):
            plugin_name = "mcp_"
        elif server.startswith("http://") or server.startswith("https://"):
            plugin_name = "http_"
        elif server.startswith("gmail://"):
            plugin_name = "gmail_"
        elif server.startswith("@"):
            # Profile reference - @ is special, determine type by profile location
            # Parse profile name from @api or @api/source
            profile_name = server[1:].split("/")[0].split("?")[0]

            # Check which profile directory contains this profile
            from pathlib import Path
            profile_type = None

            # Search order: project → user → bundled
            search_paths = [
                Path.cwd() / ".jn" / "profiles",
                Path.home() / ".local" / "jn" / "profiles",
            ]

            # Add JN_HOME if set
            import os
            jn_home = os.environ.get("JN_HOME")
            if jn_home:
                search_paths.append(Path(jn_home) / "profiles")
            else:
                # Fallback to bundled (3 levels up from this file)
                bundled = Path(__file__).parent.parent.parent.parent / "jn_home" / "profiles"
                if bundled.exists():
                    search_paths.append(bundled)

            # Determine profile type by which subdirectory contains it
            for base_path in search_paths:
                for protocol in ["mcp", "http", "gmail"]:
                    profile_dir = base_path / protocol / profile_name
                    if profile_dir.exists():
                        profile_type = protocol
                        break
                if profile_type:
                    break

            # Map profile type to plugin name
            if profile_type == "mcp":
                plugin_name = "mcp_"
            elif profile_type == "http":
                plugin_name = "http_"
            elif profile_type == "gmail":
                plugin_name = "gmail_"
            else:
                click.echo(
                    f"Error: Profile '{profile_name}' not found in any protocol directory",
                    err=True,
                )
                sys.exit(1)

        if not plugin_name:
            click.echo(
                f"Error: Unable to determine protocol for: {server}", err=True
            )
            click.echo(
                "Supported protocols: mcp+, http://, https://, gmail://",
                err=True,
            )
            sys.exit(1)

        # Find plugin
        if plugin_name not in plugins:
            click.echo(f"Error: Plugin ({plugin_name}) not found", err=True)
            sys.exit(1)

        plugin = plugins[plugin_name]

        # Build command: uv run --script <plugin> --mode inspect <server>
        cmd = [
            "uv",
            "run",
            "--script",
            str(plugin.path),
            "--mode",
            "inspect",
            server,
        ]

        # Execute plugin
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = proc.communicate()

        # Check for errors
        if proc.returncode != 0:
            click.echo(f"Error: Inspect failed: {stderr}", err=True)
            sys.exit(1)

        # Parse result
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as e:
            click.echo(f"Error: Invalid JSON response: {e}", err=True)
            sys.exit(1)

        # Check for _error in response
        if result.get("_error"):
            click.echo(f"Error: {result.get('message', 'Unknown error')}", err=True)
            sys.exit(1)

        # Output
        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(_format_text_output(result))

    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON response: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
