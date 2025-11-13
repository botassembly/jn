#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["watchfiles>=0.21"]
# [tool.jn]
# matches = ["^watchfiles($| )", "^watchfiles .*"]
# ///

"""
JN Shell Plugin: watchfiles

Watch a directory for filesystem changes and stream NDJSON events.

Usage:
    jn sh watchfiles /path/to/dir
    jn sh watchfiles /path/to/dir --recursive --debounce-ms 100
    jn sh watchfiles . --initial --exit-after 1   # emit snapshot then exit

Notes:
    - Directory-only: for file contents, use `jn sh tail -F <file>`
    - Events are emitted as one JSON object per line (NDJSON)
    - Backpressure propagates via OS pipes; memory stays constant
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
import shlex
from typing import Iterable


def _emit(record: dict) -> None:
    print(json.dumps(record), flush=True)


def _snapshot(root: Path, recursive: bool) -> Iterable[Path]:
    if not recursive:
        # non-recursive: list only one level
        try:
            with os.scandir(root) as it:
                for entry in it:
                    yield Path(entry.path)
        except FileNotFoundError:
            return
        return

    # recursive
    for dirpath, dirnames, filenames in os.walk(root):
        p = Path(dirpath)
        for d in dirnames:
            yield p / d
        for f in filenames:
            yield p / f


def reads(command_str: str | None = None) -> None:
    if not command_str:
        _emit({"_error": "watchfiles requires a directory path"})
        sys.exit(1)

    # Parse command string with argparse
    parser = argparse.ArgumentParser(prog="watchfiles", add_help=True)
    parser.add_argument("path", help="Directory to watch")
    parser.add_argument(
        "--recursive",
        dest="recursive",
        action="store_true",
        help="Watch recursively (default)",
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Disable recursive watching",
    )
    parser.set_defaults(recursive=True)
    parser.add_argument(
        "--debounce-ms",
        type=int,
        default=50,
        help="Debounce in milliseconds (default: 50)",
    )
    parser.add_argument(
        "--exit-after",
        type=int,
        default=None,
        help="Exit after N events (useful for tests)",
    )
    parser.add_argument(
        "--initial",
        action="store_true",
        help="Emit a snapshot of existing entries before watching",
    )

    try:
        # Parse arguments after the command name using shlex to respect quoting
        args = parser.parse_args(shlex.split(command_str)[1:])
    except SystemExit as e:
        # argparse already printed help/error to stdout/stderr via uv run --script
        sys.exit(e.code)

    root = Path(args.path)
    if not root.exists():
        _emit({"_error": f"Path does not exist: {root}"})
        sys.exit(1)
    if root.is_file():
        _emit({
            "_error": f"Path is a file, not a directory: {root}",
            "hint": "Use 'jn sh tail -F <file>' to follow file contents"
        })
        sys.exit(1)

    # Emit initial snapshot if requested
    count = 0
    if args.initial:
        for p in _snapshot(root, args.recursive):
            _emit(
                {
                    "event": "exists",
                    "path": str(p),
                    "is_dir": p.is_dir(),
                    "root": str(root),
                }
            )
            count += 1
            if args.exit_after is not None and count >= args.exit_after:
                return

    # Start watching
    try:
        from watchfiles import Change, watch

        change_map = {
            Change.added: "created",
            Change.modified: "modified",
            Change.deleted: "deleted",
        }

        for changes in watch(
            str(root),
            recursive=args.recursive,
            debounce=args.debounce_ms,  # integer milliseconds as required
        ):
            # changes is a set[(Change, path)]
            for ch, path in changes:  # type: ignore[misc]
                event = change_map.get(ch, "modified")
                is_dir = Path(path).is_dir()
                _emit(
                    {
                        "event": event,
                        "path": path,
                        "is_dir": is_dir,
                        "root": str(root),
                    }
                )
                count += 1
                if args.exit_after is not None and count >= args.exit_after:
                    return

    except BrokenPipeError:
        # Downstream closed pipe (e.g., head -n 10)
        return
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    import argparse as _argparse

    _p = _argparse.ArgumentParser()
    _p.add_argument("--mode", default="read")
    _p.add_argument("address", nargs="?")
    _args = _p.parse_args()

    if _args.mode == "read":
        reads(_args.address)
    else:
        _emit({"_error": f"Unsupported mode: {_args.mode}. Only 'read' supported."})
        sys.exit(1)
