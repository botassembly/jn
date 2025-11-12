"""HTTP Profile System - hierarchical REST API configurations.

New hierarchical structure:
  profiles/http/{api_name}/_meta.json      - Connection info (base_url, headers, timeout)
  profiles/http/{api_name}/{source}.json   - Source definitions (path, method, type)

Example:
  profiles/http/genomoncology/_meta.json
  profiles/http/genomoncology/annotations.json
  profiles/http/genomoncology/alterations.json

Reference format:
  @genomoncology/annotations → Merges _meta.json + annotations.json
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple


class ProfileError(Exception):
    """Error in profile resolution."""

    pass


def find_profile_paths() -> list[Path]:
    """Get search paths for profiles (in priority order)."""
    paths = []

    # 1. Project profiles (highest priority)
    project_profile_dir = Path.cwd() / ".jn" / "profiles" / "http"
    if project_profile_dir.exists():
        paths.append(project_profile_dir)

    # 2. User profiles
    user_profile_dir = Path.home() / ".local" / "jn" / "profiles" / "http"
    if user_profile_dir.exists():
        paths.append(user_profile_dir)

    # 3. Bundled profiles (lowest priority)
    jn_home = os.environ.get("JN_HOME")
    if jn_home:
        bundled_dir = Path(jn_home) / "profiles" / "http"
    else:
        # Fallback: relative to this file
        bundled_dir = (
            Path(__file__).parent.parent.parent.parent
            / "jn_home"
            / "profiles"
            / "http"
        )

    if bundled_dir.exists():
        paths.append(bundled_dir)

    return paths


def substitute_env_vars(value: str) -> str:
    """Substitute ${VAR} environment variables in string."""
    if not isinstance(value, str):
        return value

    pattern = r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"

    def replace_var(match):
        var_name = match.group(1)
        var_value = os.environ.get(var_name)
        if var_value is None:
            raise ProfileError(f"Environment variable {var_name} not set")
        return var_value

    return re.sub(pattern, replace_var, value)


def load_hierarchical_profile(
    api_name: str, source_name: Optional[str] = None
) -> dict:
    """Load hierarchical profile: _meta.json + optional source.json.

    Args:
        api_name: API name (e.g., "genomoncology")
        source_name: Optional source name (e.g., "annotations")

    Returns:
        Merged profile dict with _meta + source info

    Raises:
        ProfileError: If profile not found
    """
    meta = {}
    source = {}

    # Search for profile directory
    for search_dir in find_profile_paths():
        api_dir = search_dir / api_name

        if not api_dir.exists():
            continue

        # Load _meta.json (connection info)
        meta_file = api_dir / "_meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except json.JSONDecodeError as e:
                raise ProfileError(f"Invalid JSON in {meta_file}: {e}")

        # Load source.json if requested
        if source_name:
            source_file = api_dir / f"{source_name}.json"
            if source_file.exists():
                try:
                    source = json.loads(source_file.read_text())
                except json.JSONDecodeError as e:
                    raise ProfileError(f"Invalid JSON in {source_file}: {e}")
            elif meta:
                # _meta exists but source doesn't
                raise ProfileError(
                    f"Source not found: {api_name}/{source_name}"
                )

        # If we found meta (and optionally source), we're done
        if meta:
            break

    if not meta:
        raise ProfileError(f"Profile not found: {api_name}")

    # Merge _meta + source
    merged = {**meta, **source}
    return merged


def resolve_profile_reference(
    reference: str, params: Optional[Dict] = None
) -> Tuple[str, Dict[str, str]]:
    """Resolve @api/source reference to URL and headers.

    Args:
        reference: Profile reference like "@genomoncology/annotations"
        params: Optional query parameters like {"gene": "BRAF", "mutation_type": "Missense"}

    Returns:
        Tuple of (url, headers_dict)

    Raises:
        ProfileError: If profile not found
    """
    if not reference.startswith("@"):
        raise ProfileError(
            f"Invalid profile reference (must start with @): {reference}"
        )

    # Parse reference: @api_name/source_name
    ref = reference[1:]  # Remove @
    parts = ref.split("/", 1)

    if len(parts) == 1:
        # Just @api_name - load _meta only
        api_name = parts[0]
        source_name = None
    else:
        api_name, source_name = parts

    # Load profile
    profile = load_hierarchical_profile(api_name, source_name)

    # Validate params against profile's allowed params (if defined)
    if params and "params" in profile:
        allowed_params = set(profile["params"])
        provided_params = set(params.keys())
        invalid_params = provided_params - allowed_params

        if invalid_params:
            import sys

            invalid_list = ", ".join(sorted(invalid_params))
            allowed_list = ", ".join(sorted(allowed_params))
            print(
                f"Warning: Parameters {invalid_list} are not supported by {reference}.\n"
                f"Supported parameters: {allowed_list}\n"
                f"The API may ignore unsupported parameters.",
                file=sys.stderr,
            )

    # Build URL
    base_url = substitute_env_vars(profile.get("base_url", ""))
    path = profile.get("path", "")

    # Construct full URL
    base = base_url.rstrip("/")
    path = path.lstrip("/")
    url = f"{base}/{path}" if path else base

    # Add query params if provided
    if params:
        from urllib.parse import urlencode

        # doseq=True handles list values (multiple params with same key)
        query_string = urlencode(params, doseq=True)
        url = f"{url}?{query_string}"

    # Build headers with env var substitution
    headers = profile.get("headers", {})
    resolved_headers = {k: substitute_env_vars(v) for k, v in headers.items()}

    return url, resolved_headers
