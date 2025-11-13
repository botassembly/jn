#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["watchfiles>=0.21"]
# [tool.jn]
# matches = [
#   "^watch($| )", "^watch .*",
#   "^watchfiles($| )", "^watchfiles .*"
# ]
# ///

"""
JN Shell Plugin: watch (watchfiles)

Watch a directory for filesystem changes and stream NDJSON events.

Usage:
    jn sh watch /path/to/dir
    jn sh watch /path/to/dir --recursive --debounce-ms 100
    jn sh watch . --initial --exit-after 1   # emit snapshot then exit

Notes:
    - Directory-only: for file contents, use `jn sh tail -F <file>`
    - Events are emitted as one JSON object per line (NDJSON)
    - Backpressure propagates via OS pipes; memory stays constant
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Iterable, List


def safe_print_json(obj: dict) -> None:
    try:
        print(json.dumps(obj), flush=True)
    except BrokenPipeError:
        os._exit(0)


def _emit(record: dict) -> None:
    safe_print_json(record)


def _snapshot(root: Path, recursive: bool) -> Iterable[Path]:
    if not recursive:
        try:
            with os.scandir(root) as it:
                for entry in it:
                    yield Path(entry.path)
        except FileNotFoundError:
            return
        return

    for dirpath, dirnames, filenames in os.walk(root):
        p = Path(dirpath)
        for d in dirnames:
            yield p / d
        for f in filenames:
            yield p / f


def _matches(path: str, includes: List[str], excludes: List[str]) -> bool:
    if includes and not any(fnmatch.fnmatch(path, pat) for pat in includes):
        return False
    if excludes and any(fnmatch.fnmatch(path, pat) for pat in excludes):
        return False
    return True


def reads(command_str: str | None = None) -> None:
    if not command_str:
        _emit({"_error": "watch requires a directory path"})
        sys.exit(1)

    parser = argparse.ArgumentParser(prog="watch", add_help=True)
    parser.add_argument("path", help="Directory to watch")
    parser.add_argument("--recursive", dest="recursive", action="store_true")
    parser.add_argument("--no-recursive", dest="recursive", action="store_false")
    parser.set_defaults(recursive=True)
    parser.add_argument("--debounce-ms", type=int, default=50)
    parser.add_argument("--exit-after", type=int, default=None)
    parser.add_argument("--initial", action="store_true")
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])

    try:
        args = parser.parse_args(shlex.split(command_str)[1:])
    except SystemExit as e:
        sys.exit(e.code)

    root = Path(args.path)
    if not root.exists():
        _emit({"_error": f"Path does not exist: {root}"})
        sys.exit(1)
    if root.is_file():
        _emit(
            {
                "_error": f"Path is a file, not a directory: {root}",
                "hint": "Use 'jn sh tail -F <file>' to follow file contents",
            }
        )
        sys.exit(1)

    count = 0
    if args.initial:
        for p in _snapshot(root, args.recursive):
            path_str = str(p)
            if not _matches(path_str, args.include, args.exclude):
                continue
            _emit(
                {
                    "event": "exists",
                    "path": path_str,
                    "is_dir": p.is_dir(),
                    "root": str(root),
                }
            )
            count += 1
            if args.exit_after is not None and count >= args.exit_after:
                return

    try:
        from watchfiles import Change, watch

        change_map = {
            Change.added: "created",
            Change.modified: "modified",
            Change.deleted: "deleted",
        }

        for changes in watch(
            str(root), recursive=args.recursive, debounce=args.debounce_ms
        ):
            for ch, path in changes:  # type: ignore[misc]
                if not _matches(path, args.include, args.exclude):
                    continue
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

