#!/usr/bin/env -S uv run --script
"""MCP (Model Context Protocol) plugin for connecting to MCP servers.

This plugin enables reading from and writing to MCP servers using:
- Naked MCP URIs: mcp+uvx://package/command?tool=X&param=Y
- Profile references: @biomcp/search?gene=BRAF

Examples:
    # Naked URI access (no profile required)
    jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"
    jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"

    # Profile-based access
    jn cat "@biomcp/search?gene=BRAF"
    jn cat "@biomcp?list=resources"
"""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.1.0",
# ]
# [tool.jn]
# matches = [
#   "^mcp\\+[a-z]+://"
# ]
# manages_parameters = true
# supports_container = true
# ///

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple
from urllib.parse import parse_qs

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ============================================================================
# VENDORED PROFILE RESOLVER (self-contained, no framework imports)
# Copied from src/jn/profiles/mcp.py to maintain plugin self-containment
# ============================================================================


class ProfileError(Exception):
    """Error in profile resolution."""

    pass


def find_profile_paths() -> list[Path]:
    """Get search paths for MCP profiles (in priority order)."""
    paths = []

    # 1. Project profiles (highest priority)
    project_profile_dir = Path.cwd() / ".jn" / "profiles" / "mcp"
    if project_profile_dir.exists():
        paths.append(project_profile_dir)

    # 2. User profiles
    user_profile_dir = Path.home() / ".local" / "jn" / "profiles" / "mcp"
    if user_profile_dir.exists():
        paths.append(user_profile_dir)

    # 3. Bundled profiles (lowest priority)
    jn_home = os.environ.get("JN_HOME")
    if jn_home:
        bundled_dir = Path(jn_home) / "profiles" / "mcp"
    else:
        # Fallback: relative to this file (3 levels up to jn_home)
        bundled_dir = Path(__file__).parent.parent.parent / "profiles" / "mcp"

    if bundled_dir.exists():
        paths.append(bundled_dir)

    return paths


def substitute_env_vars(value: str) -> str:
    """Substitute ${VAR} environment variables in string."""
    if not isinstance(value, str):
        return value

    pattern = r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"

    def replace_var(match):
        var_name = match.group(1)
        var_value = os.environ.get(var_name)
        if var_value is None:
            raise ProfileError(f"Environment variable {var_name} not set")
        return var_value

    return re.sub(pattern, replace_var, value)


