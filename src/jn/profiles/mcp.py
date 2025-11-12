"""MCP Profile System - hierarchical MCP server configurations.

New hierarchical structure:
  profiles/mcp/{server_name}/_meta.json      - Server info (command, args, env, description)
  profiles/mcp/{server_name}/{tool}.json     - Tool definitions (parameters, description)
  profiles/mcp/{server_name}/{resource}.json - Resource definitions

Example:
  profiles/mcp/biomcp/_meta.json
  profiles/mcp/biomcp/search.json
  profiles/mcp/biomcp/variant_search.json

Reference format:
  @biomcp/search → Merges _meta.json + search.json
  @biomcp?tool=search&gene=BRAF → Server + tool call with params
  @biomcp?list=tools → List tools from server
  @biomcp?resource=resource://trials → Read resource from server
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple


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
        # Fallback: relative to this file
        bundled_dir = Path(__file__).parent.parent.parent.parent / "jn_home" / "profiles" / "mcp"

    if bundled_dir.exists():
        paths.append(bundled_dir)

    return paths


def substitute_env_vars(value: str) -> str:
    """Substitute ${VAR} environment variables in string."""
    if not isinstance(value, str):
        return value

    pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}'

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


def load_hierarchical_profile(server_name: str, tool_or_resource: Optional[str] = None) -> dict:
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


def list_server_tools(server_name: str) -> list[str]:
    """List available tools for a server by scanning profile directory.

    Args:
        server_name: MCP server name

    Returns:
        List of tool names (from .json files, excluding _meta.json)
    """
    tools = []

    for search_dir in find_profile_paths():
        server_dir = search_dir / server_name
        if not server_dir.exists():
            continue

        for json_file in server_dir.glob("*.json"):
            if json_file.name != "_meta.json":
                tools.append(json_file.stem)

        # Take first match (highest priority)
        if tools:
            break

    return tools


def resolve_profile_reference(
    reference: str,
    params: Optional[Dict] = None
) -> Tuple[str, Dict]:
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
        raise ProfileError(f"Invalid profile reference (must start with @): {reference}")

    # Parse reference: @server_name/tool or @server_name?query
    ref = reference[1:]  # Remove @

    # Check for query params in reference
    if "?" in ref:
        server_part, query_part = ref.split("?", 1)
        # Parse query string
        from urllib.parse import parse_qs
        query_params = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(query_part).items()}
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
