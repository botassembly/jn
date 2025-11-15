"""Address parsing for the universal addressability system.

This module implements parsing for the address syntax:
    address[~format][?parameters]

Where:
    - address: Base address (file, URL, @profile/component, @plugin, -)
    - ~format: Optional format override
    - ?parameters: Optional query string parameters
"""

from typing import Dict
from urllib.parse import unquote

from .types import Address, AddressType


def parse_address(raw: str) -> Address:
    """Parse address[~format][?parameters] syntax.

    This is the main entry point for address parsing. It handles all
    address types and operators.

    Args:
        raw: Raw address string from user

    Returns:
        Parsed Address object

    Examples:
        >>> parse_address("file.csv")
        Address(base="file.csv", format_override=None, parameters={}, type="file")

        >>> parse_address("file.txt~csv")
        Address(base="file.txt", format_override="csv", parameters={}, type="file")

        >>> parse_address("-~csv?delimiter=;")
        Address(base="-", format_override="csv", parameters={"delimiter": ";"}, type="stdio")

        >>> parse_address("@api/source?limit=100")
        Address(base="@api/source", format_override=None, parameters={"limit": "100"}, type="profile")

        >>> parse_address("-~table.grid")
        Address(base="-", format_override="table", parameters={"tablefmt": "grid"}, type="stdio")

        >>> parse_address("file.csv.gz")
        Address(base="file.csv", compression="gz", type="file")
    """
    # Handle empty/whitespace input
    if not raw or not raw.strip():
        raise ValueError("Address cannot be empty")

    raw = raw.strip()

    # Step 1: Check if this is a protocol URL
    # Protocol URLs contain :// and their query strings are part of the URL
    is_protocol_url = "://" in raw

    # Step 2: Extract format override FIRST (before parameters)
    # Format override syntax: address~format?params
    # For protocol URLs: https://example.com/data?token=xyz~csv?delimiter=,
    #   base = https://example.com/data?token=xyz
    #   format = csv
    #   params = delimiter=,
    format_override = None
    if "~" in raw:
        # Split on ~ to separate base from format override
        base_part, format_part = raw.rsplit("~", 1)  # rsplit to get last ~

        # Extract parameters from format part if present
        if "?" in format_part:
            format_str, query_string = format_part.split("?", 1)
            parameters = _parse_query_string(query_string)
        else:
            format_str = format_part
            parameters = {}

        # Special case: "~?params" → no format override, only JN parameters.
        if not format_str and parameters:
            format_override = None
        else:
            if not format_str:
                raise ValueError(f"Format override cannot be empty: {raw}")

            # Check for shorthand format (e.g., "table.grid")
            if "." in format_str:
                format_override, variant = format_str.split(".", 1)
                # Expand shorthand
                parameters.update(_expand_shorthand(format_override, variant))
            else:
                format_override = format_str

        base = base_part
    else:
        # No format override
        # For non-protocol: extract JN parameters
        # For protocol: keep query string as part of URL
        if "?" in raw and not is_protocol_url:
            # Non-protocol: extract JN parameters
            base, query_string = raw.split("?", 1)
            parameters = _parse_query_string(query_string)
        else:
            # Protocol or no parameters
            base = raw
            parameters = {}

    # Step 4: Detect and strip compression extension
    compression = None
    compression_formats = {".gz", ".bz2", ".xz"}
    for ext in compression_formats:
        if base.endswith(ext):
            compression = ext[1:]  # Remove leading dot
            base = base[: -len(ext)]  # Strip extension from base
            break

    # Step 5: Determine address type
    addr_type = _determine_type(base)

    # Step 6: Validate address
    _validate_address(base, format_override, parameters, addr_type)

    return Address(
        raw=raw,
        base=base,
        format_override=format_override,
        parameters=parameters,
        type=addr_type,
        compression=compression,
    )


