#!/usr/bin/env python3
"""HTTP GET plugin - Fetch data from URLs.

Fetches data via HTTP GET and outputs as NDJSON.
Supports JSON responses (arrays and objects).
"""
# /// script
# dependencies = []
# ///
# META: type=source
# KEYWORDS: http, get, fetch, api, web
# DESCRIPTION: Fetch data from URLs via HTTP GET

import sys
import json
import subprocess
from typing import Optional, Iterator


def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Fetch data from URL via HTTP GET.

    Uses curl for HTTP requests. Parses JSON responses.

    Args:
        config: Configuration dict
            - url: str - URL to fetch (required)
            - headers: dict - HTTP headers
            - timeout: int - Timeout in seconds (default: 30)

    Yields:
        Records as dicts
    """
    if config is None:
        config = {}

    url = config.get('url')
    if not url:
        print("Error: URL is required", file=sys.stderr)
        sys.exit(1)

    headers = config.get('headers', {})
    timeout = config.get('timeout', 30)

    # Build curl command
    cmd = ['curl', '-s', '-L', '--max-time', str(timeout)]

    # Add headers
    for key, value in headers.items():
        cmd.extend(['-H', f'{key}: {value}'])

    # Add URL
    cmd.append(url)

    try:
        # Execute curl
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Parse response
        try:
            data = json.loads(result.stdout)

            # Handle different response types
            if isinstance(data, list):
                # JSON array - yield each item
                for item in data:
                    if isinstance(item, dict):
                        yield item
                    else:
                        # Wrap non-dict items
                        yield {'value': item}
            elif isinstance(data, dict):
                # Single JSON object
                yield data
            else:
                # Primitive value
                yield {'value': data}

        except json.JSONDecodeError:
            # Not JSON - treat as text
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines, 1):
                yield {
                    'line': i,
                    'text': line
                }

    except subprocess.CalledProcessError as e:
        print(f"HTTP request failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def schema() -> dict:
    """Return JSON schema for HTTP GET output.

    HTTP GET returns JSON objects from API responses.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "JSON response from HTTP GET request"
    }


def examples() -> list[dict]:
    """Return example usage patterns - NO MOCKS, real httpbin.org!

    Returns:
        List of example dicts with real HTTP tests
    """
    return [
        {
            "description": "GET UUID endpoint (dynamic value)",
            "config": {
                "url": "https://httpbin.org/uuid",
                "timeout": 10
            },
            "input": "",
            "expected": [
                {"uuid": ""}  # UUID changes every time!
            ],
            "ignore_fields": {"uuid"}  # UUID is dynamic - only validate structure
        },
        {
            "description": "GET IP address (dynamic value)",
            "config": {
                "url": "https://httpbin.org/ip",
                "timeout": 10
            },
            "input": "",
            "expected": [
                {"origin": ""}  # Our IP (dynamic)
            ],
            "ignore_fields": {"origin"}  # IP is dynamic
        }
    ]


def test() -> bool:
    """Run built-in tests - NO MOCKS, real HTTP!

    Tests against httpbin.org with real HTTP requests.

    Returns:
        True if all tests pass
    """
    print("Testing with REAL HTTP requests (NO MOCKS)...", file=sys.stderr)

    passed = 0
    failed = 0

    for example in examples():
        desc = example['description']
        config = example.get('config', {})

        try:
            # Run with real HTTP request
            results = list(run(config))

            # Check we got at least one result
            if len(results) > 0:
                print(f"✓ {desc}: Got {len(results)} result(s)", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ {desc}: No results", file=sys.stderr)
                failed += 1

        except Exception as e:
            print(f"✗ {desc}: {e}", file=sys.stderr)
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} real HTTP tests passed", file=sys.stderr)

    return failed == 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Fetch data from URLs via HTTP GET'
    )
    parser.add_argument(
        'url',
        nargs='?',
        help='URL to fetch'
    )
    parser.add_argument(
        '--url',
        dest='url_flag',
        help='URL to fetch (alternative)'
    )
    parser.add_argument(
        '--header', '-H',
        action='append',
        dest='headers',
        help='HTTP header (format: "Key: Value")'
    )
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=30,
        help='Timeout in seconds (default: 30)'
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

    # Get URL from either positional or flag
    url = args.url or args.url_flag
    if not url:
        parser.error("URL is required")

    # Parse headers
    headers = {}
    if args.headers:
        for header in args.headers:
            if ':' in header:
                key, value = header.split(':', 1)
                headers[key.strip()] = value.strip()

    # Build config
    config = {
        'url': url,
        'headers': headers,
        'timeout': args.timeout
    }

    # Run fetcher
    for record in run(config):
        print(json.dumps(record))
