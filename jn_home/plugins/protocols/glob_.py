#!/usr/bin/env -S uv run --script
"""Glob protocol plugin - read multiple files matching glob patterns.

This plugin enables reading data from nested directory structures using glob
patterns, with automatic format detection and path metadata injection.

Key Features:
- Glob patterns: **/*.jsonl, data/**/*.csv, etc.
- Multi-format support: Each file resolved by extension
- Path metadata injection: _path, _dir, _filename, _ext added to records
- Streaming: Constant memory regardless of file count
- Push-down filtering: Use jq to filter by path components

Usage:
    # Read all JSONL files recursively
    jn cat "processes/**/*.jsonl"

    # Read all data files in a specific folder
    jn cat "data/completed/*.json"

    # Mix file types (each parsed according to extension)
    jn cat "data/**/*.{json,csv,jsonl}"

    # Filter by path components using jq
    jn cat "processes/**/*.jsonl" | jn filter 'select(._dir | contains("failed"))'

    # Get files from specific subfolder
    jn cat "logs/**/*.jsonl" | jn filter 'select(._path | contains("2024-01"))'

Parameters:
    root        - Base directory for glob (default: current dir)
    recursive   - Enable ** patterns (default: true)
    hidden      - Include hidden files/dirs (default: false)

Output Metadata (injected into each record):
    _path       - Full relative path to file (e.g., "processes/failed/abc.jsonl")
    _dir        - Directory containing file (e.g., "processes/failed")
    _filename   - Filename with extension (e.g., "abc.jsonl")
    _basename   - Filename without extension (e.g., "abc")
    _ext        - File extension (e.g., ".jsonl")
    _file_index - 0-based index of file in glob results
    _line_index - 0-based index of record within file
"""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# type = "protocol"
# matches = [
#   "^glob://.*",
#   ".*[*?].*",
#   ".*\\*\\*.*"
# ]
# manages_parameters = true
# ///

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator, Optional


def find_format_plugin(filepath: str, plugin_dir: Path) -> Optional[Path]:
    """Find plugin for file based on extension.

    Searches custom plugins first, then falls back to bundled plugins.
    """
    # Get file extension
    ext = Path(filepath).suffix.lower()
    if not ext:
        return None

    # Map extensions to plugin names
    ext_to_plugin = {
        '.json': 'json_',
        '.jsonl': 'json_',
        '.ndjson': 'json_',
        '.csv': 'csv_',
        '.tsv': 'csv_',
        '.yaml': 'yaml_',
        '.yml': 'yaml_',
        '.toml': 'toml_',
        '.xlsx': 'xlsx_',
        '.xls': 'xlsx_',
        '.md': 'markdown_',
        '.markdown': 'markdown_',
    }

    plugin_name = ext_to_plugin.get(ext)
    if not plugin_name:
        # Default to treating as text/ndjson for unknown extensions
        plugin_name = 'json_'

    # Search paths: custom plugins, then bundled
    search_paths = []

    # Custom plugins directory
    if plugin_dir.exists():
        search_paths.append(plugin_dir / "formats")
        search_paths.append(plugin_dir)

    # Bundled plugins (fallback)
    jn_home = os.getenv("JN_HOME")
    if jn_home:
        bundled = Path(jn_home) / "plugins" / "formats"
        if bundled.exists():
            search_paths.append(bundled)

    # Also check relative to this script
    script_dir = Path(__file__).parent.parent
    bundled_formats = script_dir / "formats"
    if bundled_formats.exists() and bundled_formats not in search_paths:
        search_paths.append(bundled_formats)

    # Search for plugin
    for search_dir in search_paths:
        plugin_path = search_dir / f"{plugin_name}.py"
        if plugin_path.exists():
            return plugin_path

    return None


