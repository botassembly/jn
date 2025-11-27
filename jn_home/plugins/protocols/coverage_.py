#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["tree-sitter", "tree-sitter-python", "tree-sitter-javascript", "tree-sitter-go", "tree-sitter-rust"]
# [tool.jn]
# type = "protocol"
# matches = ["^@coverage/.*$", "^jn://coverage/.*$"]
# manages_parameters = true
# ///

"""Coverage profile plugin - language-agnostic function coverage analysis.

Combines tree-sitter code extraction with LCOV data to produce
function-level coverage reports for any codebase.

Usage:
    jn cat @coverage/functions                    # Current dir defaults
    jn cat "@coverage/functions?root=src&lcov=coverage.lcov"
    jn cat @coverage/uncovered                    # Zero coverage only
    jn cat @coverage/files                        # Per-file summary

Components:
    functions  - Per-function coverage (file, function, total, hit, coverage)
    uncovered  - Functions with 0% coverage
    files      - Per-file coverage summary
    lines      - Raw line coverage (pass-through from lcov)

Parameters:
    root       - Source root directory (default: ".")
    globs      - File patterns, comma-separated (default: auto-detect from lcov)
    lcov       - LCOV file path (default: coverage.lcov or lcov.info)
    min        - Minimum coverage % filter (default: 0)
    max        - Maximum coverage % filter (default: 100)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterator, Optional
from collections import defaultdict


# =============================================================================
# Tree-sitter extraction (embedded from ts_.py)
# =============================================================================

def get_language_for_file(file_path: str) -> Optional[str]:
    """Determine language from file extension."""
    ext_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'javascript',
        '.tsx': 'javascript',
        '.go': 'go',
        '.rs': 'rust',
    }
    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext)


def get_parser(language: str):
    """Get tree-sitter parser for language."""
    import tree_sitter

    if language == 'python':
        import tree_sitter_python as tspython
        return tree_sitter.Parser(tree_sitter.Language(tspython.language()))
    elif language == 'javascript':
        import tree_sitter_javascript as tsjs
        return tree_sitter.Parser(tree_sitter.Language(tsjs.language()))
    elif language == 'go':
        import tree_sitter_go as tsgo
        return tree_sitter.Parser(tree_sitter.Language(tsgo.language()))
    elif language == 'rust':
        import tree_sitter_rust as tsrust
        return tree_sitter.Parser(tree_sitter.Language(tsrust.language()))
    else:
        return None


def extract_functions(tree, code: bytes, file_path: str, language: str) -> Iterator[dict]:
    """Extract function/method/class definitions from AST."""

    if language == 'python':
        yield from _extract_python(tree, code, file_path)
    elif language == 'javascript':
        yield from _extract_javascript(tree, code, file_path)
    elif language == 'go':
        yield from _extract_go(tree, code, file_path)
    elif language == 'rust':
        yield from _extract_rust(tree, code, file_path)


def _extract_python(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract Python functions, methods, and classes."""

    def visit(node, current_class=None):
        if node.type == 'class_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                yield {
                    'file': file_path,
                    'function': class_name,
                    'type': 'class',
                    'class': None,
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                }
                for child in node.children:
                    yield from visit(child, class_name)

        elif node.type == 'function_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                if current_class:
                    display_name = f"{current_class}.{func_name}"
                    func_type = 'method'
                else:
                    display_name = func_name
                    func_type = 'function'

                yield {
                    'file': file_path,
                    'function': display_name,
                    'type': func_type,
                    'class': current_class,
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                }
        else:
            for child in node.children:
                yield from visit(child, current_class)

    yield from visit(tree.root_node)