def substitute_env_vars_recursive(data):
    """Recursively substitute environment variables in nested structures."""
    if isinstance(data, dict):
        return {k: substitute_env_vars_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [substitute_env_vars_recursive(item) for item in data]
    elif isinstance(data, str):
        return substitute_env_vars(data)
    else:
        return data


def load_hierarchical_profile(
    server_name: str, tool_or_resource: Optional[str] = None
) -> dict:
    """Load hierarchical MCP profile: _meta.json + optional tool/resource.json.

    Args:
        server_name: MCP server name (e.g., "biomcp")
        tool_or_resource: Optional tool/resource name (e.g., "search")

    Returns:
        Merged profile dict with _meta + tool/resource info

    Raises:
        ProfileError: If profile not found
    """
    meta = {}
    specific = {}

    # Search for profile directory
    for search_dir in find_profile_paths():
        server_dir = search_dir / server_name

        if not server_dir.exists():
            continue

        # Load _meta.json (server connection info)
        meta_file = server_dir / "_meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except json.JSONDecodeError as e:
                raise ProfileError(f"Invalid JSON in {meta_file}: {e}")

        # Load tool/resource.json if requested
        if tool_or_resource:
            specific_file = server_dir / f"{tool_or_resource}.json"
            if specific_file.exists():
                try:
                    specific = json.loads(specific_file.read_text())
                except json.JSONDecodeError as e:
                    raise ProfileError(f"Invalid JSON in {specific_file}: {e}")
            elif meta:
                # _meta exists but tool/resource doesn't - that's OK, might be dynamic
                pass

        # If we found meta, we're done
        if meta:
            break

    if not meta:
        raise ProfileError(f"MCP server profile not found: {server_name}")

    # Merge _meta + specific config
    merged = {**meta, **specific}

    # Substitute environment variables recursively
    merged = substitute_env_vars_recursive(merged)

    return merged


def resolve_profile_reference(
    reference: str, params: Optional[Dict] = None
) -> Tuple[Dict, Dict]:
    """Resolve @server/tool reference to server config and operation.

    Args:
        reference: Profile reference like "@biomcp/search" or "@biomcp?tool=search"
        params: Optional parameters for the operation

    Returns:
        Tuple of (server_config, operation_dict)
        where operation_dict contains: {
            "type": "list_tools" | "list_resources" | "call_tool" | "read_resource",
            "tool": "tool_name",  # for call_tool
            "resource": "uri",    # for read_resource
            "params": {...}       # merged params
        }

    Raises:
        ProfileError: If profile not found
    """
    if not reference.startswith("@"):
        raise ProfileError(
            f"Invalid profile reference (must start with @): {reference}"
        )

    # Parse reference: @server_name/tool or @server_name?query
    ref = reference[1:]  # Remove @

    # Check for query params in reference
    if "?" in ref:
        server_part, query_part = ref.split("?", 1)
        # Parse query string
        query_params = {
            k: v[0] if len(v) == 1 else v
            for k, v in parse_qs(query_part).items()
        }
    else:
        server_part = ref
        query_params = {}

    # Parse server/tool path
    parts = server_part.split("/", 1)
    server_name = parts[0]
    tool_name = parts[1] if len(parts) > 1 else None

    # Load server profile (with optional tool definition)
    server_config = load_hierarchical_profile(server_name, tool_name)

    # Merge params: query_params override function params
    merged_params = {**(params or {}), **query_params}

    # Determine operation type
    operation = {}

    if "list" in merged_params:
        # List operation: @biomcp?list=tools or @biomcp?list=resources
        list_type = merged_params.pop("list")
        if list_type == "tools":
            operation["type"] = "list_tools"
        elif list_type == "resources":
            operation["type"] = "list_resources"
        else:
            raise ProfileError(f"Invalid list type: {list_type}")
    elif "resource" in merged_params:
        # Read resource: @biomcp?resource=resource://trials
        operation["type"] = "read_resource"
        operation["resource"] = merged_params.pop("resource")
    elif "tool" in merged_params:
        # Call tool: @biomcp?tool=search&gene=BRAF
        operation["type"] = "call_tool"
        operation["tool"] = merged_params.pop("tool")
    elif tool_name:
        # Tool specified in path: @biomcp/search
        operation["type"] = "call_tool"
        operation["tool"] = tool_name
    else:
        # Default: list resources
        operation["type"] = "list_resources"

    # Add remaining params
    operation["params"] = merged_params

    return server_config, operation


# ============================================================================
# NAKED MCP URI PARSING (no profile required)
# ============================================================================


def parse_naked_mcp_uri(uri: str) -> Tuple[Dict, Dict]:
    """Parse naked MCP URI: mcp+{launcher}://{package}[/{command}]?{params}.

    Supported launchers:
    - uvx: UV tool runner (Python MCPs)
    - npx: NPM package executor (Node MCPs)
    - python: Direct Python script
    - node: Direct Node script

    Examples:
        mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF
        mcp+npx://@upstash/context7-mcp@latest?tool=search&library=fastapi
        mcp+python://./my_server.py?tool=fetch_data
        mcp+node://./server.js?tool=analyze

    Args:
        uri: Naked MCP URI string

    Returns:
        Tuple of (server_config, params) where:
        - server_config: dict with command, args, env for StdioServerParameters
        - params: dict of operation parameters (tool, resource, etc.)

    Raises:
        ValueError: If URI format is invalid
    """
    if not uri.startswith("mcp+"):
        raise ValueError(f"Invalid MCP URI (must start with mcp+): {uri}")

    # Extract launcher type
    protocol, rest = uri.split("://", 1)
    launcher = protocol.split("+")[1]  # "uvx", "npx", "python", "node"

    # Parse package/path and query string
    if "?" in rest:
        package_path, query_string = rest.split("?", 1)
        params = {
            k: v[0] if len(v) == 1 else v
            for k, v in parse_qs(query_string).items()
        }
    else:
        package_path = rest
        params = {}

    # Build server config based on launcher
    if launcher == "uvx":
        # Format: mcp+uvx://package/command?params
        # Command: uv run --with package command [args]
        parts = package_path.split("/")
        package = parts[0]
        command = parts[1] if len(parts) > 1 else params.pop("command", "run")

        server_config = {
            "command": "uv",
            "args": ["run", "--with", package, command],
            "transport": "stdio",
        }

    elif launcher == "npx":
        # Format: mcp+npx://package?params
        # Command: npx -y package
        server_config = {
            "command": "npx",
            "args": ["-y", package_path],
            "transport": "stdio",
        }

    elif launcher == "python":
        # Format: mcp+python://./script.py?params
        # Command: python script.py
        server_config = {
            "command": "python",
            "args": [package_path],
            "transport": "stdio",
        }

    elif launcher == "node":
        # Format: mcp+node://./script.js?params
        # Command: node script.js
        server_config = {
            "command": "node",
            "args": [package_path],
            "transport": "stdio",
        }

    else:
        raise ValueError(
            f"Unsupported MCP launcher: {launcher} (supported: uvx, npx, python, node)"
        )

    return server_config, params


# ============================================================================
# MCP OPERATIONS
# ============================================================================


def error_record(error_type: str, message: str, **extra) -> dict:
    """Create standardized error record."""
    return {"_error": True, "type": error_type, "message": message, **extra}


async def execute_mcp_operation(
    server_config: dict, operation: dict
) -> list[dict]:
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
                results.append(
                    {
                        "type": "resource",
                        "uri": resource.uri,
                        "name": resource.name,
                        "description": getattr(resource, "description", None),
                        "mimeType": getattr(resource, "mimeType", None),
                    }
                )

        elif op_type == "list_tools":
            result = await session.list_tools()
            for tool in result.tools:
                results.append(
                    {
                        "type": "tool",
                        "name": tool.name,
                        "description": getattr(tool, "description", None),
                        "inputSchema": tool.inputSchema,
                    }
                )

        elif op_type == "read_resource":
            resource_uri = operation["resource"]
            result = await session.read_resource(resource_uri)
            for content in result.contents:
                results.append(
                    {
                        "type": "resource_content",
                        "uri": resource_uri,
                        "mimeType": getattr(content, "mimeType", None),
                        "text": getattr(content, "text", None),
                        "blob": getattr(content, "blob", None),
                    }
                )

        elif op_type == "call_tool":
            tool_name = operation["tool"]
            arguments = operation["params"]
            result = await session.call_tool(tool_name, arguments)
            for content in result.content:
                results.append(
                    {
                        "type": "tool_result",
                        "tool": tool_name,
                        "mimeType": getattr(content, "mimeType", None),
                        "text": getattr(content, "text", None),
                        "blob": getattr(content, "blob", None),
                    }
                )

    finally:
        # Properly close session and streams to avoid resource leaks
        try:
            # Close MCP session
            if hasattr(session, "__aexit__"):
                await session.__aexit__(None, None, None)

            # Close streams to terminate subprocess
            if hasattr(read_stream, "aclose"):
                await read_stream.aclose()
            if hasattr(write_stream, "aclose"):
                await write_stream.aclose()
        except Exception as e:
            # Best effort cleanup - log but don't fail on cleanup errors
            print(f"Warning: MCP cleanup error: {e}", file=sys.stderr)

    return results


async def execute_tool_with_session(
    session: ClientSession, tool_name: str, arguments: dict
) -> list[dict]:
    """Execute a tool call with an existing session.

    Used by writes() to reuse connection across multiple calls.
    """
    results = []
    result = await session.call_tool(tool_name, arguments)
    for content in result.content:
        results.append(
            {
                "type": "tool_result",
                "tool": tool_name,
                "mimeType": getattr(content, "mimeType", None),
                "text": getattr(content, "text", None),
                "blob": getattr(content, "blob", None),
            }
        )
    return results


def reads(url: str, limit: int | None = None, **params) -> Iterator[dict]:
    """Read from an MCP server using naked URI or profile reference.

    Supports two formats:
    - Naked URI: mcp+uvx://package/command?tool=X&param=Y
    - Profile reference: @biomcp/search?gene=BRAF

    Container vs Leaf:
    - Container (@biomcp): Lists tools and resources with _type and _container metadata
    - Leaf (@biomcp/search or ?tool=search): Calls tool or reads resource

    Args:
        url: Naked MCP URI or profile reference
        limit: Maximum number of records to return (optional)
        **params: Additional parameters merged with URL query params

    Yields:
        Dict records from the MCP server
    """
    try:
        if url.startswith("mcp+"):
            # Naked URI: parse directly
            server_config, uri_params = parse_naked_mcp_uri(url)
            # Merge params: function params override URI params
            merged_params = {**uri_params, **params}

            # Determine operation from params
            operation = {}
            if "list" in merged_params:
                list_type = merged_params.pop("list")
                if list_type == "tools":
                    operation["type"] = "list_tools"
                elif list_type == "resources":
                    operation["type"] = "list_resources"
                else:
                    raise ValueError(f"Invalid list type: {list_type}")
            elif "resource" in merged_params:
                operation["type"] = "read_resource"
                operation["resource"] = merged_params.pop("resource")
            elif "tool" in merged_params:
                operation["type"] = "call_tool"
                operation["tool"] = merged_params.pop("tool")
            else:
                # Default: list resources
                operation["type"] = "list_resources"

            operation["params"] = merged_params
            container_name = url

        elif url.startswith("@"):
            # Profile reference: check for container vs leaf
            ref = url[1:].split("?")[0]  # Remove @ and query params

            if "/" not in ref:
                # Container: @biomcp (no tool/resource specified)
                # List both tools and resources with metadata
                server_config, _ = resolve_profile_reference(url, params)

                # Execute listing operations
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # List tools
                    tools_op = {"type": "list_tools", "params": {}}
                    tools = loop.run_until_complete(
                        execute_mcp_operation(server_config, tools_op)
                    )

                    count = 0
                    for tool in tools:
                        tool["_type"] = "tool"
                        tool["_container"] = url
                        yield tool
                        count += 1
                        if limit and count >= limit:
                            return

                    # List resources
                    resources_op = {"type": "list_resources", "params": {}}
                    resources = loop.run_until_complete(
                        execute_mcp_operation(server_config, resources_op)
                    )

                    for resource in resources:
                        resource["_type"] = "resource"
                        resource["_container"] = url
                        yield resource
                        count += 1
                        if limit and count >= limit:
                            return
                finally:
                    loop.close()
                return
            else:
                # Leaf: @biomcp/search (tool/resource specified)
                server_config, operation = resolve_profile_reference(url, params)
                container_name = url
        else:
            raise ValueError(f"Invalid MCP URL format: {url}")

    except (ProfileError, ValueError) as e:
        yield error_record("resolution_error", str(e))
        return
    except Exception as e:
        yield error_record(
            "resolution_error", str(e), exception_type=type(e).__name__
        )
        return

    # Execute async operation (for leaf nodes)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(
            execute_mcp_operation(server_config, operation)
        )

        # Apply limit if specified
        count = 0
        for result in results:
            yield result
            count += 1
            if limit and count >= limit:
                break
    except Exception as e:
        yield error_record(
            "mcp_error", str(e), exception_type=type(e).__name__
        )
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
        print(
            json.dumps(
                error_record("missing_url", "MCP profile reference required")
            ),
            flush=True,
        )
        return

    try:
        server_config, operation = resolve_profile_reference(url, {})
    except ProfileError as e:
        print(json.dumps(error_record("profile_error", str(e))), flush=True)
        return

    if operation["type"] != "call_tool":
        print(
            json.dumps(
                error_record(
                    "invalid_operation", "Write mode requires a tool reference"
                )
            ),
            flush=True,
        )
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
                    arguments = {
                        k: v
                        for k, v in record.items()
                        if not k.startswith("_")
                    }

                    # Call tool with existing session (no reconnection)
                    results = await execute_tool_with_session(
                        session, tool_name, arguments
                    )

                    for result in results:
                        print(json.dumps(result), flush=True)

                except json.JSONDecodeError as e:
                    print(
                        json.dumps(
                            error_record(
                                "json_decode_error", str(e), line=line[:100]
                            )
                        ),
                        flush=True,
                    )

        finally:
            # Properly close session and streams
            try:
                if hasattr(session, "__aexit__"):
                    await session.__aexit__(None, None, None)
                if hasattr(read_stream, "aclose"):
                    await read_stream.aclose()
                if hasattr(write_stream, "aclose"):
                    await write_stream.aclose()
            except Exception as e:
                print(f"Warning: MCP cleanup error: {e}", file=sys.stderr)

    try:
        loop.run_until_complete(process_records())
    except Exception as e:
        print(
            json.dumps(
                error_record(
                    "mcp_error", str(e), exception_type=type(e).__name__
                )
            ),
            flush=True,
        )
    finally:
        loop.close()


