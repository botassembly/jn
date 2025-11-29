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
import bz2
import gzip
import json
import lzma
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator, Optional, Tuple

# Supported compression extensions mapped to their module openers
COMPRESSION_OPENERS = {
    '.gz': gzip.open,
    '.gzip': gzip.open,
    '.bz2': bz2.open,
    '.xz': lzma.open,
    '.lzma': lzma.open,
}


def detect_compression(filepath: Path) -> Tuple[bool, str, Optional[str]]:
    """Detect if file is compressed and return (is_compressed, format_extension, compression_type).

    For 'data.jsonl.gz' returns (True, '.jsonl', '.gz')
    For 'data.csv.bz2' returns (True, '.csv', '.bz2')
    For 'data.csv' returns (False, '.csv', None)
    """
    ext = filepath.suffix.lower()
    if ext in COMPRESSION_OPENERS:
        # Get the underlying format extension (e.g., .jsonl from data.jsonl.gz)
        stem = filepath.stem
        format_ext = Path(stem).suffix.lower()
        return (True, format_ext if format_ext else '.json', ext)  # Default to json if no inner ext
    return (False, ext, None)


def find_format_plugin(filepath: str, plugin_dir: Path, format_ext: str = None) -> Optional[Path]:
    """Find plugin for file based on extension.

    Searches custom plugins first, then falls back to bundled plugins.

    Args:
        filepath: Path to the file
        plugin_dir: Directory containing custom plugins
        format_ext: Override extension to use for plugin lookup (e.g., '.jsonl' for compressed files)
    """
    # Use provided format extension or detect from filepath
    ext = format_ext if format_ext else Path(filepath).suffix.lower()
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
    compression_type: Optional[str] = None,
) -> Iterator[dict]:
    """Parse a file using the specified plugin.

    Runs plugin as subprocess using uv to maintain streaming, isolation,
    and proper dependency management (PEP 723).

    Args:
        filepath: Path to the file to parse
        plugin_path: Path to the format plugin script
        config: Configuration parameters
        compression_type: Compression extension (e.g., '.gz', '.bz2', '.xz') or None
    """
    cmd = [
        "uv", "run", "--quiet", "--script",
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
        # Open file with appropriate decompression
        if compression_type:
            # Get the appropriate opener for this compression type
            opener = COMPRESSION_OPENERS.get(compression_type, gzip.open)
            with opener(filepath, 'rt', encoding='utf-8', errors='replace') as f:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                # Feed decompressed content to plugin stdin
                try:
                    stdout, stderr = proc.communicate(input=f.read())
                except Exception as e:
                    proc.kill()
                    yield {
                        "_error": True,
                        "type": "decompress_error",
                        "message": str(e),
                        "file": str(filepath),
                    }
                    return

                for line in stdout.splitlines():
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            yield {"_raw": line}

                if proc.returncode != 0:
                    yield {
                        "_error": True,
                        "type": "plugin_error",
                        "message": stderr.strip() if stderr else f"Plugin exited with code {proc.returncode}",
                        "file": str(filepath),
                    }
        else:
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


def parse_file_direct(filepath: Path, compression_type: Optional[str] = None, format_ext: str = None) -> Iterator[dict]:
    """Parse file directly without subprocess (for simple JSONL/JSON).

    This is an optimization for the common case of JSONL files.

    Args:
        filepath: Path to the file
        compression_type: Compression extension (e.g., '.gz', '.bz2', '.xz') or None
        format_ext: Format extension to use for parsing (e.g., '.jsonl' for compressed files)
    """
    ext = format_ext if format_ext else filepath.suffix.lower()

    try:
        # Open with appropriate decompression
        if compression_type:
            opener = COMPRESSION_OPENERS.get(compression_type, gzip.open)
            f = opener(filepath, 'rt', encoding='utf-8', errors='replace')
        else:
            f = open(filepath, 'r', encoding='utf-8', errors='replace')

        with f:
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


def pattern_explicitly_names_hidden(pattern: str) -> bool:
    """Check if glob pattern explicitly names a hidden directory or file.

    Returns True if pattern starts with '.' (but not './' or '..') or contains
    '/.' followed by a non-special character, indicating the user explicitly
    wants to access hidden paths.

    Examples:
        '.botassembly/**/*.jsonl' -> True (starts with hidden dir)
        'data/.cache/*.json' -> True (contains hidden subdir)
        '**/*.jsonl' -> False (no explicit hidden reference)
        './*.json' -> False (current dir notation, not hidden intent)
        '../foo/*.json' -> False (parent dir notation, not hidden intent)
        '.hidden/*.json' -> True (hidden directory)
    """
    # Pattern starts with a dot (hidden file/dir at root)
    # Exclude './' (current dir) and '..' (parent dir)
    if pattern.startswith('.') and not pattern.startswith('./') and not pattern.startswith('..'):
        return True

    # Pattern contains /. followed by something other than / or .
    # This catches data/.cache but not ./ or ../
    idx = 0
    while True:
        idx = pattern.find('/.', idx)
        if idx == -1:
            break
        # Check what follows /.
        next_idx = idx + 2
        if next_idx < len(pattern):
            next_char = pattern[next_idx]
            # If next char is not / or ., it's a hidden path
            if next_char not in ('/', '.'):
                return True
        idx += 1

    return False


def expand_glob(pattern: str, root: Path, include_hidden: bool = False) -> Iterator[Path]:
    """Expand glob pattern to file paths.

    Handles both simple globs (*.json) and recursive globs (**/*.jsonl).

    Hidden directory handling:
    - If include_hidden=True, includes all hidden files/dirs
    - If pattern explicitly names a hidden path (starts with . or contains /.),
      hidden support is auto-enabled for that pattern
    - Otherwise, hidden files/dirs are skipped
    """
    # Handle glob:// prefix
    if pattern.startswith("glob://"):
        pattern = pattern[7:]

    # Auto-detect hidden directory intent from pattern
    # If user explicitly names a hidden path, enable hidden support
    if pattern_explicitly_names_hidden(pattern):
        include_hidden = True

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

        # Detect compression and get format extension
        is_compressed, format_ext, compression_type = detect_compression(filepath)

        # For JSONL/JSON, use direct parsing (faster)
        # For other formats, use plugin subprocess
        if format_ext in ('.jsonl', '.ndjson', '.json'):
            records = parse_file_direct(filepath, compression_type=compression_type, format_ext=format_ext)
        else:
            plugin_path = find_format_plugin(str(filepath), plugin_dir, format_ext=format_ext)
            if plugin_path:
                records = parse_file_with_plugin(filepath, plugin_path, config, compression_type=compression_type)
            else:
                # Fall back to direct parsing
                records = parse_file_direct(filepath, compression_type=compression_type, format_ext=format_ext)

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
