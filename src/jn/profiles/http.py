"""HTTP Profile System - reusable REST API configurations.

Profiles provide:
- Base URLs and authentication
- Path templates with variables
- Environment variable substitution
- Clean @profile/path syntax
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ProfileError(Exception):
    """Error in profile resolution."""
    pass


class HTTPProfile:
    """Represents an HTTP API profile."""

    def __init__(self, name: str, config: dict, profile_path: Path):
        """Initialize profile.

        Args:
            name: Profile name
            config: Profile configuration dict
            profile_path: Path to profile file
        """
        self.name = name
        self.config = config
        self.profile_path = profile_path

    @property
    def base_url(self) -> str:
        """Get base URL with env var substitution."""
        url = self.config.get("base_url", "")
        return self._substitute_env_vars(url)

    @property
    def headers(self) -> Dict[str, str]:
        """Get headers with env var substitution."""
        headers = self.config.get("headers", {})
        return {k: self._substitute_env_vars(v) for k, v in headers.items()}

    @property
    def auth(self) -> Optional[Tuple[str, str]]:
        """Get basic auth tuple if configured."""
        auth_config = self.config.get("auth", {})
        if auth_config.get("type") == "basic":
            username = self._substitute_env_vars(auth_config.get("username", ""))
            password = self._substitute_env_vars(auth_config.get("password", ""))
            if username and password:
                return (username, password)
        return None

    @property
    def timeout(self) -> int:
        """Get timeout in seconds."""
        return self.config.get("timeout", 30)

    def resolve_path(self, path: str, params: Optional[Dict[str, str]] = None) -> str:
        """Resolve path with variable substitution.

        Args:
            path: Path like "/users/{id}" or "/repos"
            params: Dict of path variables to substitute

        Returns:
            Full URL with base_url + resolved path
        """
        params = params or {}

        # Check if path references a named path template
        paths = self.config.get("paths", {})
        if path in paths:
            path = paths[path]

        # Substitute path variables
        for key, value in params.items():
            path = path.replace(f"{{{key}}}", value)

        # Build full URL
        base = self.base_url.rstrip("/")
        path = path.lstrip("/")
        return f"{base}/{path}"

    def _substitute_env_vars(self, value: str) -> str:
        """Substitute environment variables in string.

        Supports ${VAR} syntax.

        Args:
            value: String with possible env var references

        Returns:
            String with env vars substituted

        Raises:
            ProfileError: If required env var is not set
        """
        if not isinstance(value, str):
            return value

        # Find all ${VAR} patterns
        pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}'

        def replace_var(match):
            var_name = match.group(1)
            var_value = os.environ.get(var_name)
            if var_value is None:
                raise ProfileError(
                    f"Environment variable {var_name} not set (required by profile {self.name})"
                )
            return var_value

        return re.sub(pattern, replace_var, value)


def find_profile_paths() -> List[Path]:
    """Get search paths for profiles (in priority order).

    Returns:
        List of directories to search for profiles
    """
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
    # Find JN_HOME
    jn_home = os.environ.get("JN_HOME")
    if jn_home:
        bundled_dir = Path(jn_home) / "profiles" / "http"
    else:
        # Fallback: relative to this file
        bundled_dir = Path(__file__).parent.parent.parent.parent / "jn_home" / "profiles" / "http"

    if bundled_dir.exists():
        paths.append(bundled_dir)

    return paths


def load_profile(name: str) -> HTTPProfile:
    """Load profile by name.

    Args:
        name: Profile name (e.g., "github", "stripe")

    Returns:
        HTTPProfile object

    Raises:
        ProfileError: If profile not found or invalid
    """
    # Search for profile in order
    for search_dir in find_profile_paths():
        profile_file = search_dir / f"{name}.json"
        if profile_file.exists():
            try:
                config = json.loads(profile_file.read_text())
                return HTTPProfile(name, config, profile_file)
            except json.JSONDecodeError as e:
                raise ProfileError(f"Invalid JSON in profile {name}: {e}")

    raise ProfileError(f"Profile not found: {name}")


def resolve_profile_reference(reference: str) -> Tuple[str, Dict[str, str]]:
    """Resolve @profile/path reference to URL.

    Args:
        reference: Profile reference like "@github/repos/owner/repo"

    Returns:
        Tuple of (url, headers_dict)

    Raises:
        ProfileError: If profile not found or resolution fails
    """
    if not reference.startswith("@"):
        raise ProfileError(f"Invalid profile reference (must start with @): {reference}")

    # Remove @ prefix
    ref = reference[1:]

    # Split profile name from path
    parts = ref.split("/", 1)
    if len(parts) == 1:
        # Just profile name, no path
        profile_name = parts[0]
        path = ""
    else:
        profile_name, path = parts

    # Load profile
    profile = load_profile(profile_name)

    # Extract path variables (e.g., {id})
    path_vars = {}
    # For now, we'll handle simple positional substitution
    # More advanced: parse path template and match

    # Resolve to full URL
    if path:
        url = profile.resolve_path("/" + path, path_vars)
    else:
        url = profile.base_url

    return url, profile.headers
