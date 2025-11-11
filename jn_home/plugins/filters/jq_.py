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
import shutil
import subprocess
import sys
from typing import Iterator, Optional


def filters(config: Optional[dict] = None) -> Iterator[dict]:
    """Filter NDJSON stream using jq expression."""
    if config is None:
        config = {}
    query = config.get("query", ".")
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
    parser = argparse.ArgumentParser(description="jq filter plugin - transform NDJSON streams")
    parser.add_argument("--query", "-q", default=".", help="jq query expression (default: .)")
    args = parser.parse_args()
    config = {"query": args.query}
    for record in filters(config):
        print(json.dumps(record), flush=True)
