#!/usr/bin/env python3
"""JN v5 CLI - Agent-native ETL commands."""

import sys
import subprocess
from pathlib import Path
from typing import Optional, List

from .discovery import get_cached_plugins
from .registry import build_registry


def get_plugin_dir() -> Path:
    """Get path to built-in plugins directory."""
    return Path(__file__).parent / 'plugins'


def get_cache_path() -> Path:
    """Get path to plugin cache."""
    # Cache in same directory as plugins for now
    return Path(__file__).parent / 'cache.json'


def resolve_plugin(source: str, registry) -> Optional[str]:
    """Resolve source to plugin name.

    Args:
        source: Filename, URL, or pattern
        registry: Pattern registry

    Returns:
        Plugin name or None
    """
    return registry.match(source)


def run_plugin(plugin_path: str, mode: str, args: List[str] = None) -> subprocess.Popen:
    """Execute a plugin in specified mode.

    Args:
        plugin_path: Path to plugin .py file
        mode: 'read' or 'write'
        args: Additional CLI args for plugin

    Returns:
        Popen process
    """
    cmd = [sys.executable, plugin_path, '--mode', mode]
    if args:
        cmd.extend(args)

    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if mode == 'write' else None,
        stdout=subprocess.PIPE if mode == 'read' else None,
        stderr=subprocess.PIPE
    )


