#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "tree-sitter>=0.23.0",
#   "tree-sitter-python>=0.23.0",
#   "tree-sitter-javascript>=0.23.0",
#   "tree-sitter-typescript>=0.23.0",
#   "tree-sitter-rust>=0.23.0",
#   "tree-sitter-go>=0.23.0",
#   "tree-sitter-java>=0.23.0",
#   "tree-sitter-c>=0.23.0",
#   "tree-sitter-cpp>=0.23.0",
#   "tree-sitter-ruby>=0.23.0",
# ]
#
# [tool.jn]
# matches = [
#   ".*\\.py$",
#   ".*\\.js$",
#   ".*\\.jsx$",
#   ".*\\.ts$",
#   ".*\\.tsx$",
#   ".*\\.rs$",
#   ".*\\.go$",
#   ".*\\.java$",
#   ".*\\.c$",
#   ".*\\.h$",
#   ".*\\.cpp$",
#   ".*\\.hpp$",
#   ".*\\.cc$",
#   ".*\\.rb$"
# ]
# ///
"""Tree-sitter code analysis plugin.

A structural code engine for extracting, analyzing, and understanding code.
Treats source code as a queryable database.

Output modes:
- symbols (default): Extract function/class/method definitions
- calls: Extract function calls with caller context
- imports: Extract import/require statements
- skeleton: Code with bodies stripped (for LLM context compression)
- strings: Extract all string literals
- comments: Extract all comments

Examples:
    # Extract all symbols from a Python file
    jn cat app.py~treesitter

    # Extract function calls
    jn cat app.py~treesitter --output-mode=calls

    # Generate skeleton for LLM context
    jn cat app.py~treesitter --output-mode=skeleton

    # Extract imports
    jn cat app.py~treesitter --output-mode=imports

    # Specify language explicitly
    jn cat script~treesitter --lang=python
"""

import json
import sys
from pathlib import Path
from typing import Iterator, Optional

# Language loading is deferred to avoid import errors if grammars missing
_LANGUAGES = {}


def _get_language(lang: str):
    """Lazy-load tree-sitter language."""
    if lang in _LANGUAGES:
        return _LANGUAGES[lang]

    from tree_sitter import Language

    lang_modules = {
        'python': 'tree_sitter_python',
        'javascript': 'tree_sitter_javascript',
        'typescript': 'tree_sitter_typescript',
        'tsx': 'tree_sitter_typescript',
        'rust': 'tree_sitter_rust',
        'go': 'tree_sitter_go',
        'java': 'tree_sitter_java',
        'c': 'tree_sitter_c',
        'cpp': 'tree_sitter_cpp',
        'ruby': 'tree_sitter_ruby',
    }

    module_name = lang_modules.get(lang)
    if not module_name:
        raise ValueError(f"Unsupported language: {lang}")

    import importlib
    mod = importlib.import_module(module_name)

    # Handle typescript which has both typescript and tsx
    if lang == 'tsx':
        language = Language(mod.language_tsx())
    elif lang == 'typescript':
        language = Language(mod.language_typescript())
    else:
        language = Language(mod.language())

    _LANGUAGES[lang] = language
    return language


def _detect_language(filename: str) -> str:
    """Detect language from file extension."""
    ext_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'tsx',
        '.rs': 'rust',
        '.go': 'go',
        '.java': 'java',
        '.c': 'c',
        '.h': 'c',
        '.cpp': 'cpp',
        '.hpp': 'cpp',
        '.cc': 'cpp',
        '.rb': 'ruby',
    }

    suffix = Path(filename).suffix.lower()
    return ext_map.get(suffix, 'python')


def _get_node_text(node, source_bytes: bytes) -> str:
    """Extract text from a node."""
    return source_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _find_parent_function(node, source_bytes: bytes, lang: str) -> Optional[dict]:
    """Find the enclosing function for a node."""
    func_types = {
        'python': ['function_definition', 'lambda'],
        'javascript': ['function_declaration', 'function_expression', 'arrow_function', 'method_definition'],
        'typescript': ['function_declaration', 'function_expression', 'arrow_function', 'method_definition'],
        'tsx': ['function_declaration', 'function_expression', 'arrow_function', 'method_definition'],
        'rust': ['function_item', 'closure_expression'],
        'go': ['function_declaration', 'method_declaration', 'func_literal'],
        'java': ['method_declaration', 'constructor_declaration', 'lambda_expression'],
        'c': ['function_definition'],
        'cpp': ['function_definition', 'lambda_expression'],
        'ruby': ['method', 'singleton_method', 'lambda', 'block'],
    }

    types = func_types.get(lang, ['function_definition'])
    current = node.parent

    while current:
        if current.type in types:
            name = _extract_function_name(current, source_bytes, lang)
            return {
                'name': name,
                'type': current.type,
                'start_line': current.start_point[0] + 1,
                'end_line': current.end_point[0] + 1,
            }
        current = current.parent

    return None


