"""Function introspection utilities for determining config parameters."""

import importlib.util
import inspect
import sys
from typing import Callable, List, Optional


def load_plugin_function(
    plugin_path: str, function_name: str = "reads"
) -> Optional[Callable]:
    """Load a specific function from a plugin file.

    Args:
        plugin_path: Path to plugin .py file
        function_name: Name of function to load (default: "reads")

    Returns:
        Function object, or None if not found
    """
    try:
        # Load module from path
        spec = importlib.util.spec_from_file_location(
            "plugin_module", plugin_path
        )
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules["plugin_module"] = module
        spec.loader.exec_module(module)

        # Get function
        func = getattr(module, function_name, None)
        return func if callable(func) else None

    except Exception:
        return None


def get_config_params(func: Callable) -> List[str]:
    """Extract config parameter names from function signature.

    Args:
        func: Function to introspect (typically a plugin's reads() function)

    Returns:
        List of parameter names that are expected config parameters.
        Excludes special parameters like 'config', 'params', 'kwargs'.

    Examples:
        >>> def reads(url: str, method: str = "GET", timeout: int = 30, **params):
        ...     pass
        >>> get_config_params(reads)
        ['url', 'method', 'timeout']

        >>> def reads(config: Optional[dict] = None):
        ...     pass
        >>> get_config_params(reads)
        []  # config dict means all params are config, handled separately
    """
    try:
        sig = inspect.signature(func)
        params = []

        for name, param in sig.parameters.items():
            # Skip dict collectors - these mean "all params are config"
            if name in ("config", "params", "kwargs"):
                continue

            # Skip *args and **kwargs style parameters
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            params.append(name)

        return params

    except Exception:
        return []


def is_config_dict_pattern(func: Callable) -> bool:
    """Check if function uses config dict pattern (config: dict parameter).

    Args:
        func: Function to check

    Returns:
        True if function has a 'config' parameter (indicating all params are config)
    """
    try:
        sig = inspect.signature(func)
        return "config" in sig.parameters
    except Exception:
        return False


def get_plugin_config_params(plugin_path: str) -> List[str]:
    """Get config parameter names from plugin's reads() function.

    This is a convenience wrapper that loads the plugin and introspects it.

    For plugins using the config dict pattern (config: Optional[dict]),
    returns a list of common config parameter names.

    Args:
        plugin_path: Path to plugin .py file

    Returns:
        List of config parameter names, or empty list if can't introspect
    """
    func = load_plugin_function(plugin_path, "reads")
    if not func:
        return []

    params = get_config_params(func)

    # If function uses config dict pattern, return common config params
    if is_config_dict_pattern(func):
        # Common config parameters that should not be treated as filters
        return [
            "limit",
            "offset",
            "delimiter",
            "skip_rows",
            "header",
            "method",
            "timeout",
            "headers",
            "format",
            "mode",  # Output mode (e.g., lcov lines/functions/branches)
        ]

    return params
