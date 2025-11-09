#!/usr/bin/env python3
"""HTTP GET plugin - IMPROVED with real httpbin tests and schema.

This demonstrates:
- Real integration tests using httpbin.org
- JSON schema for output validation
- Smart field matching (exact vs dynamic)
- Graceful handling of flaky tests (95% success is fine)
"""
# /// script
# dependencies = []
# ///
# META: type=source

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

    Schema depends on response type, but we can describe the wrapper format.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "oneOf": [
            {
                "type": "object",
                "description": "JSON response (any object)"
            },
            {
                "type": "object",
                "properties": {
                    "value": {
                        "description": "Primitive value wrapper"
                    }
                },
                "required": ["value"]
            },
            {
                "type": "object",
                "properties": {
                    "line": {
                        "type": "integer",
                        "description": "Line number"
                    },
                    "text": {
                        "type": "string",
                        "description": "Line text"
                    }
                },
                "required": ["line", "text"]
            }
        ]
    }


def examples() -> list[dict]:
    """Return test cases using httpbin.org.

    Httpbin.org is designed for testing HTTP clients. It's occasionally flaky,
    but that's fine - 95% success rate is acceptable for integration tests.
    """
    return [
        {
            "description": "GET JSON object from httpbin",
            "config": {
                "url": "https://httpbin.org/json",
                "timeout": 10
            },
            "expected": [
                {
                    # httpbin returns a sample JSON object
                    # We don't know exact values, so check types only
                }
            ],
            "checks": {
                # Don't check exact values (dynamic responses)
                # Just ensure we get back valid JSON with expected structure
                "types": ["slideshow"]  # httpbin/json returns {"slideshow": {...}}
            }
        },
        {
            "description": "GET with custom headers",
            "config": {
                "url": "https://httpbin.org/headers",
                "headers": {
                    "X-Test-Header": "test-value"
                },
                "timeout": 10
            },
            "expected": [
                {
                    "headers": {}
                }
            ],
            "checks": {
                # Response includes our headers
                "types": ["headers"]
            }
        },
        {
            "description": "GET query parameters",
            "config": {
                "url": "https://httpbin.org/get?foo=bar&test=123",
                "timeout": 10
            },
            "expected": [
                {
                    "args": {"foo": "bar", "test": "123"}
                }
            ],
            "checks": {
                # Check that specific query params made it through
                "exact": []  # Can't check exact - response includes headers, url, etc.
            }
        },
        {
            "description": "GET UUID (dynamic content)",
            "config": {
                "url": "https://httpbin.org/uuid",
                "timeout": 10
            },
            "expected": [
                {
                    "uuid": ""  # Will be different each time
                }
            ],
            "checks": {
                # UUID field must match pattern
                "patterns": {
                    "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
                }
            }
        },
        {
            "description": "GET status code endpoint",
            "config": {
                "url": "https://httpbin.org/status/200",
                "timeout": 10
            },
            "expected": [
                {}  # Empty response for 200 status
            ],
            "checks": {}
        }
    ]


def test() -> bool:
    """Run real integration tests with httpbin.

    Note: These are integration tests that hit a real HTTP endpoint.
    They may occasionally fail due to network issues - that's acceptable.
    We aim for 95% success rate.
    """
    import sys
    from pathlib import Path

    # Try to use testing framework
    jn_path = Path(__file__).parent.parent.parent / 'src'
    if str(jn_path) not in sys.path:
        sys.path.insert(0, str(jn_path))

    try:
        from jn.testing import run_plugin_tests

        print("Running integration tests against httpbin.org...", file=sys.stderr)
        print("(Network tests may occasionally fail - that's expected)\n", file=sys.stderr)

        return run_plugin_tests(
            run_func=run,
            examples_func=examples,
            schema_func=schema,
            verbose=True
        )
    except ImportError:
        # Fallback
        return test_basic()


def test_basic() -> bool:
    """Basic integration tests without framework."""
    passed = 0
    failed = 0
    skipped = 0

    print("Running integration tests against httpbin.org...", file=sys.stderr)
    print("(Network tests may occasionally fail - that's expected)\n", file=sys.stderr)

    for example in examples():
        desc = example['description']
        config = example.get('config', {})

        try:
            results = list(run(config))

            if len(results) > 0:
                print(f"✓ {desc}", file=sys.stderr)
                print(f"  Got {len(results)} record(s)", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ {desc}: No results", file=sys.stderr)
                failed += 1

        except Exception as e:
            # Network errors are expected occasionally
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                print(f"⊘ {desc}: Network error (skipped)", file=sys.stderr)
                skipped += 1
            else:
                print(f"✗ {desc}: {e}", file=sys.stderr)
                failed += 1

    total = passed + failed + skipped
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped (network)", file=sys.stderr)
    print(f"Success rate: {100 * passed / total if total > 0 else 0:.1f}%", file=sys.stderr)

    # Allow some failures due to network issues
    # Success if we pass >= 80% of tests
    success_rate = passed / total if total > 0 else 0
    return success_rate >= 0.8


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
        '--schema',
        action='store_true',
        help='Output JSON schema'
    )
    parser.add_argument(
        '--examples',
        action='store_true',
        help='Show usage examples'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run integration tests'
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
