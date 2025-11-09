"""Source/target auto-detection logic.

Harvested from oldgen/src/jn/cli/cat.py with adaptations for plugin system.
"""

from pathlib import Path
from typing import Optional


def is_url(source: str) -> bool:
    """Check if source is a URL pattern.

    Harvested from oldgen cat.py _is_url()
    """
    return source.startswith(
        ("http://", "https://", "ftp://", "ftps://", "s3://")
    )


def detect_file_extension(path: str) -> Optional[str]:
    """Get file extension for format detection.

    Returns lowercase extension including the dot (e.g., '.csv')
    """
    ext = Path(path).suffix.lower()
    return ext if ext else None


def is_jc_command(command: str) -> bool:
    """Check if command is in JC's parser registry.

    Harvested from oldgen cat.py _is_jc_command()
    """
    try:
        import jc
        return command in jc.parser_mod_list()
    except Exception:
        return False


def detect_source_type(source: str, args: list[str] = None) -> dict:
    """Auto-detect source type and return plugin info.

    Adapted from oldgen cat.py _detect_source_type() to return plugin names
    instead of driver/parser pairs.

    Priority:
        1. URL pattern → http_get plugin
        2. File exists → extension-based plugin lookup
        3. Known JC command → jc_parse plugin
        4. Unknown command → generic_exec plugin

    Args:
        source: Input source (URL, file path, or command)
        args: Additional arguments (for commands)

    Returns:
        Dict with keys:
            - type: 'source'
            - plugin: Plugin name to use
            - config: Plugin-specific configuration
    """
    args = args or []

    # 1. Check for URL
    if is_url(source):
        return {
            'type': 'source',
            'plugin': 'http_get',
            'config': {'url': source}
        }

    # 2. Check if file exists
    path = Path(source)
    if path.exists() and path.is_file():
        ext = detect_file_extension(source)
        return {
            'type': 'source',
            'plugin': None,  # Will be resolved by registry
            'config': {
                'path': str(path.resolve()),
                'extension': ext
            }
        }

    # 3. Check if command is in JC registry
    if is_jc_command(source):
        return {
            'type': 'source',
            'plugin': 'jc_parse',
            'config': {
                'command': [source] + args,
                'parser': source
            }
        }

    # 4. Fallback: unknown command with generic execution
    return {
        'type': 'source',
        'plugin': 'generic_exec',
        'config': {
            'command': [source] + args
        }
    }


def detect_target_type(target: str) -> dict:
    """Auto-detect target type and return plugin info.

    Args:
        target: Output target (file path or URL)

    Returns:
        Dict with keys:
            - type: 'target'
            - plugin: Plugin name (None if needs registry lookup)
            - config: Plugin-specific configuration
    """
    # URL → HTTP POST
    if is_url(target):
        return {
            'type': 'target',
            'plugin': 'http_post',
            'config': {'url': target}
        }

    # File path → extension-based lookup
    path = Path(target)
    ext = detect_file_extension(target)

    return {
        'type': 'target',
        'plugin': None,  # Will be resolved by registry
        'config': {
            'path': str(path.resolve()),
            'extension': ext
        }
    }


def detect_filter_type(filter_arg: str) -> dict:
    """Auto-detect filter type.

    Args:
        filter_arg: Filter specification (name or inline jq)

    Returns:
        Dict with keys:
            - type: 'filter'
            - plugin: Plugin name
            - config: Filter configuration
    """
    # Inline jq expression?
    if filter_arg.startswith('.') or 'select(' in filter_arg:
        return {
            'type': 'filter',
            'plugin': 'jq_filter',
            'config': {'query': filter_arg}
        }

    # Named filter (will be looked up in registry)
    return {
        'type': 'filter',
        'plugin': filter_arg,
        'config': {}
    }