def _extract_javascript(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract JavaScript/TypeScript functions."""

    def visit(node, current_class=None):
        if node.type in ('function_declaration', 'function'):
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                yield {
                    'file': file_path,
                    'function': func_name,
                    'type': 'function',
                    'class': current_class,
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                }

        elif node.type == 'method_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                method_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                display_name = f"{current_class}.{method_name}" if current_class else method_name
                yield {
                    'file': file_path,
                    'function': display_name,
                    'type': 'method',
                    'class': current_class,
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                }

        elif node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                yield {
                    'file': file_path,
                    'function': class_name,
                    'type': 'class',
                    'class': None,
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                }
                for child in node.children:
                    yield from visit(child, class_name)
                return

        elif node.type == 'arrow_function':
            parent = node.parent
            if parent and parent.type == 'variable_declarator':
                name_node = parent.child_by_field_name('name')
                if name_node:
                    func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    yield {
                        'file': file_path,
                        'function': func_name,
                        'type': 'function',
                        'class': current_class,
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1,
                    }

        for child in node.children:
            yield from visit(child, current_class)

    yield from visit(tree.root_node)


def _extract_go(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract Go functions and methods."""

    def visit(node):
        if node.type == 'function_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                yield {
                    'file': file_path,
                    'function': func_name,
                    'type': 'function',
                    'class': None,
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                }

        elif node.type == 'method_declaration':
            name_node = node.child_by_field_name('name')
            receiver_node = node.child_by_field_name('receiver')
            if name_node:
                method_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                receiver_type = None
                if receiver_node:
                    for child in receiver_node.children:
                        if child.type == 'parameter_declaration':
                            type_node = child.child_by_field_name('type')
                            if type_node:
                                receiver_type = code[type_node.start_byte:type_node.end_byte].decode('utf-8')
                                receiver_type = receiver_type.lstrip('*')

                display_name = f"{receiver_type}.{method_name}" if receiver_type else method_name
                yield {
                    'file': file_path,
                    'function': display_name,
                    'type': 'method',
                    'class': receiver_type,
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                }

        for child in node.children:
            yield from visit(child)

    yield from visit(tree.root_node)


