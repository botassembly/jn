"""Address parsing for the universal addressability system.

This module implements parsing for the address syntax:
    address[~format][?parameters]

Where:
    - address: Base address (file, URL, @profile/component, @plugin, -)
    - ~format: Optional format override
    - ?parameters: Optional query string parameters
"""

from typing import Dict
from urllib.parse import parse_qs, unquote

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
    """
    # Handle empty/whitespace input
    if not raw or not raw.strip():
        raise ValueError("Address cannot be empty")

    raw = raw.strip()

    # Step 1: Check if this is a protocol URL
    # Protocol URLs contain :// and their query strings are part of the URL
    is_protocol_url = "://" in raw

    # Step 2: Extract JN parameters (everything after ?)
    # For protocol URLs, keep query string as part of the URL
    parameters: Dict[str, str] = {}
    if "?" in raw and not is_protocol_url:
        # Non-protocol: split on ? to get JN parameters
        addr_part, query_string = raw.split("?", 1)
        parameters = _parse_query_string(query_string)
    else:
        # Protocol URL: keep full URL with query string
        addr_part = raw

    # Step 3: Extract format override (everything after ~)
    format_override = None
    if "~" in addr_part and not is_protocol_url:
        # Only parse ~ for non-protocol addresses
        # Protocols can't have format overrides (they determine their own format)
        base, format_str = addr_part.rsplit("~", 1)  # rsplit to get last ~
        if not format_str:
            raise ValueError(f"Format override cannot be empty: {raw}")

        # Check for shorthand format (e.g., "table.grid")
        if "." in format_str:
            format_override, variant = format_str.split(".", 1)
            # Expand shorthand
            parameters.update(_expand_shorthand(format_override, variant))
        else:
            format_override = format_str
    else:
        base = addr_part

    # Step 4: Determine address type
    addr_type = _determine_type(base)

    # Step 5: Validate address
    _validate_address(base, format_override, parameters, addr_type)

    return Address(
        raw=raw,
        base=base,
        format_override=format_override,
        parameters=parameters,
        type=addr_type,
    )


def _parse_query_string(query_string: str) -> Dict[str, str]:
    """Parse URL query string into dict.

    Args:
        query_string: Query string without leading ?

    Returns:
        Dict of key-value pairs

    Examples:
        >>> _parse_query_string("key=value")
        {"key": "value"}

        >>> _parse_query_string("key1=value1&key2=value2")
        {"key1": "value1", "key2": "value2"}

        >>> _parse_query_string("delimiter=%3B")  # URL-encoded semicolon
        {"delimiter": ";"}
    """
    parsed = parse_qs(query_string, keep_blank_values=True)

    # Flatten single-item lists and URL-decode
    result = {}
    for key, values in parsed.items():
        if len(values) == 1:
            result[key] = unquote(values[0])
        else:
            # Multiple values for same key - keep as comma-separated
            result[key] = ",".join(unquote(v) for v in values)

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
