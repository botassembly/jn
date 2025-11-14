"""Profile system for JN - reusable API configurations and plugin profiles.

Two types of profiles:
1. HTTP/API profiles (http.py) - Connection configs for REST APIs
2. Generic plugin profiles (resolver.py) - Reusable content for any plugin
"""

from .http import ProfileError as HTTPProfileError
from .http import resolve_profile_reference
from .resolver import ProfileError, resolve_profile

__all__ = [
    "HTTPProfileError",
    "ProfileError",
    "resolve_profile",
    "resolve_profile_reference",
]