def _extract_rust(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract Rust functions and methods."""

    def visit(node, current_impl=None):
        if node.type == 'function_item':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                if current_impl:
                    display_name = f"{current_impl}::{func_name}"
                    func_type = 'method'
                else:
                    display_name = func_name
                    func_type = 'function'

                yield {
                    'file': file_path,
                    'function': display_name,
                    'type': func_type,
                    'class': current_impl,
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                }

        elif node.type == 'impl_item':
            type_node = node.child_by_field_name('type')
            impl_name = None
            if type_node:
                impl_name = code[type_node.start_byte:type_node.end_byte].decode('utf-8')

            for child in node.children:
                yield from visit(child, impl_name)
            return

        for child in node.children:
            yield from visit(child, current_impl)

    yield from visit(tree.root_node)


def extract_from_file(file_path: str) -> Iterator[dict]:
    """Extract functions from a single file."""
    path = Path(file_path)
    if not path.exists():
        return

    lang = get_language_for_file(file_path)
    if not lang:
        return

    parser = get_parser(lang)
    if not parser:
        return

    code = path.read_bytes()
    tree = parser.parse(code)
    yield from extract_functions(tree, code, file_path, lang)


# =============================================================================
# LCOV parsing
# =============================================================================

def parse_lcov_lines(lcov_path: str) -> Iterator[dict]:
    """Parse LCOV file and yield line coverage records."""
    current_file = None

    with open(lcov_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('SF:'):
                current_file = line[3:]
            elif line.startswith('DA:') and current_file:
                parts = line[3:].split(',')
                if len(parts) >= 2:
                    line_num = int(parts[0])
                    hits = int(parts[1])
                    yield {
                        'file': current_file,
                        'line': line_num,
                        'hits': hits,
                        'executed': hits > 0,
                    }
            elif line == 'end_of_record':
                current_file = None


def get_files_from_lcov(lcov_path: str) -> set[str]:
    """Extract unique file paths from LCOV."""
    files = set()
    with open(lcov_path, 'r') as f:
        for line in f:
            if line.startswith('SF:'):
                files.add(line[3:].strip())
    return files


# =============================================================================
# Coverage computation
# =============================================================================

def compute_function_coverage(
    root: str,
    globs: list[str],
    lcov_path: str,
) -> Iterator[dict]:
    """Compute per-function coverage by joining code structure with LCOV data."""

    # Step 1: Load LCOV lines into lookup by file
    lcov_by_file: dict[str, list[dict]] = defaultdict(list)
    for record in parse_lcov_lines(lcov_path):
        lcov_by_file[record['file']].append(record)

    # Step 2: Find source files
    root_path = Path(root)
    source_files = set()

    for glob_pattern in globs:
        for path in root_path.glob(glob_pattern):
            if path.is_file():
                # Normalize path to match LCOV format
                rel_path = str(path)
                source_files.add(rel_path)

    # Step 3: Extract functions and compute coverage
    for file_path in sorted(source_files):
        # Get LCOV lines for this file
        lines = lcov_by_file.get(file_path, [])

        # Extract functions
        for func in extract_from_file(file_path):
            start = func['start_line']
            end = func['end_line']

            # Find lines within function range
            matching_lines = [
                l for l in lines
                if start <= l['line'] <= end
            ]

            total = len(matching_lines)
            hit = sum(1 for l in matching_lines if l['executed'])
            coverage = int((hit / total) * 100) if total > 0 else 0

            yield {
                'file': func['file'],
                'function': func['function'],
                'type': func['type'],
                'start_line': start,
                'end_line': end,
                'total': total,
                'hit': hit,
                'coverage': coverage,
            }


def compute_file_coverage(lcov_path: str) -> Iterator[dict]:
    """Compute per-file coverage summary."""
    file_stats: dict[str, dict] = defaultdict(lambda: {'total': 0, 'hit': 0})

    for record in parse_lcov_lines(lcov_path):
        stats = file_stats[record['file']]
        stats['total'] += 1
        if record['executed']:
            stats['hit'] += 1

    for file_path, stats in sorted(file_stats.items()):
        total = stats['total']
        hit = stats['hit']
        coverage = int((hit / total) * 100) if total > 0 else 0
        yield {
            'file': file_path,
            'total': total,
            'hit': hit,
            'coverage': coverage,
        }


# =============================================================================
# Profile resolution
# =============================================================================

def find_lcov_file() -> Optional[str]:
    """Find LCOV file in current directory."""
    candidates = ['coverage.lcov', 'lcov.info', 'coverage/lcov.info']
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def detect_globs_from_lcov(lcov_path: str) -> list[str]:
    """Detect file patterns from LCOV file paths."""
    files = get_files_from_lcov(lcov_path)

    # Detect extensions
    extensions = set()
    for f in files:
        ext = Path(f).suffix.lower()
        if ext:
            extensions.add(ext)

    # Build glob patterns
    globs = []
    for ext in extensions:
        globs.append(f"**/*{ext}")

    return globs if globs else ["**/*.py"]


def parse_address(address: str) -> tuple[str, dict]:
    """Parse @coverage/component?params address."""
    # Remove prefix
    if address.startswith('@coverage/'):
        address = address[10:]
    elif address.startswith('jn://coverage/'):
        address = address[14:]

    # Split component and params
    if '?' in address:
        component, query = address.split('?', 1)
        params = dict(p.split('=', 1) for p in query.split('&') if '=' in p)
    else:
        component = address
        params = {}

    return component, params


# =============================================================================
# Main entry point
# =============================================================================

def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read coverage data based on component and parameters."""
    config = config or {}

    # Parse address if provided
    source = config.get('source', '@coverage/functions')
    component, params = parse_address(source)

    # Merge config with parsed params (config takes precedence)
    params.update({k: v for k, v in config.items() if k != 'source'})

    # Resolve parameters with defaults
    root = params.get('root', '.')
    lcov_path = params.get('lcov') or find_lcov_file()

    if not lcov_path or not Path(lcov_path).exists():
        raise FileNotFoundError(f"LCOV file not found. Specify with ?lcov=path")

    # Resolve globs
    globs_str = params.get('globs', '')
    if globs_str:
        globs = [g.strip() for g in globs_str.split(',')]
    else:
        globs = detect_globs_from_lcov(lcov_path)

    # Coverage filters
    min_cov = int(params.get('min', 0))
    max_cov = int(params.get('max', 100))

    # Generate output based on component
    if component == 'functions':
        for record in compute_function_coverage(root, globs, lcov_path):
            if min_cov <= record['coverage'] <= max_cov:
                yield record

    elif component == 'uncovered':
        for record in compute_function_coverage(root, globs, lcov_path):
            if record['coverage'] == 0 and record['total'] > 0:
                yield record

    elif component == 'files':
        for record in compute_file_coverage(lcov_path):
            if min_cov <= record['coverage'] <= max_cov:
                yield record

    elif component == 'lines':
        # Pass-through LCOV lines
        for record in parse_lcov_lines(lcov_path):
            yield record

    else:
        raise ValueError(f"Unknown component: {component}. Use: functions, uncovered, files, lines")


def main():
    parser = argparse.ArgumentParser(description='Coverage profile plugin')
    parser.add_argument('--mode', choices=['read'], default='read')
    parser.add_argument('--source', help='Source address')
    parser.add_argument('--root', help='Source root directory')
    parser.add_argument('--lcov', help='LCOV file path')
    parser.add_argument('--globs', help='File patterns (comma-separated)')
    parser.add_argument('--min', type=int, help='Minimum coverage %')
    parser.add_argument('--max', type=int, help='Maximum coverage %')

    args = parser.parse_args()

    config = {
        'source': args.source or '@coverage/functions',
    }
    if args.root:
        config['root'] = args.root
    if args.lcov:
        config['lcov'] = args.lcov
    if args.globs:
        config['globs'] = args.globs
    if args.min is not None:
        config['min'] = args.min
    if args.max is not None:
        config['max'] = args.max

    try:
        for record in reads(config):
            print(json.dumps(record), flush=True)
    except FileNotFoundError as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
