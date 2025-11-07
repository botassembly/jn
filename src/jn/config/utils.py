"""Utility helpers for CLI integration."""


def parse_key_value_pairs(items: list[str]) -> dict[str, str]:
    """Parse "key=value" pairs from CLI flags into a dictionary."""

    result: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid format: {item} (expected key=value)")
        key, value = item.split("=", 1)
        result[key] = value
    return result


__all__ = ["parse_key_value_pairs"]
