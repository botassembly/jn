"""Profile discovery and search service.

Simple in-memory search - fast enough for thousands of profiles.
No indexing/caching needed until dataset grows significantly.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ProfileInfo:
    """Profile metadata."""

    reference: str  # "@gmail/inbox" or "@builtin/pivot"
    type: str  # "gmail", "jq", "http", "mcp"
    namespace: str  # "gmail", "builtin", "genomoncology"
    name: str  # "inbox", "pivot"
    path: Path  # Full file path
    description: str = ""
    params: List[str] = field(default_factory=list)
    examples: List[dict] = field(default_factory=list)


def _get_profile_paths() -> List[Path]:
    """Get profile search paths in priority order.

    Returns:
        List of profile root directories
    """
    paths = []

    # 1. Project profiles (highest priority)
    project_dir = Path.cwd() / ".jn" / "profiles"
    if project_dir.exists():
        paths.append(project_dir)

    # 2. User profiles
    user_dir = Path.home() / ".local" / "jn" / "profiles"
    if user_dir.exists():
        paths.append(user_dir)

    # 3. Bundled profiles (lowest priority)
    jn_home = os.environ.get("JN_HOME")
    if jn_home:
        bundled_dir = Path(jn_home) / "profiles"
    else:
        # Fallback: relative to this file
        bundled_dir = (
            Path(__file__).parent.parent.parent.parent / "jn_home" / "profiles"
        )

    if bundled_dir.exists():
        paths.append(bundled_dir)

    return paths


def _parse_jq_profile(jq_file: Path, profile_root: Path) -> ProfileInfo:
    """Parse JQ profile from .jq file.

    Extracts description and parameters from comments at top of file.
    """
    content = jq_file.read_text()

    # Extract description from first comment line
    description = ""
    params = []

    for line in content.split("\n")[:20]:  # Check first 20 lines
        line = line.strip()

        # Description from first comment
        if line.startswith("#") and not description:
            desc_text = line.lstrip("#").strip()
            if (
                desc_text
                and not desc_text.startswith("Parameters:")
                and not desc_text.startswith("Usage:")
            ):
                description = desc_text

        # Parameters from "# Parameters: x, y, z" format
        if "# Parameters:" in line:
            # Extract comma-separated params after "Parameters:"
            params_text = line.split("Parameters:", 1)[1].strip()
            # Split by comma and clean up
            params = [p.strip() for p in params_text.split(",")]
            break  # Found the params line, stop searching

    # If no explicit parameters line, look for $variable references
    if not params:
        for line in content.split("\n")[:20]:
            if line.startswith("# $") or "$" in line:
                # Extract variable names like $row_key, $col_key
                param_matches = re.findall(r"\$(\w+)", line)
                params.extend(param_matches)

        # Deduplicate params while preserving order
        seen = set()
        params = [p for p in params if not (p in seen or seen.add(p))]

    # Build reference from path
    rel_path = jq_file.relative_to(profile_root / "jq")
    parts = rel_path.with_suffix("").parts

    if len(parts) == 1:
        # No subdirectory - use profile type as namespace
        namespace = "jq"
        name = parts[0]
    else:
        namespace = parts[0]
        name = "/".join(parts[1:])

    reference = f"@{namespace}/{name}"

    return ProfileInfo(
        reference=reference,
        type="jq",
        namespace=namespace,
        name=name,
        path=jq_file,
        description=description,
        params=params,
    )


def _parse_json_profile(
    json_file: Path, profile_root: Path, profile_type: str
) -> ProfileInfo:
    """Parse JSON profile (gmail, http, mcp).

    Args:
        json_file: Path to JSON file
        profile_root: Root profile directory
        profile_type: "gmail", "http", or "mcp"
    """
    data = json.loads(json_file.read_text())

    # Skip _meta.json files
    if json_file.name == "_meta.json":
        return None

    # Build reference from path
    rel_path = json_file.relative_to(profile_root / profile_type)
    parts = rel_path.with_suffix("").parts

    if len(parts) == 1:
        # No subdirectory - use profile type as namespace
        namespace = profile_type
        name = parts[0]
    else:
        namespace = parts[0]
        name = "/".join(parts[1:])

    reference = f"@{namespace}/{name}"

    return ProfileInfo(
        reference=reference,
        type=profile_type,
        namespace=namespace,
        name=name,
        path=json_file,
        description=data.get("description", ""),
        params=data.get("params", []),
        examples=data.get("examples", []),
    )


def _parse_duckdb_profile(
    sql_file: Path, profile_root: Path
) -> Optional[ProfileInfo]:
    """Parse DuckDB .sql file into ProfileInfo.

    Extracts:
    - Description from first comment line
    - Parameters from comment or SQL body
    """
    content = sql_file.read_text()

    # Parse metadata from comments
    description = ""
    params = []

    for line in content.split("\n")[:20]:
        line = line.strip()

        # Description from first comment
        if line.startswith("--") and not description:
            desc = line.lstrip("-").strip()
            if desc and not desc.startswith("Parameters:"):
                description = desc

        # Parameters from "-- Parameters: x, y, z"
        if "-- Parameters:" in line:
            params_text = line.split("Parameters:", 1)[1].strip()
            # Parse "gene (required), mutation_type (optional)"
            params = [p.split("(")[0].strip() for p in params_text.split(",")]
            break

    # If no explicit parameters, find $param or :param in SQL
    if not params:
        params = list(set(re.findall(r"[$:](\w+)", content)))

    # Build reference from path
    # profiles/duckdb/genie/folfox.sql → @genie/folfox
    rel_path = sql_file.relative_to(profile_root / "duckdb")
    parts = rel_path.with_suffix("").parts

    namespace = parts[0]
    name = "/".join(parts[1:]) if len(parts) > 1 else parts[0]

    return ProfileInfo(
        reference=f"@{namespace}/{name}",
        type="duckdb",
        namespace=namespace,
        name=name,
        path=sql_file,
        description=description,
        params=params,
    )


def list_all_profiles() -> List[ProfileInfo]:
    """Scan filesystem and load all profiles.

    Fast enough to run every time (~4ms for 15 profiles).
    No caching needed until >1000 profiles.

    Returns:
        List of all discovered profiles
    """
    profiles = []

    for profile_root in _get_profile_paths():
        # JQ profiles
        jq_dir = profile_root / "jq"
        if jq_dir.exists():
            for jq_file in jq_dir.rglob("*.jq"):
                profiles.append(_parse_jq_profile(jq_file, profile_root))

        # Gmail profiles
        gmail_dir = profile_root / "gmail"
        if gmail_dir.exists():
            for json_file in gmail_dir.rglob("*.json"):
                profile = _parse_json_profile(json_file, profile_root, "gmail")
                if profile:  # Skip _meta.json
                    profiles.append(profile)

        # HTTP profiles (future)
        http_dir = profile_root / "http"
        if http_dir.exists():
            for json_file in http_dir.rglob("*.json"):
                profile = _parse_json_profile(json_file, profile_root, "http")
                if profile:
                    profiles.append(profile)

        # MCP profiles (future)
        mcp_dir = profile_root / "mcp"
        if mcp_dir.exists():
            for json_file in mcp_dir.rglob("*.json"):
                profile = _parse_json_profile(json_file, profile_root, "mcp")
                if profile:
                    profiles.append(profile)

        # DuckDB profiles
        duckdb_dir = profile_root / "duckdb"
        if duckdb_dir.exists():
            for sql_file in duckdb_dir.rglob("*.sql"):
                profile = _parse_duckdb_profile(sql_file, profile_root)
                if profile:
                    profiles.append(profile)

    return profiles


def search_profiles(
    query: Optional[str] = None, type_filter: Optional[str] = None
) -> List[ProfileInfo]:
    """Search profiles by name or description.

    Simple case-insensitive substring search.
    Fast enough for thousands of profiles.

    Args:
        query: Search term (case-insensitive), or None for all
        type_filter: Optional filter by type ("jq", "gmail", "http", "mcp")

    Returns:
        Matching profiles, sorted alphabetically by reference
    """
    all_profiles = list_all_profiles()

    # Filter by type
    if type_filter:
        all_profiles = [p for p in all_profiles if p.type == type_filter]

    # No query = return all
    if not query:
        return sorted(all_profiles, key=lambda p: p.reference)

    # Simple case-insensitive contains search
    query_lower = query.lower().strip()

    matches = [
        p
        for p in all_profiles
        if query_lower in p.name.lower()
        or query_lower in p.description.lower()
    ]

    return sorted(matches, key=lambda p: p.reference)


def get_profile_info(reference: str) -> Optional[ProfileInfo]:
    """Get detailed info about a specific profile.

    Args:
        reference: Profile reference like "@gmail/inbox" or "@builtin/pivot"

    Returns:
        ProfileInfo or None if not found
    """
    all_profiles = list_all_profiles()

    for profile in all_profiles:
        if profile.reference == reference:
            return profile

    return None
