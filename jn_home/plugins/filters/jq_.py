#!/usr/bin/env -S uv run --script
"""Filter NDJSON streams using jq expressions.

This plugin wraps the jq command-line tool with support for:
- Direct jq expressions (e.g., '.name')
- Profile file references (e.g., /path/to/filter.jq)
- Native argument binding via --jq-arg flags

Invocation modes:
    # Direct expression (string substitution already done by framework)
    jq_.py ".name"

    # Profile file with native jq arguments
    jq_.py /path/to/filter.jq --jq-arg region East --jq-arg threshold 1000

The --jq-arg flags are converted to jq's native --arg flags, enabling
type-safe parameter binding without string substitution issues.
"""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = []  # jq doesn't match files, invoked explicitly via 'jn filter'
# ///

import subprocess
import sys


def parse_args(args: list[str]) -> tuple[str, list[str], bool]:
    """Parse plugin arguments.

    Args:
        args: Command line arguments (excluding script name)

    Returns:
        Tuple of (query_or_path, jq_args, slurp) where:
        - query_or_path: jq expression string OR path to .jq file
        - jq_args: List of --arg key value arguments for jq
        - slurp: Whether to enable slurp mode (jq -s)
    """
    if not args:
        return ".", [], False

    query_or_path = args[0]
    jq_args = []
    slurp = False

    # Parse --jq-arg key value pairs and --jq-slurp flag
    i = 1
    while i < len(args):
        if args[i] == "--jq-arg" and i + 2 < len(args):
            key = args[i + 1]
            value = args[i + 2]
            jq_args.extend(["--arg", key, value])
            i += 3
        elif args[i] == "--jq-slurp":
            slurp = True
            i += 1
        else:
            # Unknown argument - skip
            i += 1

    return query_or_path, jq_args, slurp


def build_jq_command(query_or_path: str, jq_args: list[str], slurp: bool = False) -> list[str]:
    """Build the jq command line.

    Args:
        query_or_path: jq expression or path to .jq file
        jq_args: Additional --arg flags for jq
        slurp: Enable slurp mode (-s) to read all input into array

    Returns:
        Complete jq command as list

    Note on slurp mode:
        When slurp=True, jq reads the entire NDJSON stream into a single array
        before processing. This enables aggregation operations like group_by,
        sort_by, unique, and length on the full dataset.

        WARNING: Slurp mode loads all data into memory, breaking streaming
        guarantees. Only use for bounded datasets that fit in memory.
    """
    # Base command with compact output for NDJSON compatibility
    cmd = ["jq", "-c"]

    # Add slurp mode if requested (must come before expression)
    if slurp:
        cmd.append("-s")

    # Add argument bindings
    cmd.extend(jq_args)

    # If query is a file path, use -f flag
    if query_or_path.endswith(".jq"):
        cmd.extend(["-f", query_or_path])
    else:
        # Direct expression
        cmd.append(query_or_path)

    return cmd


if __name__ == "__main__":
    # Parse arguments
    query_or_path, jq_args, slurp = parse_args(sys.argv[1:])

    # Build jq command
    cmd = build_jq_command(query_or_path, jq_args, slurp=slurp)

    # Run jq with streaming I/O
    # Use Popen (not run) to ensure concurrent execution and backpressure
    # Inherit stdin/stdout for streaming - OS handles backpressure through pipes
    proc = subprocess.Popen(
        cmd,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    # Wait for jq to complete
    sys.exit(proc.wait())
