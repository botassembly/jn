#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "tree-sitter>=0.24",
#   "tree-sitter-python>=0.24",
#   "tree-sitter-javascript>=0.24",
#   "tree-sitter-go>=0.24",
#   "tree-sitter-rust>=0.24",
# ]
#
# [tool.jn]
# matches = []
# description = "Extract code structure (functions, methods, classes) using tree-sitter"
# ///
"""Tree-sitter code structure extraction plugin.

Extracts functions, methods, and classes from source files using tree-sitter.
Produces NDJSON output suitable for joining with coverage data.

Usage:
    jn cat file.py --plugin ts_
    jn cat "src/**/*.py" --plugin ts_

Output schema:
    {
        "file": "src/example.py",
        "function": "ClassName.method_name",
        "type": "method",
        "class": "ClassName",
        "start_line": 10,
        "end_line": 25
    }

Supported languages: Python, JavaScript, Go, Rust
"""

import json
import sys
from pathlib import Path
from typing import Iterator, Optional

# Language detection by extension
LANG_MAP = {
    '.py': 'python',
    '.pyw': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.mjs': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.go': 'go',
    '.rs': 'rust',
}


def get_parser(lang: str):
    """Get tree-sitter parser for language."""
    from tree_sitter import Language, Parser

    if lang == 'python':
        import tree_sitter_python as ts_lang
    elif lang in ('javascript', 'typescript'):
        import tree_sitter_javascript as ts_lang
    elif lang == 'go':
        import tree_sitter_go as ts_lang
    elif lang == 'rust':
        import tree_sitter_rust as ts_lang
    else:
        raise ValueError(f"Unsupported language: {lang}")

    language = Language(ts_lang.language())
    parser = Parser(language)
    return parser


def extract_python(node, code: bytes, file_path: str, class_name: Optional[str] = None):
    """Extract functions/methods from Python AST."""
    if node.type == 'class_definition':
        # Get class name
        for child in node.children:
            if child.type == 'identifier':
                cls_name = code[child.start_byte:child.end_byte].decode()
                break
        else:
            cls_name = '<unknown>'

        # Yield the class itself
        yield {
            'file': file_path,
            'function': cls_name,
            'type': 'class',
            'class': None,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
        }

        # Recurse into class body for methods
        for child in node.children:
            if child.type == 'block':
                yield from extract_python(child, code, file_path, cls_name)

    elif node.type == 'function_definition':
        # Get function name
        for child in node.children:
            if child.type == 'identifier':
                func_name = code[child.start_byte:child.end_byte].decode()
                break
        else:
            func_name = '<unknown>'

        # Build qualified name
        if class_name:
            qualified_name = f"{class_name}.{func_name}"
            func_type = 'method'
        else:
            qualified_name = func_name
            func_type = 'function'

        yield {
            'file': file_path,
            'function': qualified_name,
            'type': func_type,
            'class': class_name,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
        }

    else:
        # Recurse into children
        for child in node.children:
            yield from extract_python(child, code, file_path, class_name)


def extract_javascript(node, code: bytes, file_path: str, class_name: Optional[str] = None):
    """Extract functions/methods from JavaScript AST."""
    if node.type == 'class_declaration':
        # Get class name
        for child in node.children:
            if child.type == 'identifier':
                cls_name = code[child.start_byte:child.end_byte].decode()
                break
        else:
            cls_name = '<unknown>'

        yield {
            'file': file_path,
            'function': cls_name,
            'type': 'class',
            'class': None,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
        }

        # Recurse into class body
        for child in node.children:
            if child.type == 'class_body':
                yield from extract_javascript(child, code, file_path, cls_name)

    elif node.type == 'method_definition':
        # Get method name
        for child in node.children:
            if child.type == 'property_identifier':
                func_name = code[child.start_byte:child.end_byte].decode()
                break
        else:
            func_name = '<unknown>'

        qualified_name = f"{class_name}.{func_name}" if class_name else func_name

        yield {
            'file': file_path,
            'function': qualified_name,
            'type': 'method',
            'class': class_name,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
        }

    elif node.type == 'function_declaration':
        # Get function name
        for child in node.children:
            if child.type == 'identifier':
                func_name = code[child.start_byte:child.end_byte].decode()
                break
        else:
            func_name = '<unknown>'

        yield {
            'file': file_path,
            'function': func_name,
            'type': 'function',
            'class': None,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
        }

    elif node.type == 'arrow_function':
        # Check if assigned to variable
        parent = node.parent
        if parent and parent.type == 'variable_declarator':
            for child in parent.children:
                if child.type == 'identifier':
                    func_name = code[child.start_byte:child.end_byte].decode()
                    yield {
                        'file': file_path,
                        'function': func_name,
                        'type': 'arrow_function',
                        'class': None,
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1,
                    }
                    break
    else:
        for child in node.children:
            yield from extract_javascript(child, code, file_path, class_name)


