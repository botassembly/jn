"""Utility helpers for CLI integration."""

import os
import re
from typing import Dict, Optional


def parse_key_value_pairs(items: list[str]) -> dict[str, str]:
    """Parse "key=value" pairs from CLI flags into a dictionary."""

    result: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid format: {item} (expected key=value)")
        key, value = item.split("=", 1)
        result[key] = value
    return result


def substitute_template(
    text: str,
    params: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
) -> str:
    """Substitute ${params.*} and ${env.*} placeholders in text.

    Args:
        text: Text containing placeholders like ${params.key} or ${env.KEY}
        params: Dictionary of parameter values
        env: Dictionary of environment variables (defaults to os.environ)

    Returns:
        Text with placeholders substituted

    Raises:
        KeyError: If a referenced param or env var is not found
    """
    params = params or {}
    env = env if env is not None else dict(os.environ)

    def replace_param(match):
        key = match.group(1)
        if key not in params:
            raise KeyError(f"Parameter not found: {key}")
        return params[key]

    def replace_env(match):
        key = match.group(1)
        if key not in env:
            raise KeyError(f"Environment variable not found: {key}")
        return env[key]

    # Replace ${params.key}
    text = re.sub(r"\$\{params\.([^}]+)\}", replace_param, text)
    # Replace ${env.KEY}
    text = re.sub(r"\$\{env\.([^}]+)\}", replace_env, text)

    return text


__all__ = ["parse_key_value_pairs", "substitute_template"]