def _extract_function_name(node, source_bytes: bytes, lang: str) -> str:
    """Extract function name from a function node."""
    # Try common name child patterns
    for child in node.children:
        if child.type in ['identifier', 'name', 'property_identifier']:
            return _get_node_text(child, source_bytes)

    # Language-specific patterns
    if lang == 'python':
        for child in node.children:
            if child.type == 'identifier':
                return _get_node_text(child, source_bytes)
    elif lang in ['javascript', 'typescript', 'tsx']:
        for child in node.children:
            if child.type in ['identifier', 'property_identifier']:
                return _get_node_text(child, source_bytes)
    elif lang == 'rust':
        for child in node.children:
            if child.type == 'identifier':
                return _get_node_text(child, source_bytes)
    elif lang == 'go':
        for child in node.children:
            if child.type == 'identifier':
                return _get_node_text(child, source_bytes)

    return '<anonymous>'


def _extract_class_name(node, source_bytes: bytes, lang: str) -> str:
    """Extract class name from a class node."""
    for child in node.children:
        if child.type in ['identifier', 'name', 'type_identifier']:
            return _get_node_text(child, source_bytes)
    return '<anonymous>'


def extract_symbols(tree, source_bytes: bytes, lang: str, filename: str) -> Iterator[dict]:
    """Extract function/class/method definitions."""

    # Node types for different symbol kinds by language
    func_types = {
        'python': ['function_definition'],
        'javascript': ['function_declaration', 'function_expression', 'arrow_function', 'method_definition'],
        'typescript': ['function_declaration', 'function_expression', 'arrow_function', 'method_definition'],
        'tsx': ['function_declaration', 'function_expression', 'arrow_function', 'method_definition'],
        'rust': ['function_item'],
        'go': ['function_declaration', 'method_declaration'],
        'java': ['method_declaration', 'constructor_declaration'],
        'c': ['function_definition'],
        'cpp': ['function_definition'],
        'ruby': ['method', 'singleton_method'],
    }

    class_types = {
        'python': ['class_definition'],
        'javascript': ['class_declaration', 'class'],
        'typescript': ['class_declaration', 'class', 'interface_declaration'],
        'tsx': ['class_declaration', 'class', 'interface_declaration'],
        'rust': ['struct_item', 'enum_item', 'impl_item', 'trait_item'],
        'go': ['type_declaration'],
        'java': ['class_declaration', 'interface_declaration', 'enum_declaration'],
        'c': ['struct_specifier', 'enum_specifier'],
        'cpp': ['class_specifier', 'struct_specifier'],
        'ruby': ['class', 'module'],
    }

    def walk(node, parent_class=None):
        node_type = node.type

        # Check for class definitions
        if node_type in class_types.get(lang, []):
            class_name = _extract_class_name(node, source_bytes, lang)
            yield {
                'file': filename,
                'filename': Path(filename).name,
                'type': 'class',
                'name': class_name,
                'node_type': node_type,
                'start_line': node.start_point[0] + 1,
                'end_line': node.end_point[0] + 1,
                'lines': node.end_point[0] - node.start_point[0] + 1,
                'parent_class': parent_class,
            }
            # Recurse with this as parent class
            for child in node.children:
                yield from walk(child, parent_class=class_name)
            return

        # Check for function definitions
        if node_type in func_types.get(lang, []):
            func_name = _extract_function_name(node, source_bytes, lang)

            # Determine if it's a method (inside a class)
            symbol_type = 'method' if parent_class else 'function'

            yield {
                'file': filename,
                'filename': Path(filename).name,
                'type': symbol_type,
                'name': func_name,
                'node_type': node_type,
                'start_line': node.start_point[0] + 1,
                'end_line': node.end_point[0] + 1,
                'lines': node.end_point[0] - node.start_point[0] + 1,
                'parent_class': parent_class,
            }

        # Recurse into children
        for child in node.children:
            yield from walk(child, parent_class)

    yield from walk(tree.root_node)


