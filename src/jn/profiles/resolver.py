"""Generic profile resolution system - works for any plugin.

This module provides a unified way for any plugin to have reusable profiles.
Profiles are files stored in profiles/{plugin_dir}/ directories that contain
plugin-specific content (queries, configurations, templates, etc.).

Examples:
    - JQ filter profiles: profiles/jq/builtin/group_count.jq
    - CSV format profiles: profiles/csv/formats/wide.csv (hypothetical)
    - SQL query profiles: profiles/sql/analytics/revenue.sql (hypothetical)

The framework resolves profile references (@namespace/name) and substitutes
parameters before passing the content to the plugin.
"""

import glob
import os
from pathlib import Path
from typing import Dict, Optional


class ProfileError(Exception):
    """Error resolving plugin profile."""

    pass


def resolve_profile(
    profile_ref: str, plugin_name: str, params: Optional[Dict[str, str]] = None
) -> str:
    """Resolve @profile/name reference for any plugin.

    Generic profile resolution system that works for all plugins.
    Searches for profile files and performs parameter substitution.

    Args:
        profile_ref: Profile reference like "@builtin/pivot" or "@analytics/custom"
        plugin_name: Name of plugin (e.g., "jq_", "csv_", "http_")
        params: Optional parameters to substitute (e.g., {"by": "status"})

    Returns:
        Resolved profile content with parameters substituted

    Raises:
        ProfileError: If profile not found

    Profile Directory Structure:
        Plugin "jq_" looks in profiles/jq/ (trailing underscore removed)
        Plugin "csv_" looks in profiles/csv/
        Plugin "http_" looks in profiles/http/

    Search Paths (in order):
        1. ~/.local/jn/profiles/{plugin_dir}/{profile_path}.*
        2. $JN_HOME/profiles/{plugin_dir}/{profile_path}.* (if JN_HOME set)
        3. {jn_package}/jn_home/profiles/{plugin_dir}/{profile_path}.* (bundled)

    File Extension:
        Auto-detected - searches for files with any extension.
        Common patterns: .jq for jq_, .json for http_, .sql for sql_, etc.

    Parameter Substitution:
        - $param_name - replaced with "param_value" (quoted)
        - Supports any parameter name defined in params dict
        - Example: $by with params={"by": "status"} → "status"

    Comment Stripping:
        Lines starting with # are treated as comments and removed.
        This works for .jq, .sql, .py, and other hash-comment formats.

    Examples:
        # JQ filter profile
        resolve_profile("@builtin/group_count", "jq_", {"by": "status"})
        → Searches profiles/jq/builtin/group_count.jq
        → Returns jq query with $by replaced with "status"

        # Hypothetical CSV format profile
        resolve_profile("@formats/wide", "csv_", {})
        → Searches profiles/csv/formats/wide.csv
        → Returns CSV format configuration
    """
    if params is None:
        params = {}

    # Remove @ prefix
    profile_path = profile_ref.lstrip("@")

    # Derive plugin directory name (remove trailing underscore if present)
    plugin_dir = plugin_name.rstrip("_")

    # Build search paths (without extension - we'll glob for it)
    search_bases = []

    # 1. User profiles in ~/.local/jn
    search_bases.append(
        Path.home() / ".local" / "jn" / "profiles" / plugin_dir / profile_path
    )

    # 2. Project profiles (if JN_HOME is set)
    if "JN_HOME" in os.environ:
        search_bases.append(
            Path(os.environ["JN_HOME"])
            / "profiles"
            / plugin_dir
            / profile_path
        )

    # 3. Bundled profiles (relative to this module)
    # This file is in src/jn/profiles/resolver.py
    # Bundled profiles are in jn_home/profiles/
    # Navigate up to find jn_home/
    package_root = Path(
        __file__
    ).parent.parent.parent.parent  # Up to repo root
    bundled_base = (
        package_root / "jn_home" / "profiles" / plugin_dir / profile_path
    )
    search_bases.append(bundled_base)

    # Search for profile file with any extension
    profile_file = None
    searched_patterns = []

    for base in search_bases:
        # Try with wildcard extension
        pattern = str(base) + ".*"
        searched_patterns.append(pattern)
        matches = glob.glob(pattern)
        if matches:
            # Take first match
            profile_file = Path(matches[0])
            break

    if not profile_file:
        # Format error message with search locations
        search_list = "\n".join(
            f"  - {pattern}" for pattern in searched_patterns
        )
        raise ProfileError(
            f"Profile not found: {profile_ref} (for plugin '{plugin_name}')\n"
            f"Searched for:\n{search_list}"
        )

    # Load content from file
    content = profile_file.read_text()

    # Strip comment lines (lines starting with #)
    # This is generic and works for many file formats (.jq, .sql, .py, etc.)
    # Note: Some formats (like JSON) don't support # comments, so this is optional
    content_lines = [
        line
        for line in content.split("\n")
        if not line.strip().startswith("#")
    ]
    content = "\n".join(content_lines).strip()

    # Substitute parameters
    # Simple string replacement: $param_name → "param_value"
    # TODO: More sophisticated substitution could support ${param_name} syntax
    # TODO: Consider plugin-specific escaping (e.g., SQL injection prevention)
    for param_name, param_value in params.items():
        # Replace $param_name with "param_value" (quoted)
        # This works for jq and most query languages
        content = content.replace(f"${param_name}", f'"{param_value}"')

    return content
