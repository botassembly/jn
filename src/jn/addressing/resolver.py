"""Address resolution - convert parsed addresses to plugins and configurations."""

from pathlib import Path
from typing import Dict, Optional, Tuple

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

    def __init__(self, plugin_dir: Path, cache_path: Optional[Path] = None):
        """Initialize resolver with plugin directory.

        Args:
            plugin_dir: Directory containing custom plugins
            cache_path: Optional path to plugin cache file
        """
        self.plugin_dir = plugin_dir
        self.cache_path = cache_path
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

        # Build configuration from parameters
        config = self._build_config(address.parameters, plugin_name)

        # Resolve URL and headers (for protocols/profiles)
        url, headers = self._resolve_url_and_headers(address)

        return ResolvedAddress(
            address=address,
            plugin_name=plugin_name,
            plugin_path=plugin_path,
            config=config,
            url=url,
            headers=headers,
        )

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
            namespace = address.base[1:].split("/")[0]  # Remove @ and get first part

            # Map known profile namespaces to plugins
            # Gmail profiles (@gmail/...) → gmail plugin
            # HTTP API profiles (@genomoncology/..., etc.) → http plugin
            # Future: MCP profiles (@mcp/...) → mcp plugin

            # Try to find plugin by namespace first
            try:
                return self._find_plugin_by_name(namespace)
            except AddressResolutionError:
                # Namespace doesn't match a plugin name
                # Default to HTTP plugin for API profiles
                return self._find_plugin_by_name("http")

        # Case 4: Direct plugin reference
        if address.type == "plugin":
            plugin_name = address.base[1:]  # Remove @ prefix
            return self._find_plugin_by_name(plugin_name)

        # Case 5: Stdio - default to NDJSON if no override
        if address.type == "stdio":
            if mode == "write":
                # Stdout defaults to NDJSON
                return self._find_plugin_by_format("ndjson")
            else:
                # Stdin defaults to NDJSON
                return self._find_plugin_by_format("ndjson")

        # Case 6: File - auto-detect from extension
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

        raise AddressResolutionError(
            f"Plugin not found for format: {format_name}. "
            f"Available plugins: {', '.join(sorted(self._plugins.keys()))}"
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

        raise AddressResolutionError(
            f"Plugin not found for protocol: {protocol}. "
            f"Available plugins: {', '.join(sorted(self._plugins.keys()))}"
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

        raise AddressResolutionError(
            f"No plugin found for: {source}. "
            f"Consider using format override: {source}~<format>"
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
            # Try to convert to appropriate type
            if value.lower() in ("true", "false"):
                # Boolean
                config[key] = value.lower() == "true"
            elif self._is_number(value):
                # Numeric (int or float)
                if "." in value or "e" in value.lower():
                    config[key] = float(value)
                else:
                    config[key] = int(value)
            else:
                # String
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
        self, address: Address
    ) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
        """Resolve URL and headers for address.

        Args:
            address: Parsed address

        Returns:
            Tuple of (url, headers)

        Raises:
            AddressResolutionError: If resolution fails
        """
        # Protocol URLs: use base directly
        if address.type == "protocol":
            # For protocols, the base is already a URL
            # Parameters are part of the URL or will be passed to the plugin
            return address.base, None

        # Profile references: resolve via appropriate profile system
        if address.type == "profile":
            # Determine which profile system based on namespace
            namespace = address.base[1:].split("/")[0]

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

        # File/stdio/plugin: no URL
        return None, None
