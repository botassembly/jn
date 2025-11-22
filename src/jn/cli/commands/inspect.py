"""Inspect command - discover capabilities or inspect data."""

import json
import subprocess
import sys

import click

from ...addressing import parse_address
from ...context import pass_context
from ...filtering import build_jq_filter, separate_config_and_filters
from ...introspection import get_plugin_config_params
from ...process_utils import popen_with_validation
from ..helpers import build_subprocess_env_for_coverage, check_uv_available

JN_CLI = [sys.executable, "-m", "jn.cli.main"]


def _is_container(address_str: str) -> bool:
    """Check if address is a container (for capability listing).

    Container patterns:
    - @api (no endpoint)
    - @biomcp (no tool)
    - gmail://me (no label/folder)
    - @plugin (standalone plugin reference)
    - duckdb://file.duckdb (no table/query)

    Returns:
        True if container, False if leaf
    """
    if not address_str.startswith("@"):
        # Protocol URLs need more logic
        if address_str.startswith("gmail://"):
            # gmail://me = container, gmail://me/INBOX = leaf
            return address_str.count("/") == 2

        if address_str.startswith("duckdb://"):
            # duckdb://file.duckdb = container
            # duckdb://file.duckdb/table = leaf
            # duckdb://file.duckdb?query=... = leaf
            base = address_str.split("?")[0]  # Remove query params
            # Check if there's anything after .duckdb or .ddb
            for ext in (".duckdb", ".ddb"):
                if ext in base:
                    suffix = base.split(ext, 1)[1].strip("/")
                    return not suffix  # Container if no suffix
            return False

        # Other protocols default to leaf
        return False

    # Profile/plugin reference
    ref = address_str[1:].split("?")[0]  # Remove @ and query

    # @api/endpoint = leaf, @api = container
    return "/" not in ref


