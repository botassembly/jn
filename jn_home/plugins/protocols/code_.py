#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["tree-sitter", "tree-sitter-python", "tree-sitter-javascript", "tree-sitter-go", "tree-sitter-rust"]
# [tool.jn]
# type = "protocol"
# matches = ["^@code/.*$", "^jn://code/.*$"]
# manages_parameters = true
# ///

"""Code structure plugin - extract functions/classes with optional coverage.

Uses tree-sitter for language-agnostic code parsing. Supports Python,
JavaScript/TypeScript, Go, and Rust.

Usage:
    # Basic code structure
    jn cat @code/functions                     # Current directory
    jn cat "@code/functions?root=src"          # Specific root
    jn cat "@code/functions?globs=**/*.py"     # Specific patterns

    # With coverage data
    jn cat "@code/functions?lcov=coverage.lcov"
    jn cat "@code/functions?lcov=coverage.lcov&min=0&max=50"  # Low coverage

    # Filter by type
    jn cat @code/classes
    jn cat @code/methods

Components:
    functions   - All functions, methods, classes (with caller_count if calls analyzed)
    classes     - Only classes
    methods     - Only methods
    files       - List of files found
    calls       - Call graph (caller -> callee relationships)
    dead        - Dead code (functions never called, with false positive filtering)

Parameters:
    root        - Source root directory (default: ".")
    globs       - File patterns, comma-separated (default: "**/*.py")
    lcov        - LCOV file path for coverage enrichment
    min         - Minimum coverage % filter (requires lcov)
    max         - Maximum coverage % filter (requires lcov)
    type        - Filter by type: function, method, class
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterator, Optional


# =============================================================================
# Tree-sitter language support
# =============================================================================

EXTENSION_MAP = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'javascript',
    '.tsx': 'javascript',
    '.go': 'go',
    '.rs': 'rust',
}

DEFAULT_GLOBS = {
    'python': '**/*.py',
    'javascript': '**/*.{js,jsx,ts,tsx}',
    'go': '**/*.go',
    'rust': '**/*.rs',
}


def get_language(file_path: str) -> Optional[str]:
    """Determine language from file extension."""
    ext = Path(file_path).suffix.lower()
    return EXTENSION_MAP.get(ext)


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
    return None


# =============================================================================
# Language-agnostic body detection
# =============================================================================

def get_body_range(node, code: bytes, language: str) -> tuple[int, int]:
    """Get the executable body range (start_line, end_line) for a function.

    This is language-agnostic: uses the 'body' field which exists in all
    supported languages (Python, JS, Go, Rust).

    Returns line numbers (1-indexed) for the body only, excluding:
    - The function definition line (def, func, fn, function)
    - Docstrings (Python)
    - The closing brace line (where applicable)
    """
    body = node.child_by_field_name('body')

    if body:
        body_start = body.start_point[0] + 1  # 1-indexed
        body_end = body.end_point[0] + 1

        # For block bodies with braces, exclude the braces themselves
        # Check if body starts with '{'
        if body.type in ('block', 'statement_block'):
            # Body includes braces, so actual content starts after '{'
            # and ends before '}'
            if body.child_count > 0:
                first_child = body.children[0]
                last_child = body.children[-1]

                # Skip opening brace if it's a separate token
                if first_child.type == '{':
                    if body.child_count > 1:
                        body_start = body.children[1].start_point[0] + 1

                # Skip closing brace
                if last_child.type == '}':
                    if body.child_count > 1:
                        body_end = body.children[-2].end_point[0] + 1

        # Python-specific: skip docstring
        if language == 'python' and body.child_count > 0:
            first_stmt = body.children[0]
            if first_stmt.type == 'expression_statement':
                # Check if it's a string (docstring)
                if first_stmt.child_count > 0:
                    expr = first_stmt.children[0]
                    if expr.type == 'string':
                        # Skip the docstring
                        if body.child_count > 1:
                            body_start = body.children[1].start_point[0] + 1
                        else:
                            # Only docstring in body, use docstring end
                            body_start = first_stmt.end_point[0] + 1

        return (body_start, body_end)

    # Fallback: use full node range but skip first line (def/func/fn)
    return (node.start_point[0] + 2, node.end_point[0] + 1)


# =============================================================================
# Code extraction by language
# =============================================================================

def extract_python(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract Python functions, methods, and classes."""

    def visit(node, current_class=None):
        if node.type == 'class_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                body_start, body_end = get_body_range(node, code, 'python')
                yield {
                    'file': file_path,
                    'function': class_name,
                    'type': 'class',
                    'class': None,
                    'start_line': body_start,
                    'end_line': body_end,
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

                body_start, body_end = get_body_range(node, code, 'python')
                yield {
                    'file': file_path,
                    'function': display_name,
                    'type': func_type,
                    'class': current_class,
                    'start_line': body_start,
                    'end_line': body_end,
                }
        else:
            for child in node.children:
                yield from visit(child, current_class)

    yield from visit(tree.root_node)


def extract_javascript(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract JavaScript/TypeScript functions and classes."""

    def visit(node, current_class=None):
        if node.type in ('function_declaration', 'function'):
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                body_start, body_end = get_body_range(node, code, 'javascript')
                yield {
                    'file': file_path,
                    'function': func_name,
                    'type': 'function',
                    'class': current_class,
                    'start_line': body_start,
                    'end_line': body_end,
                }

        elif node.type == 'method_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                method_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                display_name = f"{current_class}.{method_name}" if current_class else method_name
                body_start, body_end = get_body_range(node, code, 'javascript')
                yield {
                    'file': file_path,
                    'function': display_name,
                    'type': 'method',
                    'class': current_class,
                    'start_line': body_start,
                    'end_line': body_end,
                }

        elif node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                body_start, body_end = get_body_range(node, code, 'javascript')
                yield {
                    'file': file_path,
                    'function': class_name,
                    'type': 'class',
                    'class': None,
                    'start_line': body_start,
                    'end_line': body_end,
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
                    body_start, body_end = get_body_range(node, code, 'javascript')
                    yield {
                        'file': file_path,
                        'function': func_name,
                        'type': 'function',
                        'class': current_class,
                        'start_line': body_start,
                        'end_line': body_end,
                    }

        for child in node.children:
            yield from visit(child, current_class)

    yield from visit(tree.root_node)


def extract_go(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract Go functions and methods."""

    def visit(node):
        if node.type == 'function_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                body_start, body_end = get_body_range(node, code, 'go')
                yield {
                    'file': file_path,
                    'function': func_name,
                    'type': 'function',
                    'class': None,
                    'start_line': body_start,
                    'end_line': body_end,
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
                body_start, body_end = get_body_range(node, code, 'go')
                yield {
                    'file': file_path,
                    'function': display_name,
                    'type': 'method',
                    'class': receiver_type,
                    'start_line': body_start,
                    'end_line': body_end,
                }

        for child in node.children:
            yield from visit(child)

    yield from visit(tree.root_node)


def extract_rust(tree, code: bytes, file_path: str) -> Iterator[dict]:
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

                body_start, body_end = get_body_range(node, code, 'rust')
                yield {
                    'file': file_path,
                    'function': display_name,
                    'type': func_type,
                    'class': current_impl,
                    'start_line': body_start,
                    'end_line': body_end,
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


EXTRACTORS = {
    'python': extract_python,
    'javascript': extract_javascript,
    'go': extract_go,
    'rust': extract_rust,
}


# =============================================================================
# Call graph extraction by language
# =============================================================================

def extract_calls_python(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract function calls from Python code."""

    def get_call_name(call_node) -> Optional[str]:
        """Extract the function name from a call node."""
        func = call_node.child_by_field_name('function')
        if not func:
            return None

        # Simple name: foo()
        if func.type == 'identifier':
            return code[func.start_byte:func.end_byte].decode('utf-8')

        # Attribute access: obj.method() or module.func()
        if func.type == 'attribute':
            attr = func.child_by_field_name('attribute')
            obj = func.child_by_field_name('object')
            if attr:
                attr_name = code[attr.start_byte:attr.end_byte].decode('utf-8')
                # Include object for method calls
                if obj:
                    obj_name = code[obj.start_byte:obj.end_byte].decode('utf-8')
                    return f"{obj_name}.{attr_name}"
                return attr_name

        return None

    def find_calls_in_node(node) -> Iterator[tuple[str, int]]:
        """Find all calls within a node, yielding (callee, line)."""
        if node.type == 'call':
            callee = get_call_name(node)
            if callee:
                yield (callee, node.start_point[0] + 1)

        for child in node.children:
            yield from find_calls_in_node(child)

    def visit(node, current_class=None, current_func=None):
        if node.type == 'class_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                for child in node.children:
                    yield from visit(child, class_name, current_func)
                return

        elif node.type == 'function_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                if current_class:
                    caller = f"{current_class}.{func_name}"
                else:
                    caller = func_name

                # Find all calls in function body
                body = node.child_by_field_name('body')
                if body:
                    for callee, line in find_calls_in_node(body):
                        yield {
                            'file': file_path,
                            'caller': caller,
                            'callee': callee,
                            'line': line,
                        }
                return

        for child in node.children:
            yield from visit(child, current_class, current_func)

    yield from visit(tree.root_node)


def extract_calls_javascript(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract function calls from JavaScript/TypeScript code."""

    def get_call_name(call_node) -> Optional[str]:
        """Extract the function name from a call expression."""
        func = call_node.child_by_field_name('function')
        if not func:
            return None

        # Simple name: foo()
        if func.type == 'identifier':
            return code[func.start_byte:func.end_byte].decode('utf-8')

        # Member expression: obj.method()
        if func.type == 'member_expression':
            prop = func.child_by_field_name('property')
            obj = func.child_by_field_name('object')
            if prop:
                prop_name = code[prop.start_byte:prop.end_byte].decode('utf-8')
                if obj and obj.type == 'identifier':
                    obj_name = code[obj.start_byte:obj.end_byte].decode('utf-8')
                    return f"{obj_name}.{prop_name}"
                return prop_name

        return None

    def find_calls_in_node(node) -> Iterator[tuple[str, int]]:
        """Find all calls within a node."""
        if node.type == 'call_expression':
            callee = get_call_name(node)
            if callee:
                yield (callee, node.start_point[0] + 1)

        for child in node.children:
            yield from find_calls_in_node(child)

    def visit(node, current_class=None, current_func=None):
        if node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                for child in node.children:
                    yield from visit(child, class_name, current_func)
                return

        elif node.type in ('function_declaration', 'method_definition'):
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                if current_class:
                    caller = f"{current_class}.{func_name}"
                else:
                    caller = func_name

                body = node.child_by_field_name('body')
                if body:
                    for callee, line in find_calls_in_node(body):
                        yield {
                            'file': file_path,
                            'caller': caller,
                            'callee': callee,
                            'line': line,
                        }
                return

        elif node.type == 'arrow_function':
            parent = node.parent
            if parent and parent.type == 'variable_declarator':
                name_node = parent.child_by_field_name('name')
                if name_node:
                    caller = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    body = node.child_by_field_name('body')
                    if body:
                        for callee, line in find_calls_in_node(body):
                            yield {
                                'file': file_path,
                                'caller': caller,
                                'callee': callee,
                                'line': line,
                            }
                    return

        for child in node.children:
            yield from visit(child, current_class, current_func)

    yield from visit(tree.root_node)


def extract_calls_go(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract function calls from Go code."""

    def get_call_name(call_node) -> Optional[str]:
        """Extract the function name from a call expression."""
        func = call_node.child_by_field_name('function')
        if not func:
            return None

        # Simple name: foo()
        if func.type == 'identifier':
            return code[func.start_byte:func.end_byte].decode('utf-8')

        # Selector expression: pkg.Func() or obj.Method()
        if func.type == 'selector_expression':
            field = func.child_by_field_name('field')
            operand = func.child_by_field_name('operand')
            if field:
                field_name = code[field.start_byte:field.end_byte].decode('utf-8')
                if operand and operand.type == 'identifier':
                    op_name = code[operand.start_byte:operand.end_byte].decode('utf-8')
                    return f"{op_name}.{field_name}"
                return field_name

        return None

    def find_calls_in_node(node) -> Iterator[tuple[str, int]]:
        """Find all calls within a node."""
        if node.type == 'call_expression':
            callee = get_call_name(node)
            if callee:
                yield (callee, node.start_point[0] + 1)

        for child in node.children:
            yield from find_calls_in_node(child)

    def visit(node, receiver_type=None):
        if node.type == 'function_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                caller = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                body = node.child_by_field_name('body')
                if body:
                    for callee, line in find_calls_in_node(body):
                        yield {
                            'file': file_path,
                            'caller': caller,
                            'callee': callee,
                            'line': line,
                        }
                return

        elif node.type == 'method_declaration':
            name_node = node.child_by_field_name('name')
            receiver_node = node.child_by_field_name('receiver')
            if name_node:
                method_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                recv_type = None
                if receiver_node:
                    for child in receiver_node.children:
                        if child.type == 'parameter_declaration':
                            type_node = child.child_by_field_name('type')
                            if type_node:
                                recv_type = code[type_node.start_byte:type_node.end_byte].decode('utf-8')
                                recv_type = recv_type.lstrip('*')

                caller = f"{recv_type}.{method_name}" if recv_type else method_name
                body = node.child_by_field_name('body')
                if body:
                    for callee, line in find_calls_in_node(body):
                        yield {
                            'file': file_path,
                            'caller': caller,
                            'callee': callee,
                            'line': line,
                        }
                return

        for child in node.children:
            yield from visit(child, receiver_type)

    yield from visit(tree.root_node)


def extract_calls_rust(tree, code: bytes, file_path: str) -> Iterator[dict]:
    """Extract function calls from Rust code."""

    def get_call_name(call_node) -> Optional[str]:
        """Extract the function name from a call expression."""
        func = call_node.child_by_field_name('function')
        if not func:
            return None

        # Simple name: foo()
        if func.type == 'identifier':
            return code[func.start_byte:func.end_byte].decode('utf-8')

        # Scoped identifier: module::func()
        if func.type == 'scoped_identifier':
            name = func.child_by_field_name('name')
            path = func.child_by_field_name('path')
            if name:
                name_str = code[name.start_byte:name.end_byte].decode('utf-8')
                if path:
                    path_str = code[path.start_byte:path.end_byte].decode('utf-8')
                    return f"{path_str}::{name_str}"
                return name_str

        # Field expression: obj.method()
        if func.type == 'field_expression':
            field = func.child_by_field_name('field')
            if field:
                return code[field.start_byte:field.end_byte].decode('utf-8')

        return None

    def find_calls_in_node(node) -> Iterator[tuple[str, int]]:
        """Find all calls within a node."""
        if node.type == 'call_expression':
            callee = get_call_name(node)
            if callee:
                yield (callee, node.start_point[0] + 1)

        for child in node.children:
            yield from find_calls_in_node(child)

    def visit(node, current_impl=None):
        if node.type == 'function_item':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                if current_impl:
                    caller = f"{current_impl}::{func_name}"
                else:
                    caller = func_name

                body = node.child_by_field_name('body')
                if body:
                    for callee, line in find_calls_in_node(body):
                        yield {
                            'file': file_path,
                            'caller': caller,
                            'callee': callee,
                            'line': line,
                        }
                return

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


CALL_EXTRACTORS = {
    'python': extract_calls_python,
    'javascript': extract_calls_javascript,
    'go': extract_calls_go,
    'rust': extract_calls_rust,
}


def extract_from_file(file_path: str) -> Iterator[dict]:
    """Extract code structure from a single file."""
    path = Path(file_path)
    if not path.exists():
        return

    lang = get_language(file_path)
    if not lang:
        return

    parser = get_parser(lang)
    if not parser:
        return

    code = path.read_bytes()
    tree = parser.parse(code)

    extractor = EXTRACTORS.get(lang)
    if extractor:
        yield from extractor(tree, code, file_path)


def extract_calls_from_file(file_path: str) -> Iterator[dict]:
    """Extract call graph from a single file."""
    path = Path(file_path)
    if not path.exists():
        return

    lang = get_language(file_path)
    if not lang:
        return

    parser = get_parser(lang)
    if not parser:
        return

    code = path.read_bytes()
    tree = parser.parse(code)

    extractor = CALL_EXTRACTORS.get(lang)
    if extractor:
        yield from extractor(tree, code, file_path)


# =============================================================================
# LCOV parsing for coverage enrichment
# =============================================================================

def parse_lcov(lcov_path: str) -> dict[str, list[dict]]:
    """Parse LCOV file into per-file line data."""
    result: dict[str, list[dict]] = defaultdict(list)
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
                    result[current_file].append({
                        'line': line_num,
                        'hits': hits,
                        'executed': hits > 0,
                    })
            elif line == 'end_of_record':
                current_file = None

    return dict(result)


def enrich_with_coverage(record: dict, lcov_data: dict[str, list[dict]]) -> dict:
    """Add coverage data to a code structure record."""
    file_path = record['file']
    start = record['start_line']
    end = record['end_line']

    lines = lcov_data.get(file_path, [])
    matching = [l for l in lines if start <= l['line'] <= end]

    total = len(matching)
    hit = sum(1 for l in matching if l['executed'])
    coverage = int((hit / total) * 100) if total > 0 else 0

    return {
        **record,
        'lines': total,
        'hit': hit,
        'coverage': coverage,
    }


# =============================================================================
# Main extraction logic
# =============================================================================

def find_files(root: str, globs: list[str]) -> Iterator[str]:
    """Find all matching files under root."""
    root_path = Path(root)
    seen = set()

    for pattern in globs:
        for path in root_path.glob(pattern):
            if path.is_file() and str(path) not in seen:
                seen.add(str(path))
                yield str(path)


def parse_address(address: str) -> tuple[str, dict]:
    """Parse @code/component?params address."""
    # Remove prefix
    if address.startswith('@code/'):
        address = address[6:]
    elif address.startswith('jn://code/'):
        address = address[10:]

    # Split component and params
    if '?' in address:
        component, query = address.split('?', 1)
        params = {}
        for part in query.split('&'):
            if '=' in part:
                k, v = part.split('=', 1)
                params[k] = v
    else:
        component = address
        params = {}

    return component, params


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read code structure with optional coverage."""
    config = config or {}

    # Parse address
    source = config.get('source', '@code/functions')
    component, params = parse_address(source)

    # Merge config (takes precedence)
    params.update({k: v for k, v in config.items() if k != 'source'})

    # Resolve parameters
    root = params.get('root', '.')
    globs_str = params.get('globs', '**/*.py')
    globs = [g.strip() for g in globs_str.split(',')]

    lcov_path = params.get('lcov')
    min_cov = int(params.get('min', 0))
    max_cov = int(params.get('max', 100))
    type_filter = params.get('type')

    # Component-based type filter
    if component == 'classes':
        type_filter = 'class'
    elif component == 'methods':
        type_filter = 'method'
    elif component == 'files':
        # Just list files
        for f in sorted(find_files(root, globs)):
            yield {'file': f}
        return
    elif component == 'calls':
        # Extract call graph
        for file_path in sorted(find_files(root, globs)):
            for record in extract_calls_from_file(file_path):
                record['module'] = str(Path(record['file']).parent)
                yield record
        return

    elif component == 'dead':
        # Find dead code with false positive filtering
        # Collect all functions
        functions = []
        for file_path in sorted(find_files(root, globs)):
            for record in extract_from_file(file_path):
                record['module'] = str(Path(record['file']).parent)
                functions.append(record)

        # Collect all callees
        callees = set()
        for file_path in sorted(find_files(root, globs)):
            for call in extract_calls_from_file(file_path):
                callees.add(call['callee'])
                # Also add simple name for method calls (obj.method -> method)
                if '.' in call['callee']:
                    callees.add(call['callee'].split('.')[-1])

        # Filter for dead code
        for func in functions:
            func_name = func['function']
            simple_name = func_name.split('.')[-1] if '.' in func_name else func_name

            # Check if called
            is_called = func_name in callees or simple_name in callees

            if is_called:
                continue

            # Filter out false positives
            # 1. Skip AST visitor methods (visit_*)
            if simple_name.startswith('visit_'):
                continue

            # 2. Skip dunder methods (__str__, __init__, etc.)
            if simple_name.startswith('__') and simple_name.endswith('__'):
                continue

            # 3. Skip CLI entry points (simple lowercase functions are likely Click commands)
            # But keep internal functions (start with _)
            if func['type'] == 'function' and not simple_name.startswith('_'):
                # Check if it looks like a CLI command (no dots, all lowercase)
                if simple_name.islower() and '_' not in simple_name[1:]:
                    continue

            # 4. Skip classes (often instantiated dynamically)
            if func['type'] == 'class':
                continue

            # 5. Skip property-like methods (very short, no underscore prefix)
            if func['type'] == 'method':
                lines = func['end_line'] - func['start_line']
                if lines <= 2 and not simple_name.startswith('_'):
                    continue

            # Add reason for being flagged
            func['reason'] = 'never_called'
            if simple_name.startswith('_') and not simple_name.startswith('__'):
                func['reason'] = 'internal_never_called'

            yield func
        return

    # Load LCOV if specified
    lcov_data = None
    if lcov_path and Path(lcov_path).exists():
        lcov_data = parse_lcov(lcov_path)

    # Build caller count map for enrichment
    caller_counts: dict[str, int] = {}
    for file_path in sorted(find_files(root, globs)):
        for call in extract_calls_from_file(file_path):
            callee = call['callee']
            caller_counts[callee] = caller_counts.get(callee, 0) + 1
            # Also count simple name
            if '.' in callee:
                simple = callee.split('.')[-1]
                caller_counts[simple] = caller_counts.get(simple, 0) + 1

    # Extract and yield
    for file_path in sorted(find_files(root, globs)):
        for record in extract_from_file(file_path):
            # Type filter
            if type_filter and record['type'] != type_filter:
                continue

            # Add module (directory path)
            record['module'] = str(Path(record['file']).parent)

            # Add caller count
            func_name = record['function']
            simple_name = func_name.split('.')[-1] if '.' in func_name else func_name
            record['caller_count'] = max(
                caller_counts.get(func_name, 0),
                caller_counts.get(simple_name, 0)
            )

            # Enrich with coverage if available
            if lcov_data:
                record = enrich_with_coverage(record, lcov_data)

                # Coverage filter
                if 'coverage' in record:
                    if not (min_cov <= record['coverage'] <= max_cov):
                        continue

            yield record


def main():
    parser = argparse.ArgumentParser(description='Code structure plugin')
    parser.add_argument('--mode', choices=['read'], default='read')
    parser.add_argument('--source', help='Source address (@code/...)')
    parser.add_argument('--root', help='Source root directory')
    parser.add_argument('--globs', help='File patterns (comma-separated)')
    parser.add_argument('--lcov', help='LCOV file for coverage')
    parser.add_argument('--min', type=int, help='Min coverage %')
    parser.add_argument('--max', type=int, help='Max coverage %')
    parser.add_argument('--type', help='Filter: function, method, class')

    args = parser.parse_args()

    config = {'source': args.source or '@code/functions'}
    if args.root:
        config['root'] = args.root
    if args.globs:
        config['globs'] = args.globs
    if args.lcov:
        config['lcov'] = args.lcov
    if args.min is not None:
        config['min'] = args.min
    if args.max is not None:
        config['max'] = args.max
    if args.type:
        config['type'] = args.type

    try:
        for record in reads(config):
            print(json.dumps(record), flush=True)
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
