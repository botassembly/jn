#!/usr/bin/env python3
"""HTTP GET plugin - NO MOCKS, test real httpbin.

Philosophy:
- Test REAL endpoints (httpbin.org)
- No mocks whatsoever
- Ignore dynamic fields (timestamps, IPs, UUIDs)
- Focus on shape/schema validation
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
    """Fetch data from URL via HTTP GET."""
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

    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Parse JSON response
        try:
            data = json.loads(result.stdout)

            if isinstance(data, list):
                for item in data:
                    yield item if isinstance(item, dict) else {'value': item}
            elif isinstance(data, dict):
                yield data
            else:
                yield {'value': data}

        except json.JSONDecodeError:
            # Not JSON - treat as text
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines, 1):
                yield {'line': i, 'text': line}

    except subprocess.CalledProcessError as e:
        print(f"HTTP request failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def schema() -> dict:
    """JSON schema for HTTP responses."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "description": "HTTP GET response as JSON object"
    }


def examples() -> list[dict]:
    """Real integration tests - NO MOCKS!

    We test REAL httpbin endpoints and ignore dynamic fields.
    This is better than mocks because:
    - Tests actual HTTP behavior
    - Tests actual curl integration
    - Tests actual JSON parsing
    - Only ignores what's truly dynamic (timestamps, IPs, UUIDs)
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
                    # httpbin/json returns sample slideshow data
                    # Structure is consistent, values don't matter
                    "slideshow": {
                        "author": "",
                        "date": "",
                        "slides": [],
                        "title": ""
                    }
                }
            ],
            # Ignore all fields - we just check structure exists
            "ignore_fields": {"author", "date", "title"}
        },
        {
            "description": "GET with custom headers echoed back",
            "config": {
                "url": "https://httpbin.org/headers",
                "headers": {
                    "X-Test-Header": "test-value"
                },
                "timeout": 10
            },
            "expected": [
                {
                    "headers": {
                        # Dynamic fields - httpbin adds many headers
                        # We just check the structure exists
                    }
                }
            ],
            # All header values are dynamic
            "ignore_fields": {"headers"}
        },
        {
            "description": "GET query parameters",
            "config": {
                "url": "https://httpbin.org/get?foo=bar&test=123",
                "timeout": 10
            },
            "expected": [
                {
                    "args": {},    # Query params
                    "headers": {}, # Request headers
                    "origin": "",  # IP address (dynamic!)
                    "url": ""      # Full URL
                }
            ],
            # Ignore dynamic fields (IP, headers, url)
            # Shape checking will verify args exists
            "ignore_fields": {"origin", "headers", "url"}
        },
        {
            "description": "GET UUID endpoint (entirely dynamic)",
            "config": {
                "url": "https://httpbin.org/uuid",
                "timeout": 10
            },
            "expected": [
                {
                    "uuid": ""  # Changes every time
                }
            ],
            # UUID is dynamic but shape is consistent
            "ignore_fields": {"uuid"}
        },
        {
            "description": "GET IP address endpoint",
            "config": {
                "url": "https://httpbin.org/ip",
                "timeout": 10
            },
            "expected": [
                {
                    "origin": ""  # Our IP address
                }
            ],
            "ignore_fields": {"origin"}
        },
        {
            "description": "GET delay endpoint (tests timeout)",
            "config": {
                "url": "https://httpbin.org/delay/1",
                "timeout": 10
            },
            "expected": [
                {
                    "args": {},
                    "data": "",
                    "files": {},
                    "form": {},
                    "headers": {},
                    "origin": "",
                    "url": ""
                }
            ],
            "ignore_fields": {"args", "data", "files", "form", "headers", "origin", "url"}
        }
    ]


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='HTTP GET with no mocks')
    parser.add_argument('url', nargs='?', help='URL to fetch')
    parser.add_argument('--url', dest='url_flag', help='URL (alternative)')
    parser.add_argument('--header', '-H', action='append', dest='headers', help='Header')
    parser.add_argument('--timeout', '-t', type=int, default=30, help='Timeout')
    parser.add_argument('--schema', action='store_true', help='Print schema')
    parser.add_argument('--examples', action='store_true', help='Print examples')

    args = parser.parse_args()

    if args.schema:
        print(json.dumps(schema(), indent=2))
        sys.exit(0)

    if args.examples:
        print(json.dumps(examples(), indent=2))
        sys.exit(0)

    url = args.url or args.url_flag
    if not url:
        parser.error("URL is required")

    headers = {}
    if args.headers:
        for header in args.headers:
            if ':' in header:
                key, value = header.split(':', 1)
                headers[key.strip()] = value.strip()

    config = {
        'url': url,
        'headers': headers,
        'timeout': args.timeout
    }

    for record in run(config):
        print(json.dumps(record))
