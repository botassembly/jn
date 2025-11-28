"""JN Plugin Core Library - Proof of Concept.

This module provides common abstractions for JN plugin development,
reducing boilerplate by 60-70%.

Usage:
    from jn_plugin import Plugin, read_ndjson, write_ndjson

    plugin = Plugin("csv", "Parse CSV files")
    plugin.arg("--delimiter", default=",")

    @plugin.reader
    def reads(config):
        # Your logic here
        yield {"col1": "val1"}

    @plugin.writer
    def writes(config):
        # Your logic here
        pass

    if __name__ == "__main__":
        plugin.run()
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator


@dataclass
class Plugin:
    """Base class for JN plugins with common abstractions."""

    name: str
    description: str = ""
    _read_fn: Callable | None = field(default=None, repr=False)
    _write_fn: Callable | None = field(default=None, repr=False)
    _raw_fn: Callable | None = field(default=None, repr=False)
    _args: list[tuple] = field(default_factory=list, repr=False)
    _matches: list[str] = field(default_factory=list, repr=False)

    def arg(self, *args, **kwargs) -> "Plugin":
        """Add custom CLI argument."""
        self._args.append((args, kwargs))
        return self

    def matches(self, *patterns: str) -> "Plugin":
        """Set file patterns this plugin handles."""
        self._matches.extend(patterns)
        return self

    def reader(self, fn: Callable[[dict], Iterator[dict]]) -> Callable:
        """Register read function (decorator)."""
        self._read_fn = fn
        return fn

    def writer(self, fn: Callable[[dict], None]) -> Callable:
        """Register write function (decorator)."""
        self._write_fn = fn
        return fn

    def raw(self, fn: Callable[[dict], None]) -> Callable:
        """Register raw mode function (decorator)."""
        self._raw_fn = fn
        return fn

    def run(self, args: list[str] | None = None) -> None:
        """Parse args and execute appropriate mode."""
        parser = argparse.ArgumentParser(
            prog=self.name,
            description=self.description,
        )
        parser.add_argument(
            "--mode",
            choices=["read", "write", "raw"],
            help="Operation mode (required unless --jn-meta)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit output records",
        )
        parser.add_argument(
            "--jn-meta",
            action="store_true",
            help="Output plugin metadata as JSON",
        )

        # Add custom arguments
        for arg_args, arg_kwargs in self._args:
            parser.add_argument(*arg_args, **arg_kwargs)

        parsed = parser.parse_args(args)

        # Handle metadata request
        if parsed.jn_meta:
            self._output_metadata()
            return

        # Require --mode if not --jn-meta
        if not parsed.mode:
            parser.error("--mode is required")

        # Build config from parsed args
        config = vars(parsed).copy()
        del config["jn_meta"]

        try:
            if parsed.mode == "read" and self._read_fn:
                self._run_reader(config)
            elif parsed.mode == "write" and self._write_fn:
                self._run_writer(config)
            elif parsed.mode == "raw" and self._raw_fn:
                self._raw_fn(config)
            else:
                sys.stderr.write(f"Mode '{parsed.mode}' not supported by this plugin\n")
                sys.exit(1)
        except BrokenPipeError:
            # Graceful SIGPIPE handling
            os._exit(0)
        except KeyboardInterrupt:
            os._exit(0)
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.exit(1)

    def _run_reader(self, config: dict) -> None:
        """Execute reader with NDJSON output and limit support."""
        limit = config.get("limit")
        count = 0

        for record in self._read_fn(config):
            write_ndjson(record)
            count += 1
            if limit and count >= limit:
                break

    def _run_writer(self, config: dict) -> None:
        """Execute writer."""
        self._write_fn(config)

    def _output_metadata(self) -> None:
        """Output plugin metadata as JSON."""
        meta = {
            "name": self.name,
            "description": self.description,
            "modes": [],
            "matches": self._matches,
        }
        if self._read_fn:
            meta["modes"].append("read")
        if self._write_fn:
            meta["modes"].append("write")
        if self._raw_fn:
            meta["modes"].append("raw")
        print(json.dumps(meta, indent=2))


# =============================================================================
# I/O Helpers
# =============================================================================


def read_ndjson() -> Iterator[dict]:
    """Read NDJSON lines from stdin (streaming)."""
    for line in sys.stdin:
        line = line.strip()
        if line:
            yield json.loads(line)


def read_ndjson_all() -> list[dict]:
    """Read all NDJSON lines into list."""
    return list(read_ndjson())


def read_binary() -> bytes:
    """Read binary data from stdin."""
    return sys.stdin.buffer.read()


def read_text() -> str:
    """Read all text from stdin."""
    return sys.stdin.read()


def read_lines() -> Iterator[str]:
    """Read text lines from stdin (streaming)."""
    for line in sys.stdin:
        yield line.rstrip("\n\r")


def write_ndjson(record: dict) -> None:
    """Write single NDJSON record to stdout (with flush)."""
    try:
        print(json.dumps(record), flush=True)
    except BrokenPipeError:
        os._exit(0)


def write_binary(data: bytes) -> None:
    """Write binary data to stdout."""
    try:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        os._exit(0)


def write_text(text: str) -> None:
    """Write text to stdout."""
    try:
        sys.stdout.write(text)
    except BrokenPipeError:
        os._exit(0)


# =============================================================================
# Error Helpers
# =============================================================================


def error_record(error_type: str, message: str, **extra: Any) -> dict:
    """Create standardized error record."""
    return {"_error": True, "type": error_type, "message": message, **extra}


def fatal(message: str, code: int = 1) -> None:
    """Print error to stderr and exit."""
    sys.stderr.write(f"Error: {message}\n")
    sys.exit(code)
