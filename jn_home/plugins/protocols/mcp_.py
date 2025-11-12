#!/usr/bin/env -S uv run --script
"""MCP (Model Context Protocol) plugin for connecting to MCP servers.

This plugin enables reading from and writing to MCP servers, supporting both
resources (data endpoints) and tools (functional endpoints).

Examples:
    # List resources from a server
    jn cat "mcp://biomcp?list=resources"

    # Read a specific resource
    jn cat "mcp://biomcp?resource=resource://example"

    # List available tools
    jn cat "mcp://biomcp?list=tools"

    # Call a tool
    jn cat "mcp://biomcp?tool=search&gene=BRAF"

    # Call a tool with stdin data (write mode)
    echo '{"gene": "BRAF"}' | jn put "mcp://biomcp?tool=search"
"""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.1.0",
# ]
# [tool.jn]
# matches = [
#   "^mcp://.*",
#   "^mcp\\+stdio://.*",
#   "^mcp\\+http://.*"
# ]
# ///

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import parse_qs, urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def error_record(error_type: str, message: str, **extra) -> dict:
    """Create standardized error record."""
    return {"_error": True, "type": error_type, "message": message, **extra}


def load_server_config(server_name: str) -> Optional[dict]:
    """Load MCP server configuration from config file.

    Looks for config in:
    1. $JN_HOME/mcp-servers.json
    2. ~/.jn/mcp-servers.json
    3. Current directory ./mcp-servers.json

    Args:
        server_name: Name of the MCP server

    Returns:
        Server config dict with 'command' and 'args', or None if not found
    """
    config_paths = [
        Path(os.environ.get("JN_HOME", "~/.jn")).expanduser() / "mcp-servers.json",
        Path.home() / ".jn" / "mcp-servers.json",
        Path("mcp-servers.json"),
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    if server_name in config:
                        return config[server_name]
            except (json.JSONDecodeError, IOError) as e:
                # Continue to next config file
                continue

    return None


def parse_mcp_url(url: str) -> tuple[str, str, dict]:
    """Parse MCP URL into components.

    Format: mcp://server-name?param=value&param2=value2
            mcp+stdio://server-name?param=value
            mcp+http://host:port/path?param=value

    Args:
        url: MCP URL to parse

    Returns:
        Tuple of (transport, server_name, params)
    """
    parsed = urlparse(url)

    # Determine transport from scheme
    if parsed.scheme == "mcp":
        transport = "stdio"  # Default to stdio
    elif parsed.scheme == "mcp+stdio":
        transport = "stdio"
    elif parsed.scheme == "mcp+http":
        transport = "http"
    else:
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")

    # Server name is the netloc (hostname)
    server_name = parsed.netloc

    # Parse query parameters
    params = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()}

    return transport, server_name, params


async def connect_stdio_server(server_config: dict) -> ClientSession:
    """Connect to an MCP server via stdio transport.

    Args:
        server_config: Config dict with 'command' and 'args'

    Returns:
        Connected ClientSession
    """
    server_params = StdioServerParameters(
        command=server_config["command"],
        args=server_config.get("args", []),
        env=server_config.get("env"),
    )

    # Create stdio client connection
    read_stream, write_stream = await stdio_client(server_params)

    # Initialize session
    session = ClientSession(read_stream, write_stream)
    await session.initialize()

    return session


async def list_resources_async(server_config: dict) -> Iterator[dict]:
    """List all resources from an MCP server.

    Args:
        server_config: Server configuration

    Yields:
        Resource metadata as dicts
    """
    async with await connect_stdio_server(server_config) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # List resources
            result = await session.list_resources()

            for resource in result.resources:
                yield {
                    "type": "resource",
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": getattr(resource, "description", None),
                    "mimeType": getattr(resource, "mimeType", None),
                }


async def read_resource_async(server_config: dict, resource_uri: str) -> Iterator[dict]:
    """Read a specific resource from an MCP server.

    Args:
        server_config: Server configuration
        resource_uri: URI of the resource to read

    Yields:
        Resource content as dicts
    """
    async with await connect_stdio_server(server_config) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Read resource
            result = await session.read_resource(resource_uri)

            # Yield each content item
            for content in result.contents:
                yield {
                    "type": "resource_content",
                    "uri": resource_uri,
                    "mimeType": getattr(content, "mimeType", None),
                    "text": getattr(content, "text", None),
                    "blob": getattr(content, "blob", None),
                }


async def list_tools_async(server_config: dict) -> Iterator[dict]:
    """List all tools from an MCP server.

    Args:
        server_config: Server configuration

    Yields:
        Tool metadata as dicts
    """
    async with await connect_stdio_server(server_config) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # List tools
            result = await session.list_tools()

            for tool in result.tools:
                yield {
                    "type": "tool",
                    "name": tool.name,
                    "description": getattr(tool, "description", None),
                    "inputSchema": tool.inputSchema,
                }


async def call_tool_async(
    server_config: dict, tool_name: str, arguments: dict
) -> Iterator[dict]:
    """Call a tool on an MCP server.

    Args:
        server_config: Server configuration
        tool_name: Name of the tool to call
        arguments: Tool arguments as dict

    Yields:
        Tool results as dicts
    """
    async with await connect_stdio_server(server_config) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Call tool
            result = await session.call_tool(tool_name, arguments)

            # Yield each content item from result
            for content in result.content:
                yield {
                    "type": "tool_result",
                    "tool": tool_name,
                    "mimeType": getattr(content, "mimeType", None),
                    "text": getattr(content, "text", None),
                    "blob": getattr(content, "blob", None),
                }


