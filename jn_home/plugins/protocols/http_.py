#!/usr/bin/env -S uv run --script
"""HTTP protocol plugin for fetching data from HTTP/HTTPS endpoints.

This plugin enables reading from HTTP/HTTPS endpoints using:
- Naked URLs: https://example.com/data.json
- Profile references: @genomoncology/alterations?gene=BRAF

Examples:
    # Naked URL access (no profile required)
    jn cat "https://api.example.com/data.json"
    jn inspect "https://api.example.com"

    # Profile-based access
    jn cat "@genomoncology/alterations?gene=BRAF"
    jn inspect "@genomoncology"
"""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests>=2.31.0",
# ]
# [tool.jn]
# matches = [
#   "^https?://.*"
# ]
# supports_raw = true
# ///

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import requests


# Format detection mapping
FORMAT_DETECT = {
    # Content types
    "application/json": "json",
    "application/x-ndjson": "ndjson",
    "text/csv": "csv",
    # File extensions (text formats only)
    ".json": "json",
    ".jsonl": "ndjson",
    ".csv": "csv",
    ".tsv": "csv",
}


# ============================================================================
# VENDORED HTTP PROFILE RESOLVER (self-contained, no framework imports)
# Copied from src/jn/profiles/http.py to maintain plugin self-containment
# ============================================================================


class ProfileError(Exception):
    """Error in profile resolution."""

    pass


def find_profile_paths() -> list[Path]:
    """Get search paths for HTTP profiles (in priority order)."""
    paths = []

    # 1. Project profiles (highest priority)
    project_profile_dir = Path.cwd() / ".jn" / "profiles" / "http"
    if project_profile_dir.exists():
        paths.append(project_profile_dir)

    # 2. User profiles
    user_profile_dir = Path.home() / ".local" / "jn" / "profiles" / "http"
    if user_profile_dir.exists():
        paths.append(user_profile_dir)

    # 3. Bundled profiles (lowest priority)
    jn_home = os.environ.get("JN_HOME")
    if jn_home:
        bundled_dir = Path(jn_home) / "profiles" / "http"
    else:
        # Fallback: relative to this file (3 levels up to jn_home)
        bundled_dir = Path(__file__).parent.parent.parent / "profiles" / "http"

    if bundled_dir.exists():
        paths.append(bundled_dir)

    return paths


def substitute_env_vars(value: str) -> str:
    """Substitute ${VAR} environment variables in string."""
    if not isinstance(value, str):
        return value

    pattern = r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"

    def replace_var(match):
        var_name = match.group(1)
        var_value = os.environ.get(var_name)
        if var_value is None:
            raise ProfileError(f"Environment variable {var_name} not set")
        return var_value

    return re.sub(pattern, replace_var, value)