def inspect_profiles() -> Iterator[dict]:
    """List all available MCP profiles.

    Called by framework with --mode inspect-profiles.
    Returns ProfileInfo-compatible records.
    """
    for profile_root in find_profile_paths():
        # Scan each server directory
        for server_dir in sorted(profile_root.iterdir()):
            if not server_dir.is_dir():
                continue

            server_name = server_dir.name

            # Scan .json files in server directory (skip _meta.json)
            for json_file in sorted(server_dir.glob("*.json")):
                if json_file.name.startswith("_"):
                    continue

                # Parse tool metadata from JSON file
                try:
                    tool_data = json.loads(json_file.read_text())
                except json.JSONDecodeError:
                    continue

                tool_name = json_file.stem  # filename without .json
                description = tool_data.get("description", "")
                params = list(tool_data.get("parameters", {}).keys())

                # Emit profile record
                yield {
                    "_type": "profile",
                    "reference": f"@{server_name}/{tool_name}",
                    "type": "mcp",
                    "namespace": server_name,
                    "name": tool_name,
                    "path": str(json_file),
                    "description": description,
                    "params": params,
                }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MCP protocol plugin")
    parser.add_argument(
        "--mode",
        choices=["read", "write", "inspect-profiles"],
        required=True,
        help="Operation mode",
    )
    parser.add_argument(
        "url", nargs="?", help="MCP naked URI or profile reference"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of records to return",
    )

    args, unknown = parser.parse_known_args()

    # Handle inspect-profiles mode
    if args.mode == "inspect-profiles":
        try:
            for profile in inspect_profiles():
                print(json.dumps(profile), flush=True)
        except Exception as e:
            sys.stderr.write(f"Error listing profiles: {e}\n")
            sys.exit(1)
        sys.exit(0)

    # Parse unknown args as parameters (--key=value)
    params = {}
    for arg in unknown:
        if arg.startswith("--") and "=" in arg:
            key, value = arg[2:].split("=", 1)
            params[key] = value

    if args.mode == "read":
        if not args.url:
            parser.error("URL is required for read mode")

        for record in reads(args.url, limit=args.limit, **params):
            print(json.dumps(record), flush=True)

    else:  # write mode
        writes(url=args.url)
