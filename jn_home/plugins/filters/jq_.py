#!/usr/bin/env -S uv run --script
"""Filter NDJSON streams using jq expressions."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = []  # jq doesn't match files, invoked explicitly via 'jn filter'
# ///

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator, Optional


def _resolve_profile(profile_ref: str, params: dict) -> str:
    """Resolve @profile/name reference to jq query string.

    Args:
        profile_ref: Profile reference like "@builtin/pivot" or "@analytics/custom"
        params: Parameters to substitute in the query (e.g., {"row": "product"})

    Returns:
        Resolved jq query string with parameters substituted
    """
    # Remove @ prefix
    profile_path = profile_ref.lstrip("@")

    # Search for profile in multiple locations
    search_paths = [
        # User profiles
        Path.home() / ".local" / "jn" / "profiles" / "jq" / f"{profile_path}.jq",
        # Project profiles (if JN_HOME is set)
        Path(os.environ.get("JN_HOME", ".")) / "profiles" / "jq" / f"{profile_path}.jq",
        # Bundled profiles (relative to this script)
        Path(__file__).parent.parent.parent / "profiles" / "jq" / f"{profile_path}.jq",
    ]

    # Find first existing profile
    profile_file = None
    for path in search_paths:
        if path.exists():
            profile_file = path
            break

    if not profile_file:
        print(f"Error: Profile not found: {profile_ref}", file=sys.stderr)
        print(f"Searched in:", file=sys.stderr)
        for path in search_paths:
            print(f"  - {path}", file=sys.stderr)
        sys.exit(1)

    # Load query from file
    query = profile_file.read_text()

    # Strip comments (lines starting with #)
    query_lines = [line for line in query.split("\n") if not line.strip().startswith("#")]
    query = "\n".join(query_lines).strip()

    # Substitute parameters
    for param_name, param_value in params.items():
        # Replace $param_name with "param_value" in the query
        # This supports parameters like $row_key, $col_key, etc.
        query = query.replace(f"${param_name}", f'"{param_value}"')

    return query


def filters(config: Optional[dict] = None) -> Iterator[dict]:
    """Filter NDJSON stream using jq expression or profile.

    Config:
        query: jq expression or @profile/name reference
        params: Dict of parameters for profile substitution
    """
    if config is None:
        config = {}
    query = config.get("query", ".")
    params = config.get("params", {})

    # Check if query is a profile reference
    if query.startswith("@"):
        query = _resolve_profile(query, params)

    if not shutil.which("jq"):
        print(
            "Error: jq command not found. Install from: https://jqlang.github.io/jq/",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        # Check if stdin is a real file handle (has fileno)
        try:
            sys.stdin.fileno()
            stdin_source = sys.stdin
            input_data = None
        except (AttributeError, OSError, io.UnsupportedOperation):
            # stdin is not a real file (e.g., Click test runner StringIO)
            stdin_source = subprocess.PIPE
            input_data = sys.stdin.read()

        jq_process = subprocess.Popen(
            ["jq", "-c", query], stdin=stdin_source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if input_data is not None:
            jq_process.stdin.write(input_data)
            jq_process.stdin.close()

        for line in jq_process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if isinstance(record, dict):
                    yield record
                elif isinstance(record, list):
                    for item in record:
                        if isinstance(item, dict):
                            yield item
                        else:
                            yield {"value": item}
                else:
                    yield {"value": record}
            except json.JSONDecodeError:
                yield {"value": line}

        jq_process.wait()
        if jq_process.returncode != 0:
            stderr_data = jq_process.stderr.read()
            print(f"jq error: {stderr_data}", file=sys.stderr)
            sys.exit(1)

    except (subprocess.SubprocessError, BrokenPipeError, IOError) as e:
        # Try to clean up jq process, but don't mask the error
        try:
            if jq_process.poll() is None:  # Only kill if still running
                jq_process.kill()
                jq_process.wait(timeout=1)
        except (ProcessLookupError, TimeoutError, NameError):
            # Process already dead, won't die, or jq_process not yet defined
            pass

        print(f"jq error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="jq filter plugin - transform NDJSON streams with profile support"
    )
    parser.add_argument(
        "--query", "-q", default=".",
        help="jq query expression or @profile/name reference (default: .)"
    )

    # Add common parameter arguments for profiles
    parser.add_argument("--row", help="Row key for pivot operations")
    parser.add_argument("--col", help="Column key for pivot operations")
    parser.add_argument("--value", help="Value key for pivot operations")
    parser.add_argument("--by", help="Group by key")
    parser.add_argument("--sum", help="Field to sum")
    parser.add_argument("--field", help="Field for statistics")

    # Allow arbitrary parameters via --param key=value
    parser.add_argument(
        "--param", "-p", action="append", dest="params",
        help="Custom parameter (format: key=value, can be used multiple times)"
    )

    args = parser.parse_args()

    # Build params dict from arguments
    params = {}
    if args.row:
        params["row_key"] = args.row
    if args.col:
        params["col_key"] = args.col
    if args.value:
        params["value_key"] = args.value
    if args.by:
        params["by"] = args.by
    if args.sum:
        params["sum"] = args.sum
    if args.field:
        params["field"] = args.field

    # Parse custom --param arguments
    if args.params:
        for param in args.params:
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value

    config = {"query": args.query, "params": params}
    for record in filters(config):
        print(json.dumps(record), flush=True)