def _format_container_text(result: dict) -> str:
    """Format container listing as human-readable text using generic formatter.

    Plugins emit standardized container metadata with the following structure:
    {
        "_type": "container_listing",
        "_plugin": "plugin_name",
        "_container": "container_identifier",
        "items": [...],
        "metadata": {...}
    }

    This generic formatter works for all plugins without protocol-specific logic.
    """
    if "_error" in result:
        return f"Error: {result['message']}"

    lines = []

    # Extract metadata
    plugin_name = result.get("_plugin", result.get("transport", "unknown"))
    container = result.get("_container", result.get("database", result.get("api", result.get("server", result.get("account", "unknown")))))

    # Header
    lines.append(f"Container: {container} ({plugin_name})")

    # Additional metadata (skip internal fields starting with _)
    metadata = result.get("metadata", {})
    for key, value in metadata.items():
        if not key.startswith("_"):
            # Format key: convert snake_case to Title Case
            display_key = key.replace("_", " ").title()
            lines.append(f"{display_key}: {value}")

    # Legacy fields that might not be in metadata
    for legacy_key in ["base_url", "email", "messagesTotal", "threadsTotal"]:
        if legacy_key in result and legacy_key not in metadata:
            display_key = legacy_key.replace("_", " ").title()
            lines.append(f"{display_key}: {result[legacy_key]}")

    lines.append("")

    # Items listing
    items = result.get("items", result.get("sources", result.get("tools", result.get("resources", result.get("tables", result.get("queries", result.get("labels", [])))))))

    # Detect item type from field names or use generic
    item_type = "Items"
    if "sources" in result:
        item_type = "Sources"
    elif "tools" in result or "resources" in result:
        item_type = "Tools" if "tools" in result else "Resources"
    elif "tables" in result:
        item_type = "Tables"
    elif "queries" in result:
        item_type = "Queries"
    elif "labels" in result:
        item_type = "Labels"

    lines.append(f"{item_type} ({len(items)}):")

    if items:
        for item in items:
            # Item name
            name = item.get("name", item.get("id", "unknown"))
            lines.append(f"  • {name}")

            # Description
            if item.get("description"):
                lines.append(f"    {item['description']}")

            # Show other fields (skip internal ones and name/description)
            skip_fields = {"name", "description", "_type", "_plugin"}
            for key, value in item.items():
                if key not in skip_fields and not key.startswith("_"):
                    display_key = key.replace("_", " ").title()

                    # Special formatting for common field types
                    if isinstance(value, list):
                        if value:  # Non-empty list
                            if key == "params" or key == "parameters":
                                lines.append(f"    {display_key}: {', '.join(str(v) for v in value)}")
                            else:
                                lines.append(f"    {display_key}: {len(value)} items")
                        # Skip empty lists
                    elif isinstance(value, dict):
                        # Handle nested structures (like inputSchema)
                        if key in ["inputSchema", "schema"]:
                            properties = value.get("properties", {})
                            required = value.get("required", [])
                            if properties:
                                lines.append("    Parameters:")
                                for param_name, param_info in properties.items():
                                    param_type = param_info.get("type", "any")
                                    param_desc = param_info.get("description", "")
                                    req_marker = "*" if param_name in required else " "
                                    lines.append(
                                        f"      {req_marker} {param_name} ({param_type}): {param_desc}"
                                    )
                        else:
                            lines.append(f"    {display_key}: {json.dumps(value)}")
                    else:
                        lines.append(f"    {display_key}: {value}")

            lines.append("")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _format_data_text(result: dict) -> str:
    """Format data inspection as human-readable text."""
    lines = []

    lines.append(f"Resource: {result.get('resource', 'unknown')}")
    if result.get("transport"):
        lines.append(f"Transport: {result['transport']}")
    if result.get("format"):
        lines.append(f"Format: {result['format']}")

    rows = result.get("rows", 0)
    limit = result.get("limit")
    if limit is not None:
        lines.append(f"Rows: {rows} (sample, limit: {limit})")
    else:
        lines.append(f"Rows: {rows}")

    lines.append(f"Columns: {result.get('columns', 0)}")
    lines.append("")

    # Schema
    schema = result.get("schema", {})
    if schema:
        lines.append("Schema:")
        for field, info in schema.items():
            nullable = " (nullable)" if info.get("nullable") else ""
            unique = info.get("unique", 0)
            field_min = info.get("min")
            field_max = info.get("max")

            line = f"  {field}: {info['type']}{nullable}"
            if unique:
                line += f" ({unique} unique)"
            if field_min is not None and field_max is not None:
                line += f" [{field_min} to {field_max}]"
            lines.append(line)
        lines.append("")

    # Facets (only fields the analyzer deemed interesting)
    facets = result.get("facets", {})
    if facets:
        lines.append("Facets:")
        # Show up to 5 fields, rendered as simple ASCII tables
        for field, counts in list(facets.items())[:5]:
            items = list(counts.items())
            if not items:
                continue

            # Sort by frequency (desc), then value (asc) for stability
            items.sort(key=lambda kv: (-kv[1], str(kv[0])))
            top_items = items[:10]

            # Compute column widths, ensuring headers fit
            count_width = max(
                len("count"), max(len(str(c)) for _, c in top_items)
            )
            value_width = max(
                len(field), max(len(str(v)) for v, _ in top_items)
            )
            value_width = min(max(value_width, 5), 40)

            # Simple boxed table
            border = (
                "    +"
                + "-" * (count_width + 2)
                + "+"
                + "-" * (value_width + 2)
                + "+"
            )

            lines.append(f"  {field}:")
            lines.append(border)
            header = (
                f"    | {'count'.rjust(count_width)} "
                f"| {field.ljust(value_width)} |"
            )
            lines.append(header)
            lines.append(border)

            for value, count in top_items:
                value_str = str(value)
                row = (
                    f"    | {str(count).rjust(count_width)} "
                    f"| {value_str.ljust(value_width)} |"
                )
                lines.append(row)

            if len(items) > 10:
                remaining = len(items) - 10
                more_txt = f"... ({remaining} more)"
                gutter_width = (
                    count_width + 1 + 1 + value_width
                )  # count + space + value
                lines.append(f"    | {more_txt.ljust(gutter_width)} |")

            lines.append(border)
            lines.append("")

    # Stats
    stats = result.get("stats", {})
    if stats:
        lines.append("Statistics:")
        for field, field_stats in stats.items():
            lines.append(f"  {field}:")
            lines.append(
                f"    Count: {field_stats['count']} (nulls: {field_stats['nulls']})"
            )
            lines.append(f"    Min: {field_stats['min']:.2f}")
            lines.append(f"    Max: {field_stats['max']:.2f}")
            lines.append(f"    Mean: {field_stats['mean']:.2f}")
            lines.append(f"    StdDev: {field_stats['stddev']:.2f}")
            lines.append("")

    return "\n".join(lines)


