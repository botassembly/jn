#!/usr/bin/env -S uv run --script
"""Parse JSON files and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [
#   ".*\\.json$",
#   ".*\\.jsonl$",
#   ".*\\.ndjson$"
# ]
# ///

import json
import sys
from typing import Iterator, Optional


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read JSON from stdin, yield NDJSON records."""
    config = config or {}
    content = sys.stdin.read().strip()
    if not content:
        return
    lines = content.split("\n")
    if len(lines) > 1:
        try:
            json.loads(lines[0])
            for line in lines:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        yield obj
                    else:
                        yield {"value": obj}
            return
        except json.JSONDecodeError:
            pass
    data = json.loads(content)
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
            else:
                yield {"value": item}
    elif isinstance(data, dict):
        yield data
    else:
        yield {"value": data}


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write JSON to stdout."""
    config = config or {}
    output_format = config.get("format", "array")
    indent = config.get("indent")
    sort_keys = config.get("sort_keys", False)
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            records.append(json.loads(line))
    if output_format == "ndjson":
        for record in records:
            print(json.dumps(record, sort_keys=sort_keys))
    elif output_format == "array":
        print(json.dumps(records, indent=indent, sort_keys=sort_keys))
    elif output_format == "object":
        if len(records) == 0:
            print("{}")
        elif len(records) == 1:
            print(json.dumps(records[0], indent=indent, sort_keys=sort_keys))
        else:
            print(
                f"Error: Cannot write {len(records)} records as single object",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print(f"Error: Unknown format '{output_format}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="JSON format plugin - read/write JSON files"
    )
    parser.add_argument("--mode", choices=["read", "write"], help="Mode")
    parser.add_argument("--format", choices=["ndjson", "array", "object"], default="array")
    parser.add_argument("--indent", type=int)
    parser.add_argument("--sort-keys", action="store_true")
    args = parser.parse_args()
    if not args.mode:
        parser.error("--mode is required when not running tests")
    config = {}
    if args.mode == "read":
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        config["format"] = args.format
        if args.indent is not None:
            config["indent"] = args.indent
        config["sort_keys"] = args.sort_keys
        writes(config)