def cmd_cat(args):
    """Read file(s) and output NDJSON.

    Usage:
        jn cat file.csv              # Read CSV, output NDJSON to stdout
        jn cat file.csv output.yaml  # Read CSV, write YAML
    """
    if len(args) == 0:
        print("Usage: jn cat <input> [output]", file=sys.stderr)
        sys.exit(1)

    # Load plugins
    plugin_dir = get_plugin_dir()
    cache_path = get_cache_path()
    plugins = get_cached_plugins(plugin_dir, cache_path)
    registry = build_registry(plugins)

    input_file = args[0]
    output_file = args[1] if len(args) > 1 else None

    # Resolve input plugin
    input_plugin_name = resolve_plugin(input_file, registry)
    if not input_plugin_name:
        print(f"Error: No plugin found for {input_file}", file=sys.stderr)
        sys.exit(1)

    input_plugin = plugins[input_plugin_name]

    if output_file:
        # Two-stage pipeline: input → output
        output_plugin_name = resolve_plugin(output_file, registry)
        if not output_plugin_name:
            print(f"Error: No plugin found for {output_file}", file=sys.stderr)
            sys.exit(1)

        output_plugin = plugins[output_plugin_name]

        # Start reader
        with open(input_file, 'r') as infile:
            reader = subprocess.Popen(
                [sys.executable, input_plugin.path, '--mode', 'read'],
                stdin=infile,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Start writer
            with open(output_file, 'w') as outfile:
                writer = subprocess.Popen(
                    [sys.executable, output_plugin.path, '--mode', 'write'],
                    stdin=reader.stdout,
                    stdout=outfile,
                    stderr=subprocess.PIPE
                )

                # Close reader stdout in parent (for SIGPIPE)
                reader.stdout.close()

                # Wait for both processes
                writer.wait()
                reader.wait()

                # Get error output
                writer_stderr = writer.stderr.read()
                reader_stderr = reader.stderr.read()

                if writer.returncode != 0:
                    error_msg = writer_stderr.decode() if writer_stderr else "Unknown error"
                    print(f"Writer error: {error_msg}", file=sys.stderr)
                    sys.exit(1)

                if reader.returncode != 0:
                    error_msg = reader_stderr.decode() if reader_stderr else "Unknown error"
                    print(f"Reader error: {error_msg}", file=sys.stderr)
                    sys.exit(1)

    else:
        # Single stage: input → stdout (NDJSON)
        with open(input_file, 'r') as infile:
            reader = subprocess.Popen(
                [sys.executable, input_plugin.path, '--mode', 'read'],
                stdin=infile,
                stdout=None,  # Inherit stdout
                stderr=subprocess.PIPE
            )

            stderr_output = reader.communicate()[1]

            if reader.returncode != 0:
                print(f"Error: {stderr_output.decode()}", file=sys.stderr)
                sys.exit(1)


def cmd_put(args):
    """Read NDJSON from stdin, write to file.

    Usage:
        jn cat file.csv | jn put output.json
    """
    if len(args) == 0:
        print("Usage: jn put <output>", file=sys.stderr)
        sys.exit(1)

    # Load plugins
    plugin_dir = get_plugin_dir()
    cache_path = get_cache_path()
    plugins = get_cached_plugins(plugin_dir, cache_path)
    registry = build_registry(plugins)

    output_file = args[0]

    # Resolve output plugin
    output_plugin_name = resolve_plugin(output_file, registry)
    if not output_plugin_name:
        print(f"Error: No plugin found for {output_file}", file=sys.stderr)
        sys.exit(1)

    output_plugin = plugins[output_plugin_name]

    # Write from stdin to file
    with open(output_file, 'w') as outfile:
        writer = subprocess.Popen(
            [sys.executable, output_plugin.path, '--mode', 'write'],
            stdin=None,  # Inherit stdin
            stdout=outfile,
            stderr=subprocess.PIPE
        )

        stderr_output = writer.communicate()[1]

        if writer.returncode != 0:
            print(f"Error: {stderr_output.decode()}", file=sys.stderr)
            sys.exit(1)


def cmd_run(args):
    """Run a pipeline: input → filters → output.

    Usage:
        jn run input.csv output.json
    """
    if len(args) < 2:
        print("Usage: jn run <input> <output>", file=sys.stderr)
        sys.exit(1)

    # For now, just delegate to cat
    cmd_cat(args)


def cmd_filter(args):
    """Filter NDJSON using jq expression.

    Usage:
        jn cat file.csv | jn filter '.age > 25'
    """
    if len(args) == 0:
        print("Usage: jn filter <jq-expression>", file=sys.stderr)
        sys.exit(1)

    query = args[0]

    # Get jq plugin path
    plugin_dir = get_plugin_dir()
    jq_plugin = plugin_dir / 'filters' / 'jq_.py'

    if not jq_plugin.exists():
        print("Error: jq filter plugin not found", file=sys.stderr)
        sys.exit(1)

    # Run jq filter with stdin/stdout
    jq_process = subprocess.Popen(
        [sys.executable, str(jq_plugin), '--query', query],
        stdin=None,  # Inherit stdin
        stdout=None,  # Inherit stdout
        stderr=subprocess.PIPE
    )

    stderr_output = jq_process.communicate()[1]

    if jq_process.returncode != 0:
        error_msg = stderr_output.decode() if stderr_output else "Unknown error"
        print(f"Filter error: {error_msg}", file=sys.stderr)
        sys.exit(1)


def cmd_head(args):
    """Output first N records from NDJSON stream.

    Usage:
        jn cat file.csv | jn head 10
    """
    n = int(args[0]) if args else 10

    count = 0
    for line in sys.stdin:
        if count >= n:
            break
        print(line, end='')
        count += 1


def cmd_tail(args):
    """Output last N records from NDJSON stream.

    Usage:
        jn cat file.csv | jn tail 10
    """
    n = int(args[0]) if args else 10

    # Buffer last N lines
    buffer = []
    for line in sys.stdin:
        buffer.append(line)
        if len(buffer) > n:
            buffer.pop(0)

    for line in buffer:
        print(line, end='')


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: jn <command> [args...]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  cat <input> [output]  - Read file(s)", file=sys.stderr)
        print("  put <output>          - Write to file from stdin", file=sys.stderr)
        print("  run <input> <output>  - Run pipeline", file=sys.stderr)
        print("  filter <expr>         - Filter with jq", file=sys.stderr)
        print("  head [N]              - First N records (default: 10)", file=sys.stderr)
        print("  tail [N]              - Last N records (default: 10)", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        'cat': cmd_cat,
        'put': cmd_put,
        'run': cmd_run,
        'filter': cmd_filter,
        'head': cmd_head,
        'tail': cmd_tail,
    }

    if command not in commands:
        print(f"Error: Unknown command '{command}'", file=sys.stderr)
        sys.exit(1)

    commands[command](args)


if __name__ == '__main__':
    main()
