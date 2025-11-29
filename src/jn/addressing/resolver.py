"""Address resolution - convert parsed addresses to plugins and configurations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..plugins.discovery import (
    PluginMetadata,
    get_cached_plugins_with_fallback,
    get_plugin_by_name,
)
from ..plugins.registry import build_registry
from ..profiles.http import ProfileError as HTTPProfileError
from ..profiles.http import resolve_profile_reference
from .types import Address, ResolvedAddress


class AddressResolutionError(Exception):
    """Error resolving address to plugin."""

    pass


@dataclass
class ExecutionStage:
    """Represents a single stage in a pipeline execution plan.

    Attributes:
        plugin_path: Path to plugin script
        mode: Execution mode ("read", "write", or "raw")
        config: Configuration parameters for plugin
        url: Optional URL argument for plugin
        headers: Optional headers for HTTP requests
    """

    plugin_path: str
    mode: str
    config: Dict[str, any]
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class AddressResolver:
    """Resolve parsed addresses to plugins and configurations.

    The resolver takes a parsed Address and determines:
    1. Which plugin to use (based on format override, protocol, profile, or extension)
    2. What configuration to pass to the plugin
    3. What URL to use (for protocols/profiles)
    4. What headers to use (for HTTP requests)

    Example usage:
        # Create resolver
        resolver = AddressResolver(plugin_dir, cache_path)

        # Resolve address
        addr = parse_address("data.txt~csv?delimiter=;")
        resolved = resolver.resolve(addr, mode="read")

        # Use resolved address
        run_plugin(resolved.plugin_path, resolved.config, mode="read")
    """

    def __init__(
        self,
        plugin_dir: Path,
        cache_path: Optional[Path] = None,
        home_dir: Optional[Path] = None,
    ):
        """Initialize resolver with plugin directory.

        Args:
            plugin_dir: Directory containing custom plugins
            cache_path: Optional path to plugin cache file
            home_dir: JN home directory (overrides $JN_HOME)
        """
        self.plugin_dir = plugin_dir
        self.cache_path = cache_path
        self.home_dir = home_dir
        self._plugins: Optional[Dict[str, PluginMetadata]] = None
        self._registry = None

    def _ensure_plugins_loaded(self) -> None:
        """Lazily load plugins and registry on first use."""
        if self._plugins is None:
            self._plugins = get_cached_plugins_with_fallback(
                self.plugin_dir, self.cache_path
            )
            self._registry = build_registry(self._plugins)

    def resolve(self, address: Address, mode: str = "read") -> ResolvedAddress:
        """Resolve address to plugin and configuration.

        Args:
            address: Parsed address to resolve
            mode: Plugin mode ("read" or "write")

        Returns:
            ResolvedAddress with plugin info and configuration

        Raises:
            AddressResolutionError: If address cannot be resolved
        """
        self._ensure_plugins_loaded()

        # Determine plugin
        plugin_name, plugin_path = self._find_plugin(address, mode)

        # Check if this is a protocol-role plugin
        plugin = self._plugins.get(plugin_name)
        is_protocol_plugin = plugin and plugin.role == "protocol"

        # Build configuration from parameters
        # For protocol plugins, parameters stay in URL (not extracted to config)
        # This allows self-contained plugins to handle their own parameter parsing
        # Exception: glob addresses - parameters are passed via config since there's no URL
        if is_protocol_plugin and address.type != "glob":
            config = {}
        else:
            config = self._build_config(address.parameters, plugin_name)

        # Resolve URL and headers (for protocols/profiles)
        url, headers = self._resolve_url_and_headers(address, plugin_name)

        return ResolvedAddress(
            address=address,
            plugin_name=plugin_name,
            plugin_path=plugin_path,
            config=config,
            url=url,
            headers=headers,
        )

    def plan_execution(
        self, address: Address, mode: str = "read"
    ) -> List[ExecutionStage]:
        """Plan execution stages for address.

        For most addresses, returns a single stage. For protocol URLs with format
        extensions (e.g., https://example.com/data.xlsx), returns two stages:
        1. Protocol stage (raw mode) - fetches bytes
        2. Format stage (read mode) - parses bytes

        For compressed files (.gz, .bz2, .xz), inserts decompression stage:
        1. Protocol/file stage (raw mode) - fetches/reads bytes
        2. Decompression stage (raw mode) - decompresses bytes
        3. Format stage (read mode) - parses decompressed bytes

        Args:
            address: Parsed address to resolve
            mode: Plugin mode ("read" or "write")

        Returns:
            List of execution stages (1-3 stages)

        Raises:
            AddressResolutionError: If address cannot be resolved
        """
        self._ensure_plugins_loaded()

        # Stdio without format override: pass-through (no stage). Caller should
        # stream stdin directly to the consumer (e.g., writer or stdout).
        if (
            address.type == "stdio"
            and not address.format_override
            and mode == "read"
        ):
            return []

        # Build base stages (protocol + format, or single stage)
        stages = []

        # Only consider 2-stage for protocol URLs in read mode
        if mode == "read" and address.type == "protocol":
            # Check if registry suggests 2-stage plan OR if there's explicit format override
            # Note: We use the original base (without .gz) for format detection
            if address.format_override:
                # Explicit format override: protocol (raw) → format (read)
                # Extract protocol from URL
                protocol = address.base.split("://")[0]
                proto_name = f"{protocol}_"

                # Verify protocol plugin exists
                if proto_name not in self._plugins:
                    # Try common protocols
                    if protocol in ("http", "https"):
                        proto_name = "http_"
                    else:
                        raise AddressResolutionError(
                            f"Protocol plugin not found: {protocol}"
                        )

                # Get format plugin name
                fmt_name = f"{address.format_override}_"
                if fmt_name not in self._plugins:
                    # Try without underscore
                    fmt_name = address.format_override
                    if fmt_name not in self._plugins:
                        raise AddressResolutionError(
                            f"Format plugin not found: {address.format_override}"
                        )

                plan = [proto_name, fmt_name]
            else:
                # Auto-detect format from URL
                plan = self._registry.plan_for_read(
                    address.base, self._plugins
                )

            if len(plan) == 2:
                # Two-stage: protocol (raw) → format (read)
                proto_name, fmt_name = plan
                proto_plugin = self._plugins[proto_name]
                fmt_plugin = self._plugins[fmt_name]

                # Resolve URL and headers
                # Reconstruct full URL with compression extension if needed
                if address.compression:
                    # Add compression extension back: base + .gz
                    full_url = f"{address.base}.{address.compression}"
                else:
                    full_url = address.base

                # Create temporary address with full URL for resolution
                temp_addr = Address(
                    raw=full_url,
                    base=full_url,
                    format_override=None,  # Don't include format in URL
                    parameters={},  # Don't include params in URL
                    type="protocol",
                )
                url, headers = self._resolve_url_and_headers(
                    temp_addr, proto_name
                )

                # Protocol stage: raw mode, URL as argument
                protocol_stage = ExecutionStage(
                    plugin_path=proto_plugin.path,
                    mode="raw",
                    config={},
                    url=url,
                    headers=headers,
                )

                # Format stage: read mode, stdin from protocol/decompression
                # Build config from address parameters
                format_config = self._build_config(
                    address.parameters, fmt_name
                )
                format_stage = ExecutionStage(
                    plugin_path=fmt_plugin.path,
                    mode="read",
                    config=format_config,
                    url=None,
                    headers=None,
                )

                stages = [protocol_stage, format_stage]
            else:
                # Single stage - resolve normally
                resolved = self.resolve(address, mode)
                stage = ExecutionStage(
                    plugin_path=resolved.plugin_path,
                    mode=mode,
                    config=resolved.config,
                    url=resolved.url,
                    headers=resolved.headers,
                )
                stages = [stage]
        else:
            # Single-stage execution
            resolved = self.resolve(address, mode)
            stage = ExecutionStage(
                plugin_path=resolved.plugin_path,
                mode=mode,
                config=resolved.config,
                url=resolved.url,
                headers=resolved.headers,
            )
            stages = [stage]

        # Insert decompression stage if compression detected (only in read mode)
        # Skip for glob addresses - glob plugin handles compression internally
        if mode == "read" and address.compression and address.type != "glob":
            # Find decompression plugin
            try:
                decomp_name = f"{address.compression}_"
                decomp_plugin = self._plugins.get(decomp_name)
                if not decomp_plugin:
                    raise AddressResolutionError(
                        f"Decompression plugin not found: {address.compression}. "
                        f"Available plugins: {', '.join(sorted(self._plugins.keys()))}"
                    )

                decomp_stage = ExecutionStage(
                    plugin_path=decomp_plugin.path,
                    mode="raw",
                    config={},
                    url=None,
                    headers=None,
                )

                # Insert decompression stage after first stage (protocol/file read)
                # Pipeline becomes: fetch/read (raw) → decompress (raw) → parse (read)
                if len(stages) >= 2:
                    # Protocol + format: insert decomp between them
                    stages = [stages[0], decomp_stage, stages[1]]
                elif len(stages) == 1:
                    # Single stage: add decomp before it
                    stages = [decomp_stage, stages[0]]
            except KeyError:
                raise AddressResolutionError(
                    f"Decompression plugin not found: {address.compression}"
                )

        return stages

    def _find_plugin(self, address: Address, mode: str) -> Tuple[str, str]:
        """Find plugin for address.

        Args:
            address: Parsed address
            mode: Plugin mode ("read" or "write")

        Returns:
            Tuple of (plugin_name, plugin_path)

        Raises:
            AddressResolutionError: If plugin not found
        """
        # Case 1: Explicit format override
        if address.format_override:
            return self._find_plugin_by_format(address.format_override)

        # Case 2: Protocol URL
        if address.type == "protocol":
            return self._find_plugin_by_protocol(address.base)

        # Case 3: Profile reference
        if address.type == "profile":
            # Determine plugin from profile namespace
            # Extract namespace: @namespace/component → namespace
            namespace = address.base[1:].split("/")[
                0
            ]  # Remove @ and get first part

            # Map known profile namespaces to plugins
            # Gmail profiles (@gmail/...) → gmail plugin
            # HTTP API profiles (@genomoncology/..., etc.) → http plugin
            # Future: MCP profiles (@mcp/...) → mcp plugin

            # Try to find plugin by namespace
            try:
                return self._find_plugin_by_name(namespace)
            except AddressResolutionError:
                # Check if any protocol plugin has profiles for this namespace
                # This allows protocol plugins like duckdb to manage profile namespaces
                import os
                from pathlib import Path

                # Use home_dir from context if provided, otherwise fall back to env/default
                if self.home_dir:
                    jn_home = self.home_dir
                else:
                    jn_home = Path(os.getenv("JN_HOME", Path.home() / ".jn"))
                project_profiles = Path.cwd() / ".jn" / "profiles"

                # Check each protocol plugin's profile directory
                for plugin_name, plugin_meta in self._plugins.items():
                    if plugin_meta.role == "protocol":
                        # Derive profile type from plugin name (e.g., duckdb_ -> duckdb)
                        profile_type = plugin_name.rstrip("_")

                        # Check if this plugin has a profile namespace directory
                        for base_dir in [
                            project_profiles,
                            jn_home / "profiles",
                        ]:
                            ns_dir = base_dir / profile_type / namespace
                            if ns_dir.exists():
                                return plugin_name, plugin_meta.path
                # Default to HTTP plugin for API profiles
                return self._find_plugin_by_name("http_")

        # Case 4: Direct plugin reference
        if address.type == "plugin":
            plugin_name = address.base[1:]  # Remove @ prefix

            # If a matching HTTP profile exists for this name, treat as a
            # profile container and route through the HTTP plugin instead of
            # a direct plugin reference.
            try:
                from ..profiles.http import find_profile_paths  # lazy import
            except ImportError:
                find_profile_paths = None  # type: ignore[assignment]

            if find_profile_paths is not None:
                for search_dir in find_profile_paths():
                    api_dir = search_dir / plugin_name
                    if api_dir.exists():
                        # Use HTTP plugin for container handling
                        return self._find_plugin_by_name("http_")

            return self._find_plugin_by_name(plugin_name)

        # Case 5: Stdio - default to NDJSON if no override
        if address.type == "stdio":
            if mode == "write":
                # Stdout defaults to NDJSON
                return self._find_plugin_by_format("ndjson")
            else:
                # Stdin defaults to NDJSON
                return self._find_plugin_by_format("ndjson")

        # Case 6: Glob pattern - use glob plugin
        if address.type == "glob":
            return self._find_plugin_by_name("glob_")

        # Case 7: File - auto-detect from extension
        if address.type == "file":
            return self._find_plugin_by_pattern(address.base)

        raise AddressResolutionError(
            f"Cannot determine plugin for address: {address.raw}"
        )

    def _find_plugin_by_format(self, format_name: str) -> Tuple[str, str]:
        """Find plugin by format name.

        Args:
            format_name: Format name (csv, json, table, etc.)

        Returns:
            Tuple of (plugin_name, plugin_path)

        Raises:
            AddressResolutionError: If plugin not found
        """
        # Try exact match first
        plugin = get_plugin_by_name(format_name, self._plugins)
        if plugin:
            return plugin.name, plugin.path

        # Try with underscore suffix
        plugin = get_plugin_by_name(f"{format_name}_", self._plugins)
        if plugin:
            return plugin.name, plugin.path

        # Check if it's a common format plugin in bundled plugins
        # Look for plugins in formats/ subdirectory
        for name, meta in self._plugins.items():
            if (
                name == format_name
                or name == f"{format_name}_"
                or f"/formats/{format_name}" in meta.path
            ):
                return meta.name, meta.path

        # Build list of available format plugins (exclude protocols, filters, etc.)
        format_plugins = sorted(
            [
                name.rstrip("_")
                for name, meta in self._plugins.items()
                if (
                    getattr(meta, "role", None) == "format"
                    or "/formats/" in meta.path
                )
            ]
        )

        raise AddressResolutionError(
            f"Plugin not found for format: {format_name}\n"
            f"  Available format plugins: {', '.join(format_plugins)}\n"
            f"  Usage: source~{format_name} or source?format={format_name}"
        )

    def _find_plugin_by_protocol(self, url: str) -> Tuple[str, str]:
        """Find plugin by protocol.

        Args:
            url: URL with protocol (http://, s3://, gmail://)

        Returns:
            Tuple of (plugin_name, plugin_path)

        Raises:
            AddressResolutionError: If plugin not found
        """
        if "://" not in url:
            raise AddressResolutionError(f"Invalid protocol URL: {url}")

        protocol = url.split("://")[0]

        # Try to find plugin by protocol name
        # Try exact match first
        plugin = get_plugin_by_name(protocol, self._plugins)
        if plugin:
            return plugin.name, plugin.path

        # Try with underscore suffix
        plugin = get_plugin_by_name(f"{protocol}_", self._plugins)
        if plugin:
            return plugin.name, plugin.path

        # Check if any plugin matches the URL pattern
        matched_name = self._registry.match(url)
        if matched_name and matched_name in self._plugins:
            plugin = self._plugins[matched_name]
            return plugin.name, plugin.path

        # Build helpful error message with examples
        common_protocols = {
            "duckdb": "duckdb://path/to/file.duckdb?query=SELECT * FROM table",
            "sqlite": "sqlite://path/to/file.db?query=SELECT * FROM table",
            "postgres": "postgres://host/db?query=SELECT * FROM table",
            "s3": "s3://bucket/key",
            "ftp": "ftp://host/path",
        }

        # List available protocol plugins
        protocol_plugins = sorted(
            [
                name.rstrip("_")
                for name, meta in self._plugins.items()
                if (
                    getattr(meta, "role", None) == "protocol"
                    or "/protocols/" in meta.path
                    or any("://" in str(m) for m in (meta.matches or []))
                )
            ]
        )

        example = common_protocols.get(protocol, f"{protocol}://...")

        raise AddressResolutionError(
            f"Plugin not found for protocol: {protocol}\n"
            f"  Example usage: {example}\n"
            f"  Available protocol plugins: {', '.join(protocol_plugins)}"
        )

    def _find_plugin_by_name(self, name: str) -> Tuple[str, str]:
        """Find plugin by exact name.

        Args:
            name: Plugin name

        Returns:
            Tuple of (plugin_name, plugin_path)

        Raises:
            AddressResolutionError: If plugin not found
        """
        # Try exact match
        plugin = get_plugin_by_name(name, self._plugins)
        if plugin:
            return plugin.name, plugin.path

        # Try with underscore suffix
        plugin = get_plugin_by_name(f"{name}_", self._plugins)
        if plugin:
            return plugin.name, plugin.path

        raise AddressResolutionError(
            f"Plugin not found: {name}. "
            f"Available plugins: {', '.join(sorted(self._plugins.keys()))}"
        )

    def _find_plugin_by_pattern(self, source: str) -> Tuple[str, str]:
        """Find plugin by pattern matching (file extension).

        Args:
            source: Source path

        Returns:
            Tuple of (plugin_name, plugin_path)

        Raises:
            AddressResolutionError: If plugin not found
        """
        matched_name = self._registry.match(source)
        if matched_name and matched_name in self._plugins:
            plugin = self._plugins[matched_name]
            return plugin.name, plugin.path

        # Build helpful error message with suggestions
        from pathlib import Path

        ext = Path(source).suffix.lower()

        suggestions = []
        if ext in (".txt", ".dat", ".data"):
            suggestions.append(f"  • Try CSV format: {source}~csv")
            suggestions.append(
                f"  • Or with delimiter: {source}~csv?delimiter=\\t"
            )
        elif ext in (".db", ".sqlite", ".sqlite3"):
            suggestions.append(
                f"  • Try SQLite: sqlite://{source}?query=SELECT * FROM table_name"  # noqa: S608
            )
        elif ext in (".duckdb", ".ddb"):
            suggestions.append(
                f"  • Try DuckDB: duckdb://{source}?query=SELECT * FROM table_name"  # noqa: S608
            )
        elif not ext:
            suggestions.append(
                f"  • Add file extension or use format override: {source}~csv"
            )
        else:
            suggestions.append(f"  • Use format override: {source}~<format>")
            suggestions.append(f"  • Example: {source}~csv or {source}~json")

        suggestion_text = "\n" + "\n".join(suggestions) if suggestions else ""

        raise AddressResolutionError(
            f"No plugin found for: {source}{suggestion_text}"
        )

    def _build_config(
        self, parameters: Dict[str, str], plugin_name: str
    ) -> Dict[str, any]:
        """Build plugin configuration from parameters.

        Maps parameter names to plugin-specific config keys.

        Args:
            parameters: Query string parameters
            plugin_name: Name of plugin

        Returns:
            Configuration dict for plugin

        Examples:
            CSV plugin:
                {"delimiter": ";", "header": "false"} → {"delimiter": ";", "header": False}

            JSON plugin:
                {"indent": "4"} → {"indent": 4}

            Table plugin:
                {"tablefmt": "grid", "maxcolwidths": "20"} → {"tablefmt": "grid", "maxcolwidths": 20}
        """
        if not parameters:
            return {}

        config = {}

        # Copy all parameters to config
        # Plugins will handle their own parameter validation
        for key, value in parameters.items():
            # Try to convert to appropriate type conservatively; defer strict
            # validation to the plugin. Avoid raising here to keep CLI errors
            # accurate (writer/reader errors vs. address syntax errors).
            try:
                low = value.lower()
            except AttributeError:
                low = value

            if isinstance(value, str) and low in ("true", "false"):
                config[key] = low == "true"
                continue

            # Treat typical numeric literals; special tokens (nan/inf) remain strings
            if (
                isinstance(value, str)
                and self._is_number(value)
                and low not in ("nan", "inf", "+inf", "-inf")
            ):
                try:
                    if "." in value or "e" in low:
                        config[key] = float(value)
                    else:
                        config[key] = int(value)
                except ValueError:
                    # Leave as string if conversion fails
                    config[key] = value
                continue

            # Default: string
            config[key] = value

        return config

    def _is_number(self, value: str) -> bool:
        """Check if string represents a number (int, float, or scientific notation).

        Args:
            value: String to check

        Returns:
            True if value is a valid number

        Examples:
            >>> _is_number("123")
            True
            >>> _is_number("-456")
            True
            >>> _is_number("3.14")
            True
            >>> _is_number("-2.5")
            True
            >>> _is_number("1e6")
            True
            >>> _is_number("abc")
            False
        """
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _resolve_url_and_headers(
        self, address: Address, plugin_name: str
    ) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
        """Resolve URL and headers for address.

        Args:
            address: Parsed address
            plugin_name: Name of the resolved plugin

        Returns:
            Tuple of (url, headers)

        Raises:
            AddressResolutionError: If resolution fails
        """
        # Protocol URLs: use base directly (re-attaching compression
        # extension when present so that URLs like *.gz resolve correctly).
        if address.type == "protocol":
            url = address.base
            if getattr(address, "compression", None):
                url = f"{url}.{address.compression}"
            return url, None

        # Profile references: resolve via appropriate profile system
        if address.type == "profile":
            # Determine which profile system based on namespace
            raw_ref = address.base
            parts = raw_ref[1:].split("/")  # Strip leading '@'
            namespace = parts[0]

            # Special case: bare '@name' (container reference)
            # If an HTTP profile exists for this namespace, route through the
            # HTTP plugin by returning the raw reference ('@name') as the URL.
            # This allows the HTTP plugin to emit a container listing.
            if len(parts) == 1:
                try:
                    from ..profiles.http import (
                        find_profile_paths,
                    )  # lazy import
                except ImportError:
                    find_profile_paths = None  # type: ignore[assignment]

                if find_profile_paths is not None:
                    for search_dir in find_profile_paths():
                        api_dir = search_dir / namespace
                        if api_dir.exists():
                            # Hand raw '@name' to the HTTP plugin
                            return raw_ref, None

            # Check if this profile is managed by a protocol plugin (like duckdb)
            # Protocol plugins handle profile resolution internally
            plugin = self._plugins.get(plugin_name)
            if (
                plugin
                and plugin.role == "protocol"
                and plugin_name not in ["http_", "gmail_"]
            ):
                # Pass the full address (including parameters) to the plugin for internal resolution
                return str(address), None

            # Gmail profiles
            if namespace == "gmail":
                try:
                    from ..profiles.gmail import (
                        GmailProfileError,
                        resolve_gmail_reference,
                    )

                    url = resolve_gmail_reference(
                        address.base, address.parameters or None
                    )
                    return url, None  # Gmail doesn't use headers
                except GmailProfileError as e:
                    raise AddressResolutionError(
                        f"Gmail profile resolution failed: {e}"
                    )

            # HTTP API profiles (default)
            try:
                url, headers = resolve_profile_reference(
                    address.base, address.parameters or None
                )
                return url, headers
            except HTTPProfileError as e:
                raise AddressResolutionError(f"Profile resolution failed: {e}")

        # Check if this is a protocol-role plugin (e.g., shell commands)
        # Even if parsed as type="file", protocol-role plugins should get URL set
        plugin = self._plugins.get(plugin_name)
        if plugin and plugin.role == "protocol":
            # Return full address (base + parameters) as URL
            # This allows shell commands like "ls?path=/tmp" to work without "shell://" prefix
            return str(address), None

        # File/stdio/plugin: no URL
        return None, None