def reads(
    url: str,
    operation: str = None,
    resource: str = None,
    tool: str = None,
    **tool_args,
) -> Iterator[dict]:
    """Read from an MCP server and yield NDJSON records.

    Args:
        url: MCP URL (e.g., mcp://biomcp?list=resources)
        operation: Operation to perform ('list')
        resource: Resource URI to read
        tool: Tool name to call
        **tool_args: Additional arguments for tool calls

    Yields:
        Dict records from the MCP server, or error records
    """
    try:
        # Parse URL
        transport, server_name, params = parse_mcp_url(url)

        # Merge URL params with function args
        if "list" in params:
            operation = params["list"]
        if "resource" in params:
            resource = params["resource"]
        if "tool" in params:
            tool = params["tool"]

        # Merge remaining params as tool args
        for key, value in params.items():
            if key not in ("list", "resource", "tool"):
                tool_args[key] = value

        # Load server configuration
        server_config = load_server_config(server_name)
        if not server_config:
            yield error_record(
                "config_not_found",
                f"MCP server '{server_name}' not found in config",
                server_name=server_name,
            )
            return

        # TODO: Support HTTP transport
        if transport != "stdio":
            yield error_record(
                "unsupported_transport",
                f"Transport '{transport}' not yet supported (only stdio)",
                transport=transport,
            )
            return

        # Route to appropriate async operation
        if operation == "resources":
            coro = list_resources_async(server_config)
        elif operation == "tools":
            coro = list_tools_async(server_config)
        elif resource:
            coro = read_resource_async(server_config, resource)
        elif tool:
            coro = call_tool_async(server_config, tool, tool_args)
        else:
            # Default: list resources
            coro = list_resources_async(server_config)

        # Run async operation and yield results
        async def run():
            async for record in coro:
                yield record

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # We need to collect all results since we can't yield from async
            results = []

            async def collect():
                if operation == "resources":
                    async for record in list_resources_async(server_config):
                        results.append(record)
                elif operation == "tools":
                    async for record in list_tools_async(server_config):
                        results.append(record)
                elif resource:
                    async for record in read_resource_async(server_config, resource):
                        results.append(record)
                elif tool:
                    async for record in call_tool_async(server_config, tool, tool_args):
                        results.append(record)
                else:
                    # Default: list resources
                    async for record in list_resources_async(server_config):
                        results.append(record)

            loop.run_until_complete(collect())

            for record in results:
                yield record
        finally:
            loop.close()

    except Exception as e:
        yield error_record("mcp_error", str(e), exception_type=type(e).__name__)


def writes(tool: str = None, **config) -> None:
    """Read NDJSON from stdin and call MCP tools with the data.

    Args:
        tool: Tool name to call
        **config: Additional configuration
    """
    # Read MCP URL from config or first line
    url = config.get("url")
    if not url:
        # Read URL from first line of stdin
        first_line = sys.stdin.readline().strip()
        if first_line:
            try:
                first_record = json.loads(first_line)
                url = first_record.get("_mcp_url")
            except json.JSONDecodeError:
                url = first_line

    if not url:
        print(
            json.dumps(error_record("missing_url", "MCP URL required for write mode")),
            flush=True,
        )
        return

    try:
        # Parse URL
        transport, server_name, params = parse_mcp_url(url)

        # Get tool name from params or config
        if "tool" in params:
            tool = params["tool"]

        if not tool:
            print(
                json.dumps(error_record("missing_tool", "Tool name required for write mode")),
                flush=True,
            )
            return

        # Load server configuration
        server_config = load_server_config(server_name)
        if not server_config:
            print(
                json.dumps(
                    error_record(
                        "config_not_found",
                        f"MCP server '{server_name}' not found in config",
                        server_name=server_name,
                    )
                ),
                flush=True,
            )
            return

        # Read NDJSON records and call tool for each
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)

                    # Skip internal fields
                    arguments = {
                        k: v for k, v in record.items() if not k.startswith("_")
                    }

                    # Call tool with record as arguments
                    async def call_and_print():
                        async for result in call_tool_async(
                            server_config, tool, arguments
                        ):
                            print(json.dumps(result), flush=True)

                    loop.run_until_complete(call_and_print())

                except json.JSONDecodeError as e:
                    print(
                        json.dumps(error_record("json_decode_error", str(e), line=line[:100])),
                        flush=True,
                    )
        finally:
            loop.close()

    except Exception as e:
        print(
            json.dumps(error_record("mcp_error", str(e), exception_type=type(e).__name__)),
            flush=True,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MCP protocol plugin")
    parser.add_argument("--mode", choices=["read", "write"], help="Operation mode")
    parser.add_argument("url", nargs="?", help="MCP URL to connect to")
    parser.add_argument("--operation", choices=["resources", "tools"], help="List operation")
    parser.add_argument("--resource", help="Resource URI to read")
    parser.add_argument("--tool", help="Tool name to call")

    args, unknown = parser.parse_known_args()

    if not args.mode:
        parser.error("--mode is required")

    if args.mode == "read":
        if not args.url:
            parser.error("URL is required for read mode")

        # Parse unknown args as tool arguments (--key=value)
        tool_args = {}
        for arg in unknown:
            if arg.startswith("--"):
                if "=" in arg:
                    key, value = arg[2:].split("=", 1)
                    tool_args[key] = value

        for record in reads(
            url=args.url,
            operation=args.operation,
            resource=args.resource,
            tool=args.tool,
            **tool_args,
        ):
            print(json.dumps(record), flush=True)

    else:  # write mode
        writes(tool=args.tool, url=args.url)