def extract_go(node, code: bytes, file_path: str):
    """Extract functions/methods from Go AST."""
    if node.type == 'function_declaration':
        # Get function name
        for child in node.children:
            if child.type == 'identifier':
                func_name = code[child.start_byte:child.end_byte].decode()
                break
        else:
            func_name = '<unknown>'

        yield {
            'file': file_path,
            'function': func_name,
            'type': 'function',
            'class': None,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
        }

    elif node.type == 'method_declaration':
        func_name = None
        receiver_type = None

        for child in node.children:
            if child.type == 'field_identifier':
                func_name = code[child.start_byte:child.end_byte].decode()
            elif child.type == 'parameter_list' and receiver_type is None:
                # First parameter list is receiver
                for param_child in child.children:
                    if param_child.type == 'parameter_declaration':
                        for pc in param_child.children:
                            if pc.type == 'type_identifier':
                                receiver_type = code[pc.start_byte:pc.end_byte].decode()
                                break
                            elif pc.type == 'pointer_type':
                                # Extract type from pointer
                                for ppc in pc.children:
                                    if ppc.type == 'type_identifier':
                                        receiver_type = code[ppc.start_byte:ppc.end_byte].decode()
                                        break
                        break

        qualified_name = f"{receiver_type}.{func_name}" if receiver_type else func_name

        yield {
            'file': file_path,
            'function': qualified_name,
            'type': 'method',
            'class': receiver_type,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
        }

    else:
        for child in node.children:
            yield from extract_go(child, code, file_path)


def extract_rust(node, code: bytes, file_path: str, impl_type: Optional[str] = None):
    """Extract functions/methods from Rust AST."""
    if node.type == 'impl_item':
        # Get the type being implemented
        for child in node.children:
            if child.type == 'type_identifier':
                impl_name = code[child.start_byte:child.end_byte].decode()
                break
        else:
            impl_name = None

        # Recurse into impl body
        for child in node.children:
            if child.type == 'declaration_list':
                yield from extract_rust(child, code, file_path, impl_name)

    elif node.type == 'function_item':
        # Get function name
        for child in node.children:
            if child.type == 'identifier':
                func_name = code[child.start_byte:child.end_byte].decode()
                break
        else:
            func_name = '<unknown>'

        if impl_type:
            qualified_name = f"{impl_type}::{func_name}"
            func_type = 'method'
        else:
            qualified_name = func_name
            func_type = 'function'

        yield {
            'file': file_path,
            'function': qualified_name,
            'type': func_type,
            'class': impl_type,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
        }

    else:
        for child in node.children:
            yield from extract_rust(child, code, file_path, impl_type)


def extract_functions(tree, code: bytes, file_path: str, lang: str):
    """Extract functions from parsed tree."""
    if lang == 'python':
        yield from extract_python(tree.root_node, code, file_path)
    elif lang in ('javascript', 'typescript'):
        yield from extract_javascript(tree.root_node, code, file_path)
    elif lang == 'go':
        yield from extract_go(tree.root_node, code, file_path)
    elif lang == 'rust':
        yield from extract_rust(tree.root_node, code, file_path)
    else:
        raise ValueError(f"Unsupported language: {lang}")


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read source file and extract code structure.

    Config options:
        file: Path to source file (required)
        lang: Language override (optional, auto-detected from extension)
    """
    config = config or {}
    file_path = config.get('file') or config.get('source')

    if not file_path:
        raise ValueError("No file specified. Use: jn cat file.py --plugin ts_")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Detect language
    lang = config.get('lang')
    if not lang:
        ext = path.suffix.lower()
        lang = LANG_MAP.get(ext)
        if not lang:
            raise ValueError(f"Cannot detect language for extension: {ext}")

    # Parse file
    code = path.read_bytes()
    parser = get_parser(lang)
    tree = parser.parse(code)

    # Extract and yield functions
    yield from extract_functions(tree, code, file_path, lang)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Tree-sitter code structure extraction')
    parser.add_argument('--mode', choices=['read'], default='read', help='Plugin mode')
    parser.add_argument('--file', help='Source file to parse')
    parser.add_argument('--lang', help='Language override')

    args = parser.parse_args()

    if args.mode == 'read':
        config = {}
        if args.file:
            config['file'] = args.file
        if args.lang:
            config['lang'] = args.lang

        try:
            for record in reads(config):
                print(json.dumps(record))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