def parse_file_with_plugin(
    filepath: Path,
    plugin_path: Path,
    config: dict,
) -> Iterator[dict]:
    """Parse a file using the specified plugin.

    Runs plugin as subprocess to maintain streaming and isolation.
    """
    cmd = [
        sys.executable,
        str(plugin_path),
        "--mode", "read",
    ]

    # Parameters that are internal to glob plugin and shouldn't be passed to format plugins
    glob_internal_params = {
        "source", "root", "hidden", "limit", "file_limit",
        "_plugin_dir", "_path", "_dir", "_filename", "_basename", "_ext",
        "_file_index", "_line_index"
    }

    # Add config parameters (only pass format-relevant params)
    for key, value in config.items():
        if key.startswith("_"):
            continue  # Skip internal params
        if key in glob_internal_params:
            continue  # Skip glob-specific params
        cmd.extend([f"--{key}", str(value)])

    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            proc = subprocess.Popen(
                cmd,
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            for line in proc.stdout:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        # If plugin outputs non-JSON, wrap it
                        yield {"_raw": line}

            proc.wait()

            if proc.returncode != 0:
                stderr = proc.stderr.read()
                yield {
                    "_error": True,
                    "type": "plugin_error",
                    "message": stderr.strip() if stderr else f"Plugin exited with code {proc.returncode}",
                    "file": str(filepath),
                }
    except Exception as e:
        yield {
            "_error": True,
            "type": "file_error",
            "message": str(e),
            "file": str(filepath),
        }


def parse_file_direct(filepath: Path) -> Iterator[dict]:
    """Parse file directly without subprocess (for simple JSONL/JSON).

    This is an optimization for the common case of JSONL files.
    """
    ext = filepath.suffix.lower()

    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            if ext in ('.jsonl', '.ndjson'):
                # JSONL: one JSON object per line
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            obj = json.loads(line)
                            if isinstance(obj, dict):
                                yield obj
                            else:
                                yield {"value": obj}
                        except json.JSONDecodeError as e:
                            yield {
                                "_error": True,
                                "type": "json_error",
                                "message": str(e),
                                "line": line[:100],
                            }
            elif ext == '.json':
                # Regular JSON: array or object
                content = f.read()
                data = json.loads(content)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            yield item
                        else:
                            yield {"value": item}
                elif isinstance(data, dict):
                    yield data
                else:
                    yield {"value": data}
            else:
                # Unknown format - try as JSONL
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            yield {"_raw": line}
    except Exception as e:
        yield {
            "_error": True,
            "type": "file_error",
            "message": str(e),
            "file": str(filepath),
        }


def inject_path_metadata(record: dict, filepath: Path, root: Path, file_idx: int, line_idx: int) -> dict:
    """Inject path metadata into record.

    Adds:
        _path      - Relative path from root
        _dir       - Directory part of path
        _filename  - Filename with extension
        _basename  - Filename without extension
        _ext       - File extension (including dot)
        _file_index - Index of file in glob results
        _line_index - Index of record within file
    """
    try:
        rel_path = filepath.relative_to(root)
    except ValueError:
        rel_path = filepath

    return {
        "_path": str(rel_path),
        "_dir": str(rel_path.parent) if rel_path.parent != Path('.') else "",
        "_filename": filepath.name,
        "_basename": filepath.stem,
        "_ext": filepath.suffix,
        "_file_index": file_idx,
        "_line_index": line_idx,
        **record,
    }


def expand_glob(pattern: str, root: Path, include_hidden: bool = False) -> Iterator[Path]:
    """Expand glob pattern to file paths.

    Handles both simple globs (*.json) and recursive globs (**/*.jsonl).
    """
    # Handle glob:// prefix
    if pattern.startswith("glob://"):
        pattern = pattern[7:]

    # Handle relative vs absolute patterns
    if pattern.startswith("/"):
        glob_root = Path("/")
        pattern = pattern[1:]
    else:
        glob_root = root

    # Expand glob
    for path in sorted(glob_root.glob(pattern)):
        if path.is_file():
            # Skip hidden files unless requested
            if not include_hidden:
                if any(part.startswith('.') for part in path.parts):
                    continue
            yield path


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read files matching glob pattern and yield NDJSON records.

    Args:
        config: Configuration dict with:
            - source: Glob pattern (required)
            - root: Base directory (default: cwd)
            - hidden: Include hidden files (default: false)
            - limit: Max records to yield
            - file_limit: Max files to process

    Yields:
        Dict records with path metadata injected
    """
    config = config or {}

    # Get pattern from source
    pattern = config.get("source", "")
    if not pattern:
        yield {
            "_error": True,
            "type": "config_error",
            "message": "No glob pattern provided",
        }
        return

    # Resolve root directory
    root_str = config.get("root", ".")
    root = Path(root_str).resolve()

    # Options
    include_hidden = config.get("hidden", False)
    if isinstance(include_hidden, str):
        include_hidden = include_hidden.lower() in ("true", "1", "yes")

    limit = config.get("limit")
    if limit is not None:
        limit = int(limit)

    file_limit = config.get("file_limit")
    if file_limit is not None:
        file_limit = int(file_limit)

    # Get plugin directory
    plugin_dir_str = config.get("_plugin_dir", os.getenv("JN_PLUGIN_DIR", ""))
    plugin_dir = Path(plugin_dir_str) if plugin_dir_str else Path.cwd() / ".jn" / "plugins"

    # Expand glob and process files
    record_count = 0
    file_count = 0

    for filepath in expand_glob(pattern, root, include_hidden):
        if file_limit and file_count >= file_limit:
            break

        ext = filepath.suffix.lower()

        # For JSONL/JSON, use direct parsing (faster)
        # For other formats, use plugin subprocess
        if ext in ('.jsonl', '.ndjson', '.json'):
            records = parse_file_direct(filepath)
        else:
            plugin_path = find_format_plugin(str(filepath), plugin_dir)
            if plugin_path:
                records = parse_file_with_plugin(filepath, plugin_path, config)
            else:
                # Fall back to direct parsing
                records = parse_file_direct(filepath)

        line_idx = 0
        for record in records:
            enriched = inject_path_metadata(record, filepath, root, file_count, line_idx)
            yield enriched

            line_idx += 1
            record_count += 1

            if limit and record_count >= limit:
                return

        file_count += 1


def main():
    parser = argparse.ArgumentParser(description="Glob protocol plugin")
    parser.add_argument("--mode", choices=["read"], default="read")
    parser.add_argument("source", nargs="?", help="Glob pattern")
    parser.add_argument("--root", default=".", help="Base directory")
    parser.add_argument("--hidden", action="store_true", help="Include hidden files")
    parser.add_argument("--limit", type=int, help="Max records")
    parser.add_argument("--file-limit", type=int, help="Max files")

    args, unknown = parser.parse_known_args()

    config = {
        "source": args.source or "",
        "root": args.root,
        "hidden": args.hidden,
    }

    if args.limit:
        config["limit"] = args.limit
    if args.file_limit:
        config["file_limit"] = args.file_limit

    # Parse additional --key=value args
    for arg in unknown:
        if arg.startswith("--") and "=" in arg:
            key, value = arg[2:].split("=", 1)
            config[key] = value

    try:
        for record in reads(config):
            print(json.dumps(record), flush=True)
    except BrokenPipeError:
        # Handle early termination (e.g., | head)
        pass
    except Exception as e:
        print(json.dumps({
            "_error": True,
            "type": "fatal_error",
            "message": str(e),
        }), file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
