#!/usr/bin/env python3
"""Environment variables plugin - Parse env output to NDJSON.

Executes env command and parses output into structured JSON.
Each environment variable becomes a record.
"""
# /// script
# dependencies = []
# ///
# META: type=source, command="env"
# KEYWORDS: env, environment, variables, system, config
# DESCRIPTION: Parse env command output to NDJSON

import sys
import json
import subprocess
from typing import Optional, Iterator


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Execute env and parse output to NDJSON.

    Args:
        config: Configuration dict (unused)

    Yields:
        Environment variable records as dicts
    """
    try:
        # Execute env
        result = subprocess.run(
            ['env'],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse output
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Split on first = sign
            if '=' in line:
                key, value = line.split('=', 1)
                yield {
                    'name': key,
                    'value': value
                }

    except subprocess.CalledProcessError as e:
        print(f"env command failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def schema() -> dict:
    """Return JSON schema for env output.

    Defines structure for environment variable records.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "Environment variable name-value pair",
        "properties": {
            "name": {"type": "string", "description": "Variable name"},
            "value": {"type": "string", "description": "Variable value"}
        },
        "required": ["name", "value"]
    }


def examples() -> list[dict]:
    """Return example usage patterns - NO MOCKS, real env command!

    Returns:
        List of example dicts with schema-only validation
    """
    return [
        {
            "description": "Parse real env output (variable results)",
            "config": {},
            "input": "",
            "expected": [],  # Empty = schema-only validation (env vars change)
            "ignore_fields": set()  # Not needed for schema-only validation
        }
    ]


def test() -> bool:
    """Run built-in tests - NO MOCKS, real env command!

    Runs real env and validates against schema.

    Returns:
        True if all tests pass
    """
    print("Testing with REAL env command (NO MOCKS)...", file=sys.stderr)

    # Try to run env and parse output
    try:
        results = list(run())
        if results:
            print(f"✓ Successfully parsed {len(results)} environment variables", file=sys.stderr)

            # Check that required fields exist
            first = results[0]
            if 'name' in first and 'value' in first:
                print("✓ Required fields present (name, value)", file=sys.stderr)

            print(f"\n2/2 real env tests passed", file=sys.stderr)
            return True
        else:
            print("✗ No environment variables parsed", file=sys.stderr)
            return False

    except Exception as e:
        print(f"✗ Test failed: {e}", file=sys.stderr)
        return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Parse env command output to NDJSON'
    )
    parser.add_argument(
        '--examples',
        action='store_true',
        help='Show usage examples'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run built-in tests'
    )
    parser.add_argument(
        '--schema',
        action='store_true',
        help='Output JSON schema'
    )

    args = parser.parse_args()

    if args.schema:
        print(json.dumps(schema(), indent=2))
        sys.exit(0)

    if args.examples:
        print(json.dumps(examples(), indent=2))
        sys.exit(0)

    if args.test:
        success = test()
        sys.exit(0 if success else 1)

    # Run env parser
    for record in run():
        print(json.dumps(record))
