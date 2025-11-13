"""Inspect command - list tools and resources from MCP servers."""

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
    lines.append(f"Server: {result['server']}")
    lines.append(f"Transport: {result['transport']}")
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
    """List tools and resources from an MCP server.

    Supports two formats:
    - Naked URI: mcp+uvx://package/command
    - Profile reference: @biomcp

    Examples:
        # Inspect MCP server with naked URI
        jn inspect "mcp+uvx://biomcp-python/biomcp"

        # Inspect via profile
        jn inspect "@biomcp"

        # JSON output
        jn inspect "mcp+uvx://biomcp-python/biomcp" --format json
    """
    try:
        check_uv_available()

        # Inspect command is MCP-specific, so bypass addressing system
        # and directly invoke mcp_ plugin to avoid plugin name resolution issues
        # (@biomcp would be interpreted as "find plugin named biomcp" rather than
        # pattern-matching to mcp_ plugin)

        # Find mcp_ plugin
        from ...plugins.discovery import discover_plugins

        plugins = discover_plugins(ctx.plugin_dir)
        if "mcp_" not in plugins:
            click.echo("Error: MCP plugin (mcp_) not found", err=True)
            sys.exit(1)

        mcp_plugin = plugins["mcp_"]

        # Build command: uv run --script <plugin> --mode inspect <server>
        cmd = [
            "uv",
            "run",
            "--script",
            str(mcp_plugin.path),
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
        result = json.loads(stdout)

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
