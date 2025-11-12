"""Gmail profile resolution - convert @gmail/source to gmail:// URLs."""

import json
import os
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlencode


class GmailProfileError(Exception):
    """Gmail profile resolution error."""

    pass


def load_gmail_profile(source_name: str) -> Dict:
    """Load Gmail profile from jn_home/profiles/gmail/.

    Args:
        source_name: Name of the source (e.g., "inbox", "unread", "messages")

    Returns:
        Profile dict with defaults and configuration

    Raises:
        GmailProfileError: If profile not found or invalid
    """
    # Use JN_HOME if set, otherwise bundled profiles
    jn_home = os.environ.get("JN_HOME")
    if jn_home:
        profile_dir = Path(jn_home) / "profiles" / "gmail"
    else:
        # Fallback: bundled profiles relative to this file
        # This file is in src/jn/profiles/gmail.py
        # Bundled profiles are in jn_home/profiles/gmail/
        profile_dir = (
            Path(__file__).parent.parent.parent.parent
            / "jn_home"
            / "profiles"
            / "gmail"
        )

    profile_path = profile_dir / f"{source_name}.json"

    if not profile_path.exists():
        raise GmailProfileError(
            f"Gmail profile '{source_name}' not found at {profile_path}"
        )

    try:
        with open(profile_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise GmailProfileError(f"Invalid JSON in {profile_path}: {e}")


def resolve_gmail_reference(
    reference: str, params: Optional[Dict] = None
) -> str:
    """Resolve @gmail/source to gmail:// URL with query parameters.

    Args:
        reference: Gmail profile reference like "@gmail/inbox" or "@gmail/messages"
        params: Optional query parameters from URL like {"from": "boss", "is": "unread"}

    Returns:
        Gmail URL like "gmail://me/messages?in=inbox&from=boss&is=unread"

    Raises:
        GmailProfileError: If profile not found

    Examples:
        >>> resolve_gmail_reference("@gmail/inbox")
        "gmail://me/messages?in=inbox"

        >>> resolve_gmail_reference("@gmail/inbox", {"from": "boss"})
        "gmail://me/messages?in=inbox&from=boss"

        >>> resolve_gmail_reference("@gmail/messages", {"is": "unread", "from": "boss"})
        "gmail://me/messages?is=unread&from=boss"
    """
    if not reference.startswith("@gmail/"):
        raise GmailProfileError(
            f"Invalid Gmail reference (must start with @gmail/): {reference}"
        )

    # Extract source name
    source_name = reference[len("@gmail/") :]

    # Load profile
    profile = load_gmail_profile(source_name)

    # Get defaults from profile (e.g., inbox has "in": "inbox")
    defaults = profile.get("defaults", {})

    # Merge defaults with provided params (params override defaults)
    all_params = {**defaults, **(params or {})}

    # Build gmail:// URL
    # Format: gmail://user_id/messages?query_params
    user_id = "me"  # Could be configurable later
    base_url = f"gmail://{user_id}/messages"

    # Add query string if we have params
    if all_params:
        query_string = urlencode(all_params, doseq=True)
        return f"{base_url}?{query_string}"

    return base_url