def _parse_query_string(query_string: str) -> Dict[str, str]:
    """Parse URL query string into dict.

    Supports both standard ``key=value`` pairs and concise filter syntax:

    - ``field=value``              → equality filter/config
    - ``field>value``              → greater-than filter
    - ``field>=value``             → greater-than-or-equal filter
    - ``field%3E%3D=value``        → same as ``field>=value`` (URL-encoded)

    Multiple values for the same key are joined with commas, preserving the
    existing semantics relied on by ``separate_config_and_filters()``.
    """
    if not query_string:
        return {}

    # Accumulate possibly multiple values per key
    multi: Dict[str, list[str]] = {}

    # Split on '&' first; we handle decoding and operators explicitly
    for part in query_string.split("&"):
        if not part:
            continue

        # Handle unencoded 2-character operators like "salary>=75000"
        # before introducing a key/value split. We only examine the raw
        # segment so that encoded forms (%3E%3D) are handled separately.
        handled = False
        for op in (">=", "<=", "!="):
            if op in part:
                field_raw, value_raw = part.split(op, 1)
                key = f"{unquote(field_raw)}{op}"
                value = unquote(value_raw)
                multi.setdefault(key, []).append(value)
                handled = True
                break

        if handled:
            continue

        # Fallback: standard key=value parsing (with URL-decoded pieces).
        if "=" in part:
            raw_key, raw_value = part.split("=", 1)
        else:
            raw_key, raw_value = part, ""

        key = unquote(raw_key)
        value = unquote(raw_value)

        # Handle concise operator syntax like "salary>75000" (no '=').
        if not raw_value and any(sym in key for sym in (">", "<", "!")):
            for op in (">=", "<=", "!=", ">", "<"):
                if op in key:
                    field, tail = key.split(op, 1)
                    if tail:
                        key = f"{field}{op}"
                        value = tail
                    break

        multi.setdefault(key, []).append(value)

    # Flatten to single dict, joining multi-values with "||" so that
    # downstream filtering can treat repeated parameters as explicit
    # OR blocks when desired.
    result: Dict[str, str] = {}
    for key, values in multi.items():
        if len(values) == 1:
            result[key] = values[0]
        else:
            result[key] = "||".join(values)

    return result


def _expand_shorthand(format_name: str, variant: str) -> Dict[str, str]:
    """Expand shorthand format variants into parameters.

    Shorthand syntax: format.variant → format + parameters

    Args:
        format_name: Base format (e.g., "table")
        variant: Variant name (e.g., "grid")

    Returns:
        Dict of expanded parameters

    Examples:
        >>> _expand_shorthand("table", "grid")
        {"tablefmt": "grid"}

        >>> _expand_shorthand("table", "markdown")
        {"tablefmt": "markdown"}
    """
    if format_name == "table":
        # table.grid → table?tablefmt=grid
        return {"tablefmt": variant}

    # For other formats, no expansion (just use variant as-is)
    # This allows future extensions like: json.compact, csv.unix, etc.
    return {}


def _determine_type(base: str) -> AddressType:
    """Determine address type from base address.

    Args:
        base: Base address string

    Returns:
        Address type

    Examples:
        >>> _determine_type("-")
        "stdio"

        >>> _determine_type("@namespace/component")
        "profile"

        >>> _determine_type("@plugin")
        "plugin"

        >>> _determine_type("http://example.com")
        "protocol"

        >>> _determine_type("file.csv")
        "file"
    """
    if base == "-" or base == "stdin" or base == "stdout":
        return "stdio"
    elif base.startswith("@"):
        if "/" in base:
            return "profile"  # @namespace/component
        else:
            return "plugin"  # @plugin
    elif "://" in base:
        return "protocol"  # http://, s3://, gmail://
    else:
        return "file"  # Filesystem path


def _validate_address(
    base: str,
    format_override: str | None,
    parameters: Dict[str, str],
    addr_type: AddressType,
) -> None:
    """Validate parsed address components.

    Args:
        base: Base address
        format_override: Format override (if any)
        parameters: Parameters dict
        addr_type: Address type

    Raises:
        ValueError: If address is invalid
    """
    # Base validation
    if not base:
        raise ValueError("Base address cannot be empty")

    # Profile validation
    if addr_type == "profile":
        if not base.startswith("@"):
            raise ValueError(f"Profile reference must start with @: {base}")
        parts = base[1:].split("/")
        if len(parts) != 2:
            raise ValueError(
                f"Profile reference must be @namespace/component: {base}"
            )
        namespace, component = parts
        if not namespace or not component:
            raise ValueError(
                f"Profile namespace and component cannot be empty: {base}"
            )

    # Plugin validation
    if addr_type == "plugin":
        if not base.startswith("@"):
            raise ValueError(f"Plugin reference must start with @: {base}")
        plugin_name = base[1:]
        if not plugin_name:
            raise ValueError(f"Plugin name cannot be empty: {base}")
        if "/" in plugin_name:
            raise ValueError(
                f"Plugin reference cannot contain /: {base}. "
                f"Did you mean a profile reference?"
            )

    # Protocol validation
    if addr_type == "protocol":
        if "://" not in base:
            raise ValueError(f"Protocol address must contain ://: {base}")
        protocol = base.split("://")[0]
        if not protocol:
            raise ValueError(f"Protocol cannot be empty: {base}")

    # Format override validation
    if format_override is not None:
        if not format_override:
            raise ValueError("Format override cannot be empty")
        # Format names should be simple identifiers
        if "/" in format_override or "@" in format_override:
            raise ValueError(
                f"Invalid format name: {format_override}. "
                f"Format names should be simple identifiers like 'csv', 'json', 'table'"
            )