def _inspect_container(address_str: str) -> dict:
    """Inspect container - call cat and aggregate listings."""
    # Execute: jn cat <container>
    proc = popen_with_validation(
        [*JN_CLI, "cat", address_str],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=build_subprocess_env_for_coverage(),
    )

    listings = []
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            listings.append(record)
        except json.JSONDecodeError:
            continue

    proc.wait()

    if proc.returncode != 0:
        stderr = proc.stderr.read()
        return {
            "_error": True,
            "message": f"Failed to list container: {stderr}",
        }

    if not listings:
        return {"_error": True, "message": "No listings found"}

    # Aggregate based on listing type
    first = listings[0]
    listing_type = first.get("_type")
    container = first.get("_container", "")

    if listing_type == "source":
        # HTTP API sources
        return {
            "api": container.lstrip("@"),
            "base_url": "",  # Would need to fetch from profile
            "transport": "http",
            "sources": [
                {k: v for k, v in rec.items() if not k.startswith("_")}
                for rec in listings
            ],
        }
    elif listing_type in ("tool", "resource"):
        # MCP tools/resources
        tools = [rec for rec in listings if rec.get("_type") == "tool"]
        resources = [rec for rec in listings if rec.get("_type") == "resource"]
        return {
            "server": container,
            "transport": "stdio",
            "tools": [
                {k: v for k, v in rec.items() if not k.startswith("_")}
                for rec in tools
            ],
            "resources": [
                {k: v for k, v in rec.items() if not k.startswith("_")}
                for rec in resources
            ],
        }
    elif listing_type == "label":
        # Gmail labels
        # Extract account info from first record if present
        return {
            "account": "me",
            "email": first.get("email", ""),
            "transport": "gmail",
            "messagesTotal": sum(
                rec.get("messagesTotal", 0) for rec in listings
            ),
            "threadsTotal": 0,  # Would need to aggregate properly
            "labels": [
                {k: v for k, v in rec.items() if not k.startswith("_")}
                for rec in listings
            ],
        }
    elif listing_type == "table":
        # DuckDB tables
        return {
            "database": container,
            "transport": "duckdb",
            "tables": [
                {k: v for k, v in rec.items() if not k.startswith("_")}
                for rec in listings
            ],
        }
    elif listing_type == "query":
        # DuckDB profile queries
        return {
            "namespace": container,
            "transport": "duckdb-profile",
            "queries": [
                {k: v for k, v in rec.items() if not k.startswith("_")}
                for rec in listings
            ],
        }
    else:
        # Generic
        return {
            "transport": "unknown",
            "listings": listings,
        }


