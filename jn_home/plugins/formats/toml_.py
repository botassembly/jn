#!/usr/bin/env -S uv run --script
"""Parse TOML configuration files and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "tomli-w>=1.0.0"
# ]
# [tool.jn]
# matches = [
#   ".*\\.toml$"
# ]
# ///

import json
import sys
import tomllib
from typing import Iterator, Optional

try:
    import tomli_w
except ImportError:
    tomli_w = None


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read TOML from stdin, yield as single NDJSON record.

    Config:
        flatten: Flatten nested tables to dot notation (default: False)

    Yields:
        Single dict containing entire TOML document structure
    """
    config = config or {}
    flatten = config.get("flatten", False)

    # Read entire TOML file
    content = sys.stdin.read()
    data = tomllib.loads(content)

    if flatten:
        yield _flatten_dict(data)
    else:
        yield data


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write as TOML to stdout.

    Config:
        merge: Merge multiple records into single TOML (default: True)

    If merge=True, combines all records into nested structure.
    If merge=False, only writes first record (TOML is single-document).
    """
    if tomli_w is None:
        raise ImportError("tomli-w package required for writing TOML")

    config = config or {}
    merge = config.get("merge", True)

    # Collect all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            records.append(json.loads(line))

    if not records:
        # Empty input - write empty TOML
        sys.stdout.write("")
        return

    # Merge or use first record
    if merge and len(records) > 1:
        # Deep merge all records
        result = {}
        for record in records:
            _deep_merge(result, record)
        data = result
    else:
        data = records[0]

    # Write TOML
    toml_content = tomli_w.dumps(data)
    sys.stdout.write(toml_content)


def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Flatten nested dict to dot notation keys."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _deep_merge(target: dict, source: dict) -> None:
    """Deep merge source dict into target dict (modifies target)."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="TOML format plugin - read/write TOML config files"
    )
    parser.add_argument(
        "--mode",
        choices=["read", "write"],
        help="Operation mode: read TOML to NDJSON, or write NDJSON to TOML",
    )
    parser.add_argument(
        "--flatten",
        action="store_true",
        help="Flatten nested tables to dot notation when reading",
    )
    parser.add_argument(
        "--no-merge",
        dest="merge",
        action="store_false",
        help="Don't merge multiple records when writing (use first only)",
    )

    args = parser.parse_args()

    if not args.mode:
        parser.error("--mode is required")

    # Build config
    config = {}

    if args.mode == "read":
        config["flatten"] = args.flatten
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        config["merge"] = args.merge
        writes(config)
