"""Address types for the universal addressability system."""

from dataclasses import dataclass, field
from typing import Dict, Literal, Optional

AddressType = Literal["file", "protocol", "profile", "plugin", "stdio"]


@dataclass
class Address:
    """Parsed address with format override and parameters.

    The Address represents a parsed user input following the syntax:
        address[~format][?parameters]

    Examples:
        "data.csv" → Address(base="data.csv", format_override=None, parameters={})
        "data.txt~csv" → Address(base="data.txt", format_override="csv", parameters={})
        "-~csv?delimiter=;" → Address(base="-", format_override="csv", parameters={"delimiter": ";"})
        "@api/source?limit=100" → Address(base="@api/source", format_override=None, parameters={"limit": "100"})
    """

    raw: str
    """Original address string provided by user."""

    base: str
    """Base address without format override or parameters.

    Examples: "file.csv", "http://example.com", "@profile/component", "@plugin", "-"
    """

    format_override: Optional[str] = None
    """Format override specified with ~ operator.

    Examples: "csv", "json", "table"
    Note: Shorthand variants are expanded by parser (e.g., "table.grid" → "table")
    """

    parameters: Dict[str, str] = field(default_factory=dict)
    """Query string parameters from ? operator.

    Examples: {"delimiter": ";", "indent": "4"}
    Note: May include expanded shorthand parameters (e.g., {"tablefmt": "grid"})
    """

    type: AddressType = "file"
    """Type of address for resolution strategy.

    - file: Filesystem path (default)
    - protocol: URL with protocol (http://, s3://, gmail://)
    - profile: Profile reference (@namespace/component)
    - plugin: Direct plugin reference (@plugin)
    - stdio: Stdin/stdout (-)
    """

    def __str__(self) -> str:
        """Human-readable representation."""
        parts = [self.base]
        if self.format_override:
            parts.append(f"~{self.format_override}")
        if self.parameters:
            param_str = "&".join(
                f"{k}={v}" for k, v in self.parameters.items()
            )
            parts.append(f"?{param_str}")
        return "".join(parts)


@dataclass
class ResolvedAddress:
    """Address resolved to plugin and configuration.

    After parsing an Address, the resolver determines which plugin to use
    and what configuration to pass to it. This class represents the result
    of that resolution process.
    """

    address: Address
    """Original parsed address."""

    plugin_name: str
    """Name of the plugin to use (e.g., "csv_", "http_", "table_")."""

    plugin_path: str
    """Full path to the plugin script."""

    config: Dict[str, any] = field(default_factory=dict)
    """Plugin configuration built from parameters.

    Examples:
        {"delimiter": ";"}  # For CSV plugin
        {"indent": 4}       # For JSON plugin
        {"tablefmt": "grid", "maxcolwidths": 20}  # For table plugin
    """

    url: Optional[str] = None
    """Resolved URL for protocol/profile addresses.

    For protocol addresses: The URL itself (may be modified)
    For profile addresses: URL built from profile config + parameters
    For file/stdio: None
    """

    headers: Optional[Dict[str, str]] = None
    """HTTP headers for protocol/profile requests (HTTP plugin only)."""

    def __str__(self) -> str:
        """Human-readable representation."""
        parts = [f"Plugin: {self.plugin_name}"]
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.config:
            parts.append(f"Config: {self.config}")
        return ", ".join(parts)
