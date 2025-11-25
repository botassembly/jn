#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# [tool.jn]
# matches = [".*\\.lcov$", ".*\\.info$"]
# ///
"""LCOV coverage format plugin.

LCOV is a universal coverage format used across languages (C/C++, JavaScript, Python, Go, Rust).
This plugin converts LCOV format to NDJSON for analysis with JN.

Output modes:
- functions (default): One record per function with coverage statistics
- files: One record per file with aggregated coverage
- lines: One record per line with execution data
- branches: One record per branch with hit data

Example:
    jn cat coverage.lcov                           # Functions (default)
    jn cat coverage.lcov --mode=files              # File summaries
    jn cat coverage.lcov --mode=lines              # Line-level data
    jn cat coverage.lcov --mode=branches           # Branch data
"""

import json
import sys
from collections import defaultdict
from typing import Iterator, Optional


def parse_lcov(input_stream) -> dict:
    """Parse LCOV format into structured data.

    Returns dict with file -> {functions, lines, branches, summary}

    LCOV Format Order:
    1. SF: (source file)
    2. DA: records (line execution data)
    3. LF/LH (lines found/hit)
    4. FN: records (function definitions)
    5. FNDA: records (function execution counts)
    6. FNF/FNH (functions found/hit)
    7. BRDA: records (branch data)
    8. BRF/BRH (branches found/hit)
    9. end_of_record
    """
    files = {}
    current_file = None
    current_functions = {}  # Use dict to match FN with FNDA
    current_lines = []
    current_branches = []

    for line in input_stream:
        line = line.strip()

        if line.startswith('SF:'):
            # Source File
            current_file = line[3:]
            current_functions = {}
            current_lines = []
            current_branches = []

        elif line.startswith('DA:'):
            # Line execution: DA:line_number,hit_count
            parts = line[3:].split(',')
            if len(parts) >= 2:
                line_num = int(parts[0])
                hit_count = int(parts[1])
                current_lines.append({
                    'line': line_num,
                    'hits': hit_count,
                    'executed': hit_count > 0
                })

        elif line.startswith('FN:'):
            # Function definition: FN:start_line,end_line,function_name (coverage.py extension)
            #                  or: FN:line,function_name (standard LCOV)
            parts = line[3:].split(',', 2)
            if len(parts) >= 3:
                # Extended format with end line (coverage.py)
                start_line = int(parts[0])
                end_line = int(parts[1])
                function_name = parts[2]
            elif len(parts) == 2:
                # Standard LCOV format (line,name only)
                start_line = int(parts[0])
                end_line = start_line  # Assume single-line function
                function_name = parts[1]
            else:
                continue  # Invalid format, skip

            current_functions[function_name] = {
                'name': function_name,
                'start_line': start_line,
                'end_line': end_line,
                'lines': end_line - start_line + 1,
                'hit_count': 0  # Will be filled by FNDA
            }

        elif line.startswith('FNDA:'):
            # Function execution count: FNDA:hit_count,function_name
            parts = line[5:].split(',', 1)
            if len(parts) == 2:
                hit_count = int(parts[0])
                function_name = parts[1]
                # Update hit count if function exists
                if function_name in current_functions:
                    current_functions[function_name]['hit_count'] = hit_count

        elif line.startswith('BRDA:'):
            # Branch data: BRDA:line,block,branch,hit_count
            parts = line[5:].split(',')
            if len(parts) >= 4:
                line_num = int(parts[0])
                block = int(parts[1])
                branch_label = parts[2]
                hit_count = 0 if parts[3] == '-' else int(parts[3])
                current_branches.append({
                    'line': line_num,
                    'block': block,
                    'branch': branch_label,
                    'hits': hit_count,
                    'taken': hit_count > 0
                })

        elif line == 'end_of_record':
            if current_file:
                # Calculate summary statistics
                total_lines = len(current_lines)
                executed_lines = sum(1 for l in current_lines if l['executed'])
                total_branches = len(current_branches)
                taken_branches = sum(1 for b in current_branches if b['taken'])

                # Convert functions dict to list and assign lines/branches
                functions_list = list(current_functions.values())
                for func in functions_list:
                    func['line_data'] = [
                        l for l in current_lines
                        if func['start_line'] <= l['line'] <= func['end_line']
                    ]
                    func['branch_data'] = [
                        b for b in current_branches
                        if func['start_line'] <= b['line'] <= func['end_line']
                    ]

                files[current_file] = {
                    'functions': functions_list,
                    'lines': current_lines,
                    'branches': current_branches,
                    'summary': {
                        'total_lines': total_lines,
                        'executed_lines': executed_lines,
                        'coverage': (executed_lines / total_lines * 100) if total_lines > 0 else 0,
                        'total_branches': total_branches,
                        'taken_branches': taken_branches,
                        'branch_coverage': (taken_branches / total_branches * 100) if total_branches > 0 else 0,
                        'total_functions': len(functions_list),
                        'executed_functions': sum(1 for f in functions_list if f['hit_count'] > 0)
                    }
                }
                current_file = None

    return files