def extract_calls(tree, source_bytes: bytes, lang: str, filename: str) -> Iterator[dict]:
    """Extract function calls with caller context."""

    call_types = {
        'python': ['call'],
        'javascript': ['call_expression', 'new_expression'],
        'typescript': ['call_expression', 'new_expression'],
        'tsx': ['call_expression', 'new_expression'],
        'rust': ['call_expression', 'macro_invocation'],
        'go': ['call_expression'],
        'java': ['method_invocation', 'object_creation_expression'],
        'c': ['call_expression'],
        'cpp': ['call_expression'],
        'ruby': ['call', 'method_call'],
    }

    def extract_callee(node, lang: str) -> str:
        """Extract the callee name from a call expression."""
        # Find the function/identifier being called
        for child in node.children:
            if child.type in ['identifier', 'name']:
                return _get_node_text(child, source_bytes)
            elif child.type in ['attribute', 'member_expression', 'field_expression']:
                # For method calls like obj.method()
                return _get_node_text(child, source_bytes)
            elif child.type in ['function', 'primary_expression']:
                # Recurse to find actual identifier
                return extract_callee(child, lang)

        # Fallback: get first meaningful child
        if node.children:
            first = node.children[0]
            if first.type not in ['(', ')', ',', 'arguments', 'argument_list']:
                return _get_node_text(first, source_bytes)

        return '<unknown>'

    def walk(node):
        if node.type in call_types.get(lang, []):
            callee = extract_callee(node, lang)
            caller = _find_parent_function(node, source_bytes, lang)

            yield {
                'file': filename,
                'filename': Path(filename).name,
                'type': 'call',
                'callee': callee,
                'caller': caller['name'] if caller else '<module>',
                'caller_type': caller['type'] if caller else 'module',
                'line': node.start_point[0] + 1,
                'column': node.start_point[1] + 1,
            }

        for child in node.children:
            yield from walk(child)

    yield from walk(tree.root_node)


def extract_imports(tree, source_bytes: bytes, lang: str, filename: str) -> Iterator[dict]:
    """Extract import statements."""

    import_types = {
        'python': ['import_statement', 'import_from_statement'],
        'javascript': ['import_statement', 'import'],
        'typescript': ['import_statement', 'import'],
        'tsx': ['import_statement', 'import'],
        'rust': ['use_declaration'],
        'go': ['import_declaration', 'import_spec'],
        'java': ['import_declaration'],
        'c': ['preproc_include'],
        'cpp': ['preproc_include'],
        'ruby': ['require', 'require_relative'],
    }

    def walk(node):
        if node.type in import_types.get(lang, []):
            import_text = _get_node_text(node, source_bytes)

            # Try to extract the module/package name
            module = import_text.strip()

            yield {
                'file': filename,
                'filename': Path(filename).name,
                'type': 'import',
                'raw': module,
                'line': node.start_point[0] + 1,
            }

        for child in node.children:
            yield from walk(child)

    yield from walk(tree.root_node)


def extract_skeleton(tree, source_bytes: bytes, lang: str, filename: str) -> Iterator[dict]:
    """Generate skeleton code with bodies stripped.

    Perfect for LLM context compression - shows structure without implementation.
    """
    lines = source_bytes.decode('utf-8', errors='replace').split('\n')

    # Find all function/method bodies to strip
    body_types = {
        'python': 'block',
        'javascript': 'statement_block',
        'typescript': 'statement_block',
        'tsx': 'statement_block',
        'rust': 'block',
        'go': 'block',
        'java': 'block',
        'c': 'compound_statement',
        'cpp': 'compound_statement',
        'ruby': 'body_statement',
    }

    func_types = {
        'python': ['function_definition'],
        'javascript': ['function_declaration', 'function_expression', 'arrow_function', 'method_definition'],
        'typescript': ['function_declaration', 'function_expression', 'arrow_function', 'method_definition'],
        'tsx': ['function_declaration', 'function_expression', 'arrow_function', 'method_definition'],
        'rust': ['function_item'],
        'go': ['function_declaration', 'method_declaration'],
        'java': ['method_declaration', 'constructor_declaration'],
        'c': ['function_definition'],
        'cpp': ['function_definition'],
        'ruby': ['method', 'singleton_method'],
    }

    # Collect ranges to replace with "..."
    body_ranges = []

    def find_bodies(node):
        if node.type in func_types.get(lang, []):
            # Find the body child
            body_type = body_types.get(lang, 'block')
            for child in node.children:
                if child.type == body_type:
                    body_ranges.append((child.start_byte, child.end_byte, child.start_point[0]))
                    break

        for child in node.children:
            find_bodies(child)

    find_bodies(tree.root_node)

    # Sort ranges by start position (reverse for replacement)
    body_ranges.sort(key=lambda x: x[0], reverse=True)

    # Build skeleton by replacing bodies
    result = source_bytes.decode('utf-8', errors='replace')
    for start, end, line_num in body_ranges:
        # Get indentation of the body
        line_start = result.rfind('\n', 0, start) + 1
        indent = ''
        for ch in result[line_start:start]:
            if ch in ' \t':
                indent += ch
            else:
                break

        # Replace body with ellipsis, keeping language-appropriate syntax
        if lang == 'python':
            replacement = '...'
        else:
            replacement = '{ ... }'

        result = result[:start] + replacement + result[end:]

    yield {
        'file': filename,
        'filename': Path(filename).name,
        'type': 'skeleton',
        'content': result,
        'original_lines': len(lines),
        'functions_stripped': len(body_ranges),
    }


