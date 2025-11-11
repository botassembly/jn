#!/usr/bin/env -S uv run --script
"""Filter NDJSON streams using jq expressions.

This plugin is a thin wrapper around the jq command-line tool.
All profile resolution, parameter substitution, and argument parsing
is handled by the JN framework before invoking this plugin.
"""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = []  # jq doesn't match files, invoked explicitly via 'jn filter'
# ///

import subprocess
import sys

if __name__ == "__main__":
    # Get query from first argument (already resolved by framework)
    # Framework resolves @profile/name references and substitutes parameters
    query = sys.argv[1] if len(sys.argv) > 1 else "."

    # Run jq with compact output (-c) for NDJSON compatibility
    # Use Popen (not run) to ensure concurrent execution and backpressure
    # Inherit stdin/stdout for streaming - OS handles backpressure through pipes
    proc = subprocess.Popen(
        ["jq", "-c", query],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    # Wait for jq to complete
    sys.exit(proc.wait())
