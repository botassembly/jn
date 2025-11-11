#!/usr/bin/env -S uv run --script
"""HTTP protocol plugin for fetching data from HTTP/HTTPS endpoints."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests>=2.31.0",
# ]
# [tool.jn]
# matches = [
#   "^https?://.*"
# ]
# ///

import json
import sys
from typing import Iterator, Optional
from urllib.parse import urlparse

import requests


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Fetch data from HTTP/HTTPS URL and yield NDJSON records.

    Config:
        url: The URL to fetch (required)
        method: HTTP method (default: 'GET')
        headers: Dict of HTTP headers
        auth: Tuple of (username, password) for Basic auth
        timeout: Request timeout in seconds (default: 30)
        verify_ssl: Verify SSL certificates (default: True)
        format: Force specific format ('json', 'csv', 'ndjson', 'text')

    Yields:
        Dict records from the response
    """
    config = config or {}

    url = config.get("url")
    if not url:
        raise ValueError("URL is required")

    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})
    auth = config.get("auth")
    timeout = config.get("timeout", 30)
    verify_ssl = config.get("verify_ssl", True)
    force_format = config.get("format")

    # Read request body from stdin for POST/PUT/PATCH
    data = None
    if method in ("POST", "PUT", "PATCH"):
        data = sys.stdin.read()

    # Make request with streaming
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            auth=auth,
            data=data,
            timeout=timeout,
            verify=verify_ssl,
            stream=True
        )
        response.raise_for_status()

        # Detect format
        content_type = response.headers.get("Content-Type", "")
        file_ext = urlparse(url).path.split(".")[-1].lower()

        # Determine format
        if force_format:
            fmt = force_format
        elif "application/json" in content_type or file_ext == "json":
            fmt = "json"
        elif "application/x-ndjson" in content_type or file_ext == "jsonl":
            fmt = "ndjson"
        elif "text/csv" in content_type or file_ext in ("csv", "tsv"):
            fmt = "csv"
        else:
            fmt = "text"

        # Process based on format
        if fmt == "json":
            # JSON - parse and yield records
            yield from _parse_json(response)
        elif fmt == "ndjson":
            # NDJSON - yield line by line
            yield from _parse_ndjson(response)
        elif fmt == "csv":
            # CSV - yield single record with content
            yield {"content": response.text, "content_type": "text/csv", "url": url}
        else:
            # Text/unknown - yield single record
            yield {"content": response.text, "content_type": content_type, "url": url}

    except requests.exceptions.RequestException as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def _parse_json(response: requests.Response) -> Iterator[dict]:
    """Parse JSON response and yield records.

    - JSON arrays: yield each element as a record
    - JSON objects: yield the object as a single record
    """
    try:
        data = response.json()

        if isinstance(data, list):
            # Array: yield each element
            for item in data:
                if isinstance(item, dict):
                    yield item
                else:
                    # Wrap primitives
                    yield {"value": item}
        elif isinstance(data, dict):
            # Single object
            yield data
        else:
            # Primitive value
            yield {"value": data}

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}", file=sys.stderr)
        sys.exit(1)


def _parse_ndjson(response: requests.Response) -> Iterator[dict]:
    """Parse NDJSON response line by line."""
    for line in response.iter_lines(decode_unicode=True):
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"NDJSON decode error on line: {line[:100]}: {e}", file=sys.stderr)
                continue


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="HTTP protocol plugin - fetch data from HTTP/HTTPS endpoints"
    )
    parser.add_argument(
        "--mode",
        choices=["read"],
        help="Operation mode (HTTP plugin only supports read)",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL to fetch"
    )
    parser.add_argument(
        "--method",
        default="GET",
        choices=["GET", "POST", "PUT", "PATCH", "DELETE"],
        help="HTTP method (default: GET)"
    )
    parser.add_argument(
        "--headers",
        type=json.loads,
        default={},
        help='HTTP headers as JSON object (e.g., \'{"Authorization": "Bearer token"}\')'
    )
    parser.add_argument(
        "--auth",
        help="Basic auth as 'username:password'"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--no-verify-ssl",
        dest="verify_ssl",
        action="store_false",
        help="Disable SSL certificate verification (use with caution)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "ndjson", "csv", "text"],
        help="Force specific format parsing"
    )

    args = parser.parse_args()

    if not args.mode:
        parser.error("--mode is required")

    if not args.url:
        parser.error("URL is required")

    # Build auth tuple if provided
    auth = None
    if args.auth:
        if ":" in args.auth:
            auth = tuple(args.auth.split(":", 1))
        else:
            parser.error("--auth must be in format 'username:password'")

    # Substitute environment variables in headers
    headers = {}
    for key, value in args.headers.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            env_value = os.environ.get(env_var)
            if not env_value:
                print(f"Error: Environment variable {env_var} not set", file=sys.stderr)
                sys.exit(1)
            headers[key] = env_value
        else:
            headers[key] = value

    # Build config
    config = {
        "url": args.url,
        "method": args.method,
        "headers": headers,
        "auth": auth,
        "timeout": args.timeout,
        "verify_ssl": args.verify_ssl,
        "format": args.format,
    }

    # Execute
    for record in reads(config):
        print(json.dumps(record), flush=True)