def substitute_env_vars_recursive(data):
    """Recursively substitute environment variables in nested structures."""
    if isinstance(data, dict):
        return {k: substitute_env_vars_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [substitute_env_vars_recursive(item) for item in data]
    elif isinstance(data, str):
        return substitute_env_vars(data)
    else:
        return data


def load_hierarchical_profile(
    api_name: str, source_name: Optional[str] = None
) -> dict:
    """Load hierarchical HTTP profile: _meta.json + optional source.json.

    Args:
        api_name: API name (e.g., "genomoncology")
        source_name: Optional source name (e.g., "alterations")

    Returns:
        Merged profile dict with _meta + source info

    Raises:
        ProfileError: If profile not found
    """
    meta = {}
    source = {}

    # Search for profile directory
    for search_dir in find_profile_paths():
        api_dir = search_dir / api_name

        if not api_dir.exists():
            continue

        # Load _meta.json (connection info)
        meta_file = api_dir / "_meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except json.JSONDecodeError as e:
                raise ProfileError(f"Invalid JSON in {meta_file}: {e}")

        # Load source.json if requested
        if source_name:
            source_file = api_dir / f"{source_name}.json"
            if source_file.exists():
                try:
                    source = json.loads(source_file.read_text())
                except json.JSONDecodeError as e:
                    raise ProfileError(f"Invalid JSON in {source_file}: {e}")
            elif meta:
                # _meta exists but source doesn't
                raise ProfileError(
                    f"Source not found: {api_name}/{source_name}"
                )

        # If we found meta, we're done
        if meta:
            break

    if not meta:
        raise ProfileError(f"HTTP API profile not found: {api_name}")

    # Merge _meta + source
    merged = {**meta, **source}

    # Substitute environment variables recursively
    merged = substitute_env_vars_recursive(merged)

    return merged


def list_profile_sources(api_name: str) -> list[str]:
    """List available sources for an HTTP API profile.

    Args:
        api_name: API name (e.g., "genomoncology")

    Returns:
        List of source names (without .json extension)
    """
    sources = []

    for search_dir in find_profile_paths():
        api_dir = search_dir / api_name
        if api_dir.exists():
            # Find all .json files except _meta.json
            for json_file in api_dir.glob("*.json"):
                if json_file.name != "_meta.json":
                    source_name = json_file.stem
                    if source_name not in sources:
                        sources.append(source_name)

    return sorted(sources)


def resolve_profile_reference(
    reference: str, params: Optional[Dict] = None
) -> Tuple[str, Dict[str, str], int, str]:
    """Resolve @api/source reference to URL, headers, timeout, and method.

    Args:
        reference: Profile reference like "@genomoncology/alterations"
        params: Optional query parameters

    Returns:
        Tuple of (url, headers_dict, timeout, method)

    Raises:
        ProfileError: If profile not found
    """
    if not reference.startswith("@"):
        raise ProfileError(
            f"Invalid profile reference (must start with @): {reference}"
        )

    # Parse reference: @api_name/source_name?query
    ref = reference[1:]  # Remove @

    # Check for query params in reference
    if "?" in ref:
        ref_part, query_part = ref.split("?", 1)
        # Parse query string
        query_params = {
            k: v[0] if len(v) == 1 else v
            for k, v in parse_qs(query_part).items()
        }
    else:
        ref_part = ref
        query_params = {}

    # Parse api/source path
    parts = ref_part.split("/", 1)

    if len(parts) == 1:
        # Just @api_name - load _meta only
        api_name = parts[0]
        source_name = None
    else:
        api_name, source_name = parts

    # Load profile
    profile = load_hierarchical_profile(api_name, source_name)

    # Merge params: function params override query params
    merged_params = {**query_params, **(params or {})}

    # Build URL
    base_url = profile.get("base_url", "")
    path = profile.get("path", "")

    # Construct full URL
    base = base_url.rstrip("/")
    path = path.lstrip("/")
    url = f"{base}/{path}" if path else base

    # Add query params if provided
    if merged_params:
        query_string = urlencode(merged_params, doseq=True)
        url = f"{url}?{query_string}"

    # Get headers, timeout, and method
    headers = profile.get("headers", {})
    timeout = profile.get("timeout", 30)
    method = profile.get("method", "GET")

    return url, headers, timeout, method


def error_record(error_type: str, message: str, **extra) -> dict:
    """Create standardized error record."""
    return {"_error": True, "type": error_type, "message": message, **extra}


def reads(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    auth: tuple | None = None,
    timeout: int = 30,
    verify_ssl: bool = True,
    force_format: str | None = None,
    limit: int | None = None,
    **params,
) -> Iterator[dict]:
    """Fetch data from HTTP/HTTPS URL or profile reference and yield NDJSON records.

    Supports two formats:
    - Naked URL: https://example.com/data.json
    - Profile reference: @genomoncology/alterations?gene=BRAF
    - Container listing: @genomoncology (no endpoint - lists available sources)

    Args:
        url: The URL to fetch or profile reference (required)
        method: HTTP method (default: 'GET')
        headers: Dict of HTTP headers
        auth: Tuple of (username, password) for Basic auth
        timeout: Request timeout in seconds (default: 30)
        verify_ssl: Verify SSL certificates (default: True)
        force_format: Force specific format ('json', 'csv', 'ndjson', 'text')
        limit: Maximum number of records to yield (default: None)
        **params: Additional parameters for profile references

    Yields:
        Dict records from the response, or listing records for containers
    """
    # Check if this is a container listing request (profile without endpoint)
    if url.startswith("@"):
        ref = url[1:].split("?")[0]  # Remove @ and query string

        if "/" not in ref:
            # Container: @api (no endpoint specified)
            # Yield listing of available sources
            api_name = ref

            try:
                # Load profile metadata
                profile = load_hierarchical_profile(api_name, None)
            except ProfileError as e:
                yield error_record("profile_error", str(e))
                return

            # List available sources
            sources = list_profile_sources(api_name)

            # Yield each source as a listing record
            for source_name in sources:
                try:
                    source_profile = load_hierarchical_profile(api_name, source_name)
                    yield {
                        "name": source_name,
                        "path": source_profile.get("path", ""),
                        "description": source_profile.get("description", ""),
                        "method": source_profile.get("method", "GET"),
                        "params": source_profile.get("params", []),
                        "_type": "source",
                        "_container": f"@{api_name}",
                    }
                except ProfileError:
                    # Skip sources that fail to load
                    pass
            return

    # Leaf resource: fetch data
    # Check if this is a profile reference
    if url.startswith("@"):
        try:
            # Resolve profile to URL, headers, timeout, and method
            resolved_url, profile_headers, profile_timeout, profile_method = (
                resolve_profile_reference(url, params)
            )
            url = resolved_url
            # Merge headers: explicit headers override profile headers
            headers = {**profile_headers, **(headers or {})}
            # Use profile timeout if not explicitly set
            if timeout == 30:  # Default value
                timeout = profile_timeout
            # Use profile method if not explicitly set
            if method == "GET":  # Default value
                method = profile_method
        except ProfileError as e:
            yield error_record("profile_error", str(e))
            return
        except Exception as e:
            yield error_record(
                "profile_error", str(e), exception_type=type(e).__name__
            )
            return

    headers = headers or {}

    # Read request body from stdin for POST/PUT/PATCH
    data = None
    if method.upper() in ("POST", "PUT", "PATCH"):
        data = sys.stdin.read()

    # Make request with streaming
    response = requests.request(
        method,
        url,
        headers=headers,
        auth=auth,
        data=data,
        timeout=timeout,
        verify=verify_ssl,
        stream=True,
    )

    if not response.ok:
        yield error_record(
            "http_error",
            f"HTTP {response.status_code}: {response.reason}",
            url=url,
            status_code=response.status_code,
        )
        return

    # Detect format
    content_type = response.headers.get("Content-Type", "")
    file_ext = "." + urlparse(url).path.split(".")[-1].lower()

    # Determine format using lookup dict
    if force_format:
        fmt = force_format
    else:
        # Try content-type first
        fmt = None
        for key, detected_fmt in FORMAT_DETECT.items():
            if key in content_type:
                fmt = detected_fmt
                break
        # Fall back to file extension
        if not fmt:
            fmt = FORMAT_DETECT.get(file_ext, "text")

    # Format handlers dict
    handlers = {
        "json": lambda: _parse_json(response, url),
        "ndjson": lambda: _parse_ndjson(response),
        "csv": lambda: [
            {"content": response.text, "content_type": "text/csv", "url": url}
        ],
        "text": lambda: [
            {
                "content": response.text,
                "content_type": content_type,
                "url": url,
            }
        ],
    }

    # Dispatch to handler and apply limit if specified
    handler = handlers.get(fmt, handlers["text"])
    if limit:
        count = 0
        for record in handler():
            yield record
            count += 1
            if count >= limit:
                break
    else:
        yield from handler()


def _parse_json(response: requests.Response, url: str) -> Iterator[dict]:
    """Parse JSON response and yield records."""
    try:
        data = response.json()
    except json.JSONDecodeError as e:
        yield error_record("json_decode_error", str(e), url=url)
        return

    if isinstance(data, list):
        for item in data:
            yield item if isinstance(item, dict) else {"value": item}
    elif isinstance(data, dict):
        yield data
    else:
        yield {"value": data}


def _parse_ndjson(response: requests.Response) -> Iterator[dict]:
    """Parse NDJSON response line by line."""
    for line in response.iter_lines(decode_unicode=True):
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as e:
            yield error_record("ndjson_decode_error", str(e), line=line[:100])




def _stream_raw(
    url: str,
    method: str,
    headers: dict,
    auth: tuple | None,
    timeout: int,
    verify_ssl: bool,
) -> int:
    """Stream response body as raw bytes to stdout. Returns exit code."""
    try:
        with requests.request(
            method,
            url,
            headers=headers,
            auth=auth,
            timeout=timeout,
            verify=verify_ssl,
            stream=True,
        ) as response:
            if not response.ok:
                # Non-200 is an error in raw mode
                sys.stderr.write(
                    json.dumps(
                        error_record(
                            "http_error",
                            f"HTTP {response.status_code}: {response.reason}",
                            url=url,
                            status_code=response.status_code,
                        )
                    )
                    + "\n"
                )
                return 1

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
            return 0
    except requests.exceptions.RequestException as e:
        # Propagate as error in raw mode (upstream should handle)
        sys.stderr.write(
            json.dumps(error_record("request_exception", str(e), url=url))
            + "\n"
        )
        return 1


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="HTTP protocol plugin")
    parser.add_argument(
        "--mode", choices=["read", "raw"], help="Operation mode"
    )
    parser.add_argument(
        "url", nargs="?", help="URL to fetch or profile reference"
    )
    parser.add_argument(
        "--method",
        default="GET",
        choices=["GET", "POST", "PUT", "PATCH", "DELETE"],
        help="HTTP method",
    )
    parser.add_argument(
        "--headers",
        type=json.loads,
        default={},
        help="HTTP headers as JSON",
    )
    parser.add_argument("--auth", help="Basic auth as 'username:password'")
    parser.add_argument(
        "--timeout", type=int, default=30, help="Request timeout"
    )
    parser.add_argument(
        "--no-verify-ssl",
        dest="verify_ssl",
        action="store_false",
        help="Disable SSL verification",
    )
    parser.add_argument(
        "--format",
        choices=["json", "ndjson", "csv", "text"],
        help="Force format",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of records to yield",
    )

    args, unknown = parser.parse_known_args()

    # Parse unknown args as parameters (--key=value) for profile references
    params = {}
    for arg in unknown:
        if arg.startswith("--") and "=" in arg:
            key, value = arg[2:].split("=", 1)
            params[key] = value

    if not args.mode or not args.url:
        parser.error("--mode and URL are required")

    # Parse auth
    auth = None
    if args.auth:
        if ":" not in args.auth:
            parser.error("--auth must be 'username:password'")
        auth = tuple(args.auth.split(":", 1))

    # Substitute env vars in headers
    headers = {}
    for key, value in args.headers.items():
        if (
            isinstance(value, str)
            and value.startswith("${")
            and value.endswith("}")
        ):
            env_var = value[2:-1]
            env_value = os.environ.get(env_var)
            if not env_value:
                print(
                    json.dumps(
                        error_record(
                            "env_var_not_set",
                            f"Environment variable {env_var} not set",
                        )
                    ),
                    flush=True,
                )
                sys.exit(1)
            headers[key] = env_value
        else:
            headers[key] = value

    # Dispatch by mode
    if args.mode == "raw":
        exit_code = _stream_raw(
            url=args.url,
            method=args.method,
            headers=headers,
            auth=auth,
            timeout=args.timeout,
            verify_ssl=args.verify_ssl,
        )
        sys.exit(exit_code)

    else:  # read mode
        # Call reads() with direct args (no config dict)
        try:
            for record in reads(
                url=args.url,
                method=args.method,
                headers=headers,
                auth=auth,
                timeout=args.timeout,
                verify_ssl=args.verify_ssl,
                force_format=args.format,
                limit=args.limit,
                **params,
            ):
                print(json.dumps(record), flush=True)
        except requests.exceptions.RequestException as e:
            # Errors are data: emit an error record and exit successfully
            print(
                json.dumps(
                    error_record("request_exception", str(e), url=args.url)
                ),
                flush=True,
            )
            sys.exit(0)
