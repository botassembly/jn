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

import sys
import json
from typing import Iterator, Optional


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read JSON from stdin, yield NDJSON records.

    Handles three JSON formats:
    1. NDJSON/JSONL: One JSON object per line (pass-through)
    2. JSON array: Parse as array, yield each element
    3. Single JSON object: Yield the object

    Config:
        array_mode: Force array parsing (default: auto-detect)

    Yields:
        Dict per JSON record
    """
    config = config or {}

    # Read all input
    content = sys.stdin.read().strip()

    if not content:
        return

    # Try to detect format
    # NDJSON: Multiple lines, each is valid JSON
    # JSON array: Starts with [
    # JSON object: Starts with {

    lines = content.split('\n')

    # Check if it's NDJSON (first line is valid JSON)
    if len(lines) > 1:
        try:
            json.loads(lines[0])
            # Looks like NDJSON - process line by line
            for line in lines:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        yield obj
                    else:
                        yield {'value': obj}
            return
        except json.JSONDecodeError:
            pass

    # Not NDJSON - parse as single JSON document
    data = json.loads(content)

    if isinstance(data, list):
        # JSON array - yield each element
        for item in data:
            if isinstance(item, dict):
                yield item
            else:
                yield {'value': item}
    elif isinstance(data, dict):
        # Single object
        yield data
    else:
        # Primitive value
        yield {'value': data}


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write JSON to stdout.

    Config:
        format: Output format - 'ndjson', 'array', 'object' (default: 'array')
        indent: Pretty-print indentation (default: None for compact)
        sort_keys: Sort object keys (default: False)

    Modes:
        - ndjson: One JSON object per line (pass-through)
        - array: JSON array of all records
        - object: Single JSON object (only if exactly 1 record)
    """
    config = config or {}
    output_format = config.get('format', 'array')
    indent = config.get('indent')
    sort_keys = config.get('sort_keys', False)

    # Collect all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            records.append(json.loads(line))

    if output_format == 'ndjson':
        # NDJSON: one per line
        for record in records:
            print(json.dumps(record, sort_keys=sort_keys))

    elif output_format == 'array':
        # JSON array
        print(json.dumps(records, indent=indent, sort_keys=sort_keys))

    elif output_format == 'object':
        # Single object (error if more than one record)
        if len(records) == 0:
            print('{}')
        elif len(records) == 1:
            print(json.dumps(records[0], indent=indent, sort_keys=sort_keys))
        else:
            print(f"Error: Cannot write {len(records)} records as single object", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Error: Unknown format '{output_format}'", file=sys.stderr)
        sys.exit(1)


def test() -> bool:
    """Run self-tests with real data (no mocks).

    Returns:
        True if all tests pass
    """
    from io import StringIO

    print("Testing JSON plugin...", file=sys.stderr)

    # Test 1: Read NDJSON
    test_input = '{"name":"Alice"}\n{"name":"Bob"}\n'
    sys.stdin = StringIO(test_input)

    results = list(reads())
    expected = [{"name": "Alice"}, {"name": "Bob"}]

    if results == expected:
        print("✓ JSON NDJSON read test passed", file=sys.stderr)
    else:
        print(f"✗ JSON read test failed: {results}", file=sys.stderr)
        return False

    # Test 2: Read JSON array
    test_input = '[{"name":"Alice"},{"name":"Bob"}]'
    sys.stdin = StringIO(test_input)

    results = list(reads())
    expected = [{"name": "Alice"}, {"name": "Bob"}]

    if results == expected:
        print("✓ JSON array read test passed", file=sys.stderr)
    else:
        print(f"✗ JSON array read test failed: {results}", file=sys.stderr)
        return False

    # Test 3: Write JSON array
    sys.stdin = StringIO('{"name":"Alice"}\n{"name":"Bob"}\n')
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    writes({'format': 'array'})

    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    expected_output = '[{"name": "Alice"}, {"name": "Bob"}]'

    if json.loads(output) == json.loads(expected_output):
        print("✓ JSON array write test passed", file=sys.stderr)
    else:
        print(f"✗ JSON write test failed: {repr(output)}", file=sys.stderr)
        return False

    print("All JSON tests passed!", file=sys.stderr)
    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='JSON format plugin - read/write JSON files')
    parser.add_argument(
        '--mode',
        choices=['read', 'write'],
        required=True,
        help='Operation mode: read JSON to NDJSON, or write NDJSON to JSON'
    )
    parser.add_argument(
        '--format',
        choices=['ndjson', 'array', 'object'],
        default='array',
        help='Output format when writing (default: array)'
    )
    parser.add_argument(
        '--indent',
        type=int,
        help='Pretty-print indentation (default: compact)'
    )
    parser.add_argument(
        '--sort-keys',
        action='store_true',
        help='Sort object keys alphabetically'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run self-tests'
    )

    args = parser.parse_args()

    if args.test:
        success = test()
        sys.exit(0 if success else 1)

    # Build config
    config = {}

    if args.mode == 'read':
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        config['format'] = args.format
        if args.indent is not None:
            config['indent'] = args.indent
        config['sort_keys'] = args.sort_keys
        writes(config)
