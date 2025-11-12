#!/usr/bin/env -S uv run --script
"""MCP (Model Context Protocol) plugin for connecting to MCP servers.

This plugin enables reading from and writing to MCP servers using profile references.

Examples:
    jn cat "@biomcp?list=resources"
    jn cat "@biomcp/search?gene=BRAF"
    echo '{"gene": "BRAF"}' | jn put "@biomcp/search"
"""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.1.0",
# ]
# [tool.jn]
# matches = [
#   "^@[a-zA-Z0-9_-]+",
# ]
# ///

import asyncio
import json
import sys
from pathlib import Path
from typing import Iterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Import MCP profile system
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
from jn.profiles.mcp import resolve_profile_reference, ProfileError


def error_record(error_type: str, message: str, **extra) -> dict:
    """Create standardized error record."""
    return {"_error": True, "type": error_type, "message": message, **extra}


async def execute_mcp_operation(server_config: dict, operation: dict) -> list[dict]:
    """Execute an MCP operation and return results.

    Connects to server, executes operation, properly cleans up resources.
    """
    results = []

    # Setup server connection
    server_params = StdioServerParameters(
        command=server_config["command"],
        args=server_config.get("args", []),
        env=server_config.get("env"),
    )

    # Use context manager for proper cleanup
    read_stream, write_stream = await stdio_client(server_params)
    session = ClientSession(read_stream, write_stream)

    try:
        await session.initialize()
        op_type = operation["type"]

        if op_type == "list_resources":
            result = await session.list_resources()
            for resource in result.resources:
                results.append({
                    "type": "resource",
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": getattr(resource, "description", None),
                    "mimeType": getattr(resource, "mimeType", None),
                })

        elif op_type == "list_tools":
            result = await session.list_tools()
            for tool in result.tools:
                results.append({
                    "type": "tool",
                    "name": tool.name,
                    "description": getattr(tool, "description", None),
                    "inputSchema": tool.inputSchema,
                })

        elif op_type == "read_resource":
            resource_uri = operation["resource"]
            result = await session.read_resource(resource_uri)
            for content in result.contents:
                results.append({
                    "type": "resource_content",
                    "uri": resource_uri,
                    "mimeType": getattr(content, "mimeType", None),
                    "text": getattr(content, "text", None),
                    "blob": getattr(content, "blob", None),
                })

        elif op_type == "call_tool":
            tool_name = operation["tool"]
            arguments = operation["params"]
            result = await session.call_tool(tool_name, arguments)
            for content in result.content:
                results.append({
                    "type": "tool_result",
                    "tool": tool_name,
                    "mimeType": getattr(content, "mimeType", None),
                    "text": getattr(content, "text", None),
                    "blob": getattr(content, "blob", None),
                })

    finally:
        # Properly close session and streams to avoid resource leaks
        try:
            # Close MCP session
            if hasattr(session, '__aexit__'):
                await session.__aexit__(None, None, None)

            # Close streams to terminate subprocess
            if hasattr(read_stream, 'aclose'):
                await read_stream.aclose()
            if hasattr(write_stream, 'aclose'):
                await write_stream.aclose()
        except Exception as e:
            # Best effort cleanup - log but don't fail on cleanup errors
            print(f"Warning: MCP cleanup error: {e}", file=sys.stderr)

    return results


async def execute_tool_with_session(session: ClientSession, tool_name: str, arguments: dict) -> list[dict]:
    """Execute a tool call with an existing session.

    Used by writes() to reuse connection across multiple calls.
    """
    results = []
    result = await session.call_tool(tool_name, arguments)
    for content in result.content:
        results.append({
            "type": "tool_result",
            "tool": tool_name,
            "mimeType": getattr(content, "mimeType", None),
            "text": getattr(content, "text", None),
            "blob": getattr(content, "blob", None),
        })
    return results


def reads(url: str, **params) -> Iterator[dict]:
    """Read from an MCP server using profile reference.

    Args:
        url: Profile reference (e.g., @biomcp/search)
        **params: Additional parameters merged with URL query params

    Yields:
        Dict records from the MCP server
    """
    try:
        server_config, operation = resolve_profile_reference(url, params)
    except ProfileError as e:
        yield error_record("profile_error", str(e))
        return
    except Exception as e:
        yield error_record("resolution_error", str(e), exception_type=type(e).__name__)
        return

    # Execute async operation
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(execute_mcp_operation(server_config, operation))
        yield from results
    except Exception as e:
        yield error_record("mcp_error", str(e), exception_type=type(e).__name__)
    finally:
        loop.close()


def writes(url: str | None = None, **config) -> None:
    """Read NDJSON from stdin and call MCP tool with each record.

    Reuses a single MCP connection for all records to avoid resource leaks.

    Args:
        url: Profile reference for the tool (e.g., @biomcp/search)
        **config: Additional configuration
    """
    if not url:
        print(json.dumps(error_record("missing_url", "MCP profile reference required")), flush=True)
        return

    try:
        server_config, operation = resolve_profile_reference(url, {})
    except ProfileError as e:
        print(json.dumps(error_record("profile_error", str(e))), flush=True)
        return

    if operation["type"] != "call_tool":
        print(json.dumps(error_record("invalid_operation", "Write mode requires a tool reference")), flush=True)
        return

    tool_name = operation["tool"]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def process_records():
        """Connect once and process all records with reused session."""
        # Setup server connection
        server_params = StdioServerParameters(
            command=server_config["command"],
            args=server_config.get("args", []),
            env=server_config.get("env"),
        )

        read_stream, write_stream = await stdio_client(server_params)
        session = ClientSession(read_stream, write_stream)

        try:
            await session.initialize()

            # Process each input line with reused session
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                    arguments = {k: v for k, v in record.items() if not k.startswith("_")}

                    # Call tool with existing session (no reconnection)
                    results = await execute_tool_with_session(session, tool_name, arguments)

                    for result in results:
                        print(json.dumps(result), flush=True)

                except json.JSONDecodeError as e:
                    print(json.dumps(error_record("json_decode_error", str(e), line=line[:100])), flush=True)

        finally:
            # Properly close session and streams
            try:
                if hasattr(session, '__aexit__'):
                    await session.__aexit__(None, None, None)
                if hasattr(read_stream, 'aclose'):
                    await read_stream.aclose()
                if hasattr(write_stream, 'aclose'):
                    await write_stream.aclose()
            except Exception as e:
                print(f"Warning: MCP cleanup error: {e}", file=sys.stderr)

    try:
        loop.run_until_complete(process_records())
    except Exception as e:
        print(json.dumps(error_record("mcp_error", str(e), exception_type=type(e).__name__)), flush=True)
    finally:
        loop.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MCP protocol plugin")
    parser.add_argument("--mode", choices=["read", "write"], required=True, help="Operation mode")
    parser.add_argument("url", nargs="?", help="MCP profile reference (@server/tool)")

    args, unknown = parser.parse_known_args()

    # Parse unknown args as parameters (--key=value)
    params = {}
    for arg in unknown:
        if arg.startswith("--") and "=" in arg:
            key, value = arg[2:].split("=", 1)
            params[key] = value

    if args.mode == "read":
        if not args.url:
            parser.error("URL is required for read mode")

        for record in reads(args.url, **params):
            print(json.dumps(record), flush=True)

    else:  # write mode
        writes(url=args.url)