def extract_strings(tree, source_bytes: bytes, lang: str, filename: str) -> Iterator[dict]:
    """Extract all string literals."""

    string_types = {
        'python': ['string', 'string_literal'],
        'javascript': ['string', 'template_string'],
        'typescript': ['string', 'template_string'],
        'tsx': ['string', 'template_string'],
        'rust': ['string_literal', 'raw_string_literal'],
        'go': ['interpreted_string_literal', 'raw_string_literal'],
        'java': ['string_literal'],
        'c': ['string_literal'],
        'cpp': ['string_literal', 'raw_string_literal'],
        'ruby': ['string', 'string_literal'],
    }

    def walk(node):
        if node.type in string_types.get(lang, []):
            text = _get_node_text(node, source_bytes)
            caller = _find_parent_function(node, source_bytes, lang)

            yield {
                'file': filename,
                'filename': Path(filename).name,
                'type': 'string',
                'value': text,
                'line': node.start_point[0] + 1,
                'column': node.start_point[1] + 1,
                'function': caller['name'] if caller else '<module>',
            }

        for child in node.children:
            yield from walk(child)

    yield from walk(tree.root_node)


def extract_comments(tree, source_bytes: bytes, lang: str, filename: str) -> Iterator[dict]:
    """Extract all comments."""

    comment_types = ['comment', 'line_comment', 'block_comment', 'documentation_comment']

    def walk(node):
        if node.type in comment_types:
            text = _get_node_text(node, source_bytes)

            yield {
                'file': filename,
                'filename': Path(filename).name,
                'type': 'comment',
                'value': text.strip(),
                'line': node.start_point[0] + 1,
            }

        for child in node.children:
            yield from walk(child)

    yield from walk(tree.root_node)


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Parse source code and extract structural information.

    Config:
        mode: Output mode - 'symbols' (default), 'calls', 'imports', 'skeleton', 'strings', 'comments'
        lang: Language override (default: auto-detect from filename)
        filename: Source filename for language detection and output
    """
    from tree_sitter import Parser

    config = config or {}
    mode = config.get('mode', 'symbols')
    lang = config.get('lang')
    filename = config.get('filename', 'input.py')

    # Auto-detect language if not specified
    if not lang:
        lang = _detect_language(filename)

    # Read source code
    source = sys.stdin.read()
    source_bytes = source.encode('utf-8')

    # Parse with tree-sitter
    language = _get_language(lang)
    parser = Parser(language)
    tree = parser.parse(source_bytes)

    # Extract based on mode
    extractors = {
        'symbols': extract_symbols,
        'calls': extract_calls,
        'imports': extract_imports,
        'skeleton': extract_skeleton,
        'strings': extract_strings,
        'comments': extract_comments,
    }

    extractor = extractors.get(mode, extract_symbols)
    yield from extractor(tree, source_bytes, lang, filename)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Tree-sitter code analysis plugin')
    parser.add_argument('--mode', choices=['read', 'write'],
                       default='read', help='Plugin mode (only read supported)')
    parser.add_argument('--output-mode',
                       choices=['symbols', 'calls', 'imports', 'skeleton', 'strings', 'comments'],
                       default='symbols', help='What to extract')
    parser.add_argument('--lang',
                       choices=['python', 'javascript', 'typescript', 'tsx', 'rust', 'go', 'java', 'c', 'cpp', 'ruby'],
                       help='Language (default: auto-detect)')
    parser.add_argument('--filename', default='input.py',
                       help='Filename for language detection')

    args = parser.parse_args()

    if args.mode == 'write':
        print("ERROR: Tree-sitter write mode not implemented", file=sys.stderr)
        print("This is an analysis plugin - source code mutation coming soon!", file=sys.stderr)
        sys.exit(1)

    config = {
        'mode': args.output_mode,
        'lang': args.lang,
        'filename': args.filename,
    }

    for record in reads(config):
        print(json.dumps(record))
