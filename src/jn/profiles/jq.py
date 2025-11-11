"""JQ profile resolution - resolve @profile/name references to jq queries."""

import os
import sys
from pathlib import Path
from typing import Dict


class JQProfileError(Exception):
    """Error resolving JQ profile."""
    pass


def resolve_jq_profile(profile_ref: str, params: Dict[str, str]) -> str:
    """Resolve @profile/name reference to jq query string.

    Searches for .jq files in standard locations and substitutes parameters.

    Args:
        profile_ref: Profile reference like "@builtin/pivot" or "@analytics/custom"
        params: Parameters to substitute in the query (e.g., {"row": "product"})

    Returns:
        Resolved jq query string with parameters substituted

    Raises:
        JQProfileError: If profile not found

    Search paths (in order):
        1. ~/.local/jn/profiles/jq/{profile_path}.jq
        2. $JN_HOME/profiles/jq/{profile_path}.jq (if JN_HOME set)
        3. {jn_package}/jn_home/profiles/jq/{profile_path}.jq (bundled)
    """
    # Remove @ prefix
    profile_path = profile_ref.lstrip("@")

    # Build search paths
    search_paths = []

    # 1. User profiles in ~/.local/jn
    search_paths.append(
        Path.home() / ".local" / "jn" / "profiles" / "jq" / f"{profile_path}.jq"
    )

    # 2. Project profiles (if JN_HOME is set)
    if "JN_HOME" in os.environ:
        search_paths.append(
            Path(os.environ["JN_HOME"]) / "profiles" / "jq" / f"{profile_path}.jq"
        )

    # 3. Bundled profiles (relative to this module)
    # This file is in src/jn/profiles/jq.py
    # Bundled profiles are in jn_home/profiles/jq/
    # Navigate up to find jn_home/
    package_root = Path(__file__).parent.parent.parent.parent  # Up to repo root
    bundled_path = package_root / "jn_home" / "profiles" / "jq" / f"{profile_path}.jq"
    search_paths.append(bundled_path)

    # Find first existing profile
    profile_file = None
    for path in search_paths:
        if path.exists():
            profile_file = path
            break

    if not profile_file:
        # Format error message with search locations
        search_list = "\n".join(f"  - {path}" for path in search_paths)
        raise JQProfileError(
            f"Profile not found: {profile_ref}\n"
            f"Searched in:\n{search_list}"
        )

    # Load query from file
    query = profile_file.read_text()

    # Strip comment lines (lines starting with #)
    # Note: jq itself doesn't support comments in queries, but we allow them in .jq files
    query_lines = [
        line for line in query.split("\n")
        if not line.strip().startswith("#")
    ]
    query = "\n".join(query_lines).strip()

    # Substitute parameters
    # TODO: Consider using jq's built-in --arg for safer parameter passing
    # Current approach: simple string replacement (works for most cases)
    for param_name, param_value in params.items():
        # Replace $param_name with "param_value" in the query
        # This supports parameters like $row_key, $col_key, etc.
        query = query.replace(f"${param_name}", f'"{param_value}"')

    return query
