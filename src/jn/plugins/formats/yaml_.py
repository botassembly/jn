#!/usr/bin/env -S uv run --script
"""Parse YAML files (including multi-document) and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ruamel.yaml>=0.18.0"
# ]
# [tool.jn]
# matches = [
#   ".*\\.yaml$",
#   ".*\\.yml$"
# ]
# ///

import sys
import json
from typing import Iterator, Optional

from ruamel.yaml import YAML


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read YAML from stdin, yield NDJSON records.

    Supports both single documents and multi-document YAML (---)
    Each YAML document becomes one NDJSON record.

    Config:
        safe: Use safe loading (default: True)

    Yields:
        Dict per YAML document
    """
    config = config or {}

    yaml = YAML()
    yaml.preserve_quotes = True

    # Load all documents from stdin
    # ruamel.yaml.load_all() handles multi-document YAML
    for doc in yaml.load_all(sys.stdin):
        if doc is not None:
            # Ensure we yield dicts (wrap primitives if needed)
            if isinstance(doc, dict):
                yield doc
            elif isinstance(doc, list):
                # List of items - yield each as separate record
                for item in doc:
                    if isinstance(item, dict):
                        yield item
                    else:
                        yield {'value': item}
            else:
                # Primitive value - wrap in dict
                yield {'value': doc}


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write YAML to stdout.

    Config:
        multi_document: Write as multi-document YAML with --- separators (default: True)
        indent: Indentation spaces (default: 2)

    Reads all records and writes as YAML document(s).
    """
    config = config or {}
    multi_document = config.get('multi_document', True)
    indent = config.get('indent', 2)

    yaml = YAML()
    yaml.indent(mapping=indent, sequence=indent, offset=indent)
    yaml.default_flow_style = False

    # Collect all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            records.append(json.loads(line))

    if not records:
        # Empty input
        return

    if multi_document and len(records) > 1:
        # Write as multi-document YAML
        for i, record in enumerate(records):
            if i > 0:
                sys.stdout.write('---\n')
            yaml.dump(record, sys.stdout)
    else:
        # Single document (or list if multiple records with multi_document=False)
        if len(records) == 1:
            yaml.dump(records[0], sys.stdout)
        else:
            yaml.dump(records, sys.stdout)


def test() -> bool:
    """Run self-tests with real data (no mocks).

    Returns:
        True if all tests pass
    """
    from io import StringIO

    print("Testing YAML plugin...", file=sys.stderr)

    # Test 1: Read single-document YAML
    test_input = "name: Alice\nage: 30\n"
    sys.stdin = StringIO(test_input)

    results = list(reads())
    expected = [{"name": "Alice", "age": 30}]

    if results == expected:
        print("✓ YAML single-document read test passed", file=sys.stderr)
    else:
        print(f"✗ YAML read test failed: {results}", file=sys.stderr)
        return False

    # Test 2: Read multi-document YAML
    test_input = "name: Alice\n---\nname: Bob\n"
    sys.stdin = StringIO(test_input)

    results = list(reads())
    expected = [{"name": "Alice"}, {"name": "Bob"}]

    if results == expected:
        print("✓ YAML multi-document read test passed", file=sys.stderr)
    else:
        print(f"✗ YAML multi-doc read test failed: {results}", file=sys.stderr)
        return False

    # Test 3: Write YAML
    sys.stdin = StringIO('{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n')
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    writes()

    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    # Check that output contains expected content (YAML formatting may vary)
    if "Alice" in output and "Bob" in output and "---" in output:
        print("✓ YAML write test passed", file=sys.stderr)
    else:
        print(f"✗ YAML write test failed: {repr(output)}", file=sys.stderr)
        return False

    print("All YAML tests passed!", file=sys.stderr)
    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='YAML format plugin - read/write YAML files')
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run self-tests'
    )
    parser.add_argument(
        '--mode',
        choices=['read', 'write'],
        help='Operation mode: read YAML to NDJSON, or write NDJSON to YAML'
    )
    parser.add_argument(
        '--indent',
        type=int,
        default=2,
        help='Indentation spaces when writing (default: 2)'
    )
    parser.add_argument(
        '--no-multi-document',
        dest='multi_document',
        action='store_false',
        help='Write as single document (list) instead of multi-document'
    )

    args = parser.parse_args()

    if args.test:
        success = test()
        sys.exit(0 if success else 1)

    if not args.mode:
        parser.error('--mode is required when not running tests')

    # Build config
    config = {}

    if args.mode == 'read':
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        config['multi_document'] = args.multi_document
        config['indent'] = args.indent
        writes(config)