def _inspect_data(ctx, address_str: str, limit: int) -> dict:
    """Inspect data - build analysis pipeline."""
    # Parse address
    addr = parse_address(address_str)

    # Get plugin path to introspect config params
    from ...addressing import AddressResolver

    resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path)

    # Resolve to get plugin
    try:
        resolved = resolver.resolve(addr, mode="read")
        plugin_path = resolved.plugin_path
    except Exception as e:
        return {"_error": True, "message": f"Failed to resolve address: {e}"}

    # Get config params from plugin
    config_params = get_plugin_config_params(plugin_path)

    # Separate filters from config
    config, filters = separate_config_and_filters(
        addr.parameters, config_params
    )
    config["limit"] = str(limit)

    # Build URI with config parameters as query string
    from urllib.parse import urlencode

    # Reconstruct URI with config parameters
    base_uri = addr.base
    # Add compression extension back if present
    if addr.compression:
        base_uri = f"{base_uri}.{addr.compression}"
    if addr.format_override:
        base_uri = f"{base_uri}~{addr.format_override}"

    if config:
        query_str = urlencode(config)
        full_uri = f"{base_uri}?{query_str}"
    else:
        full_uri = base_uri

    # Start cat process
    cat_proc = popen_with_validation(
        [*JN_CLI, "cat", full_uri],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=build_subprocess_env_for_coverage(),
    )

    # Add filter if needed
    if filters:
        jq_expr = build_jq_filter(filters)
        filter_proc = popen_with_validation(
            [*JN_CLI, "filter", jq_expr],
            stdin=cat_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=build_subprocess_env_for_coverage(),
        )
        cat_proc.stdout.close()
        analyze_stdin = filter_proc.stdout
    else:
        filter_proc = None
        analyze_stdin = cat_proc.stdout

    # Analyze
    analyze_proc = popen_with_validation(
        [*JN_CLI, "analyze", "--format", "json"],
        stdin=analyze_stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=build_subprocess_env_for_coverage(),
    )

    # Close analyze stdin in parent (allows cat/filter to receive SIGPIPE)
    if filter_proc:
        filter_proc.stdout.close()
    else:
        cat_proc.stdout.close()

    # Wait for analyze to complete
    stdout, stderr = analyze_proc.communicate()

    # Wait for upstream processes and check for errors
    cat_proc.wait()
    if filter_proc:
        filter_proc.wait()

    # Check for upstream failures first (more informative than empty analysis)
    if cat_proc.returncode != 0:
        cat_stderr = cat_proc.stderr.read()
        if isinstance(cat_stderr, bytes):
            cat_stderr = cat_stderr.decode("utf-8")
        return {"_error": True, "message": f"Cat failed: {cat_stderr}"}

    if filter_proc and filter_proc.returncode != 0:
        filter_stderr = filter_proc.stderr.read()
        return {"_error": True, "message": f"Filter failed: {filter_stderr}"}

    # Check analyze result
    if analyze_proc.returncode != 0:
        return {"_error": True, "message": f"Analysis failed: {stderr}"}

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as e:
        return {"_error": True, "message": f"Invalid analysis output: {e}"}

    # Add metadata
    result["resource"] = address_str
    result["transport"] = addr.type
    if addr.format_override:
        result["format"] = addr.format_override
    # Expose the sampling limit so callers/text formatting can clarify
    # that row counts are based on a sample, not full dataset cardinality.
    result["limit"] = limit

    return result


@click.command()
@click.argument("uri")
@click.option(
    "--limit",
    type=int,
    default=10000,
    help="Sample size for data inspection (default: 10000)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@pass_context
def inspect(ctx, uri, limit, output_format):
    """Inspect resources - discover capabilities or analyze data.

    Container inspection (lists available resources):
        jn inspect @api              # List HTTP API endpoints
        jn inspect @biomcp           # List MCP tools/resources
        jn inspect gmail://me        # List Gmail labels

    Data inspection (schema, stats, facets, samples):
        jn inspect data.csv                    # Inspect local file
        jn inspect @api/endpoint               # Inspect API data
        jn inspect @api/endpoint?gene=BRAF     # Inspect filtered data
        jn inspect gmail://me/INBOX            # Inspect Gmail messages

    Options:
        --limit N      Sample size for data inspection (default: 10000)
        --format json  Output as JSON instead of text
    """
    try:
        check_uv_available()

        # Determine if this is container or data inspection
        is_container = _is_container(uri)

        if is_container:
            # Container: list capabilities
            result = _inspect_container(uri)
        else:
            # Leaf: analyze data
            result = _inspect_data(ctx, uri, limit)

        # Check for errors
        if result.get("_error"):
            click.echo(
                f"Error: {result.get('message', 'Unknown error')}", err=True
            )
            sys.exit(1)

        # Output
        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            if is_container:
                click.echo(_format_container_text(result))
            else:
                click.echo(_format_data_text(result))

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