def emit_functions(files: dict) -> Iterator[dict]:
    """Emit one record per function with coverage statistics."""
    for file_path, file_data in files.items():
        for func in file_data['functions']:
            # Calculate function-level coverage
            line_data = func['line_data']
            total_lines = len(line_data)
            executed_lines = sum(1 for l in line_data if l['executed'])
            missing_lines = total_lines - executed_lines

            branch_data = func['branch_data']
            total_branches = len(branch_data)
            taken_branches = sum(1 for b in branch_data if b['taken'])

            # Extract just the filename from path
            filename = file_path.split('/')[-1]

            yield {
                'file': file_path,
                'filename': filename,
                'function': func['name'],
                'start_line': func['start_line'],
                'end_line': func['end_line'],
                'lines': func['lines'],
                'total_lines': total_lines,
                'executed_lines': executed_lines,
                'missing_lines': missing_lines,
                'coverage': (executed_lines / total_lines * 100) if total_lines > 0 else 0,
                'hit_count': func['hit_count'],
                'executed': func['hit_count'] > 0,
                'total_branches': total_branches,
                'taken_branches': taken_branches,
                'partial_branches': total_branches - taken_branches,
                'branch_coverage': (taken_branches / total_branches * 100) if total_branches > 0 else 0
            }


def emit_files(files: dict) -> Iterator[dict]:
    """Emit one record per file with aggregated coverage."""
    for file_path, file_data in files.items():
        summary = file_data['summary']
        filename = file_path.split('/')[-1]

        yield {
            'file': file_path,
            'filename': filename,
            'total_lines': summary['total_lines'],
            'executed_lines': summary['executed_lines'],
            'coverage': summary['coverage'],
            'total_branches': summary['total_branches'],
            'taken_branches': summary['taken_branches'],
            'branch_coverage': summary['branch_coverage'],
            'total_functions': summary['total_functions'],
            'executed_functions': summary['executed_functions'],
            'function_coverage': (summary['executed_functions'] / summary['total_functions'] * 100)
                                  if summary['total_functions'] > 0 else 0,
            'functions': [f['name'] for f in file_data['functions']]
        }


def emit_lines(files: dict) -> Iterator[dict]:
    """Emit one record per line with execution data."""
    for file_path, file_data in files.items():
        filename = file_path.split('/')[-1]
        for line in file_data['lines']:
            yield {
                'file': file_path,
                'filename': filename,
                'line': line['line'],
                'hits': line['hits'],
                'executed': line['executed']
            }


def emit_branches(files: dict) -> Iterator[dict]:
    """Emit one record per branch with hit data."""
    for file_path, file_data in files.items():
        filename = file_path.split('/')[-1]
        for branch in file_data['branches']:
            yield {
                'file': file_path,
                'filename': filename,
                'line': branch['line'],
                'block': branch['block'],
                'branch': branch['branch'],
                'hits': branch['hits'],
                'taken': branch['taken']
            }


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read LCOV from stdin, yield NDJSON records.

    Config options:
        mode: Output mode - 'functions' (default), 'files', 'lines', or 'branches'
    """
    config = config or {}
    mode = config.get('mode', 'functions')

    # Parse LCOV data
    files = parse_lcov(sys.stdin)

    # Emit records based on mode
    if mode == 'files':
        yield from emit_files(files)
    elif mode == 'lines':
        yield from emit_lines(files)
    elif mode == 'branches':
        yield from emit_branches(files)
    else:  # functions (default)
        yield from emit_functions(files)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='LCOV format plugin')
    parser.add_argument('--mode', choices=['read', 'write', 'functions', 'files', 'lines', 'branches'],
                       default='read', help='Plugin mode')
    parser.add_argument('--output-mode', choices=['functions', 'files', 'lines', 'branches'],
                       default='functions', help='Output format')

    args = parser.parse_args()

    # LCOV write mode is not implemented (and not useful - LCOV is an input format)
    if args.mode == 'write':
        print("ERROR: LCOV write mode not implemented", file=sys.stderr)
        print("LCOV is a coverage input format (from coverage.py/gcov/etc.)", file=sys.stderr)
        print("To save filtered coverage data, use JSON format instead:", file=sys.stderr)
        print("  jn cat coverage.lcov | jn filter '...' | jn put output.json", file=sys.stderr)
        sys.exit(1)

    # If mode is 'read', use output_mode for the actual format
    # Otherwise, for backward compatibility, use mode
    if args.mode == 'read':
        output_mode = args.output_mode
    else:
        output_mode = args.mode

    config = {'mode': output_mode}

    for record in reads(config):
        print(json.dumps(record))
