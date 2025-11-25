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
                'name': class_name,       # Keep 'name' for classes
                'class': class_name,      # Also add 'class' for consistency
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
                'function': func_name,    # Use 'function' to match LCOV output
                'name': func_name,        # Keep 'name' for backward compat
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


def extract_decorators(tree, source_bytes: bytes, lang: str, filename: str) -> Iterator[dict]:
    """Extract decorators/attributes from functions and classes.

    Useful for finding API routes, test functions, cached methods, etc.
    """
    # Decorator node types by language
    decorator_types = {
        'python': ['decorator'],
        'javascript': ['decorator'],
        'typescript': ['decorator'],
        'tsx': ['decorator'],
        'java': ['annotation', 'marker_annotation'],
        'rust': ['attribute_item'],
    }

    func_types = {
        'python': ['function_definition'],
        'javascript': ['function_declaration', 'method_definition'],
        'typescript': ['function_declaration', 'method_definition'],
        'tsx': ['function_declaration', 'method_definition'],
        'java': ['method_declaration'],
        'rust': ['function_item'],
    }

    class_types = {
        'python': ['class_definition'],
        'javascript': ['class_declaration'],
        'typescript': ['class_declaration'],
        'tsx': ['class_declaration'],
        'java': ['class_declaration'],
        'rust': ['struct_item', 'impl_item'],
    }

    def extract_decorator_info(dec_node) -> dict:
        """Extract decorator name and arguments."""
        dec_text = _get_node_text(dec_node, source_bytes)

        # Parse decorator: @name or @name(...) or @module.name(...)
        name = dec_text
        args = []

        # For Python: decorator contains the @ and the expression
        if lang == 'python':
            # Find the actual decorator expression (skip @)
            for child in dec_node.children:
                if child.type == 'identifier':
                    name = _get_node_text(child, source_bytes)
                elif child.type == 'call':
                    # It's @decorator(args)
                    for call_child in child.children:
                        if call_child.type in ['identifier', 'attribute']:
                            name = _get_node_text(call_child, source_bytes)
                        elif call_child.type == 'argument_list':
                            args_text = _get_node_text(call_child, source_bytes)
                            args = [args_text]  # Keep as raw for now
                elif child.type == 'attribute':
                    name = _get_node_text(child, source_bytes)

        return {'decorator': name, 'args': args, 'raw': dec_text.strip()}

    def find_decorated(node, collected_decorators=None):
        """Find decorated functions/classes."""
        if collected_decorators is None:
            collected_decorators = []

        # Collect decorators
        if node.type in decorator_types.get(lang, []):
            collected_decorators.append(extract_decorator_info(node))

        # Check for decorated definition (Python uses decorated_definition wrapper)
        if node.type == 'decorated_definition':
            # Collect all decorators, then find the function/class
            decorators = []
            target = None
            for child in node.children:
                if child.type in decorator_types.get(lang, []):
                    decorators.append(extract_decorator_info(child))
                elif child.type in func_types.get(lang, []) + class_types.get(lang, []):
                    target = child

            if target and decorators:
                target_name = _extract_function_name(target, source_bytes, lang) if target.type in func_types.get(lang, []) else _extract_class_name(target, source_bytes, lang)
                target_type = 'function' if target.type in func_types.get(lang, []) else 'class'

                for dec in decorators:
                    yield {
                        'file': filename,
                        'filename': Path(filename).name,
                        'type': 'decorator',
                        'decorator': dec['decorator'],
                        'args': dec['args'],
                        'raw': dec['raw'],
                        'target': target_name,
                        'target_type': target_type,
                        'line': node.start_point[0] + 1,
                    }

        # If we hit a function/class directly with collected decorators
        elif node.type in func_types.get(lang, []) and collected_decorators:
            func_name = _extract_function_name(node, source_bytes, lang)
            for dec in collected_decorators:
                yield {
                    'file': filename,
                    'filename': Path(filename).name,
                    'type': 'decorator',
                    'decorator': dec['decorator'],
                    'args': dec['args'],
                    'raw': dec['raw'],
                    'target': func_name,
                    'target_type': 'function',
                    'line': node.start_point[0] + 1,
                }
            collected_decorators.clear()

        # Recurse
        for child in node.children:
            yield from find_decorated(child, collected_decorators if node.type not in ['decorated_definition'] else None)

    yield from find_decorated(tree.root_node)


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Parse source code and extract structural information.

    Config:
        mode: Output mode - 'symbols' (default), 'calls', 'imports', 'skeleton', 'strings', 'comments', 'decorators'
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
        'decorators': extract_decorators,
    }

    extractor = extractors.get(mode, extract_symbols)
    yield from extractor(tree, source_bytes, lang, filename)


def _find_target_node(tree, source_bytes: bytes, target: str, lang: str):
    """Find a node by target specification.

    Target formats:
        function:name       - Find function by name
        method:class.name   - Find method by class and name
        class:name          - Find class by name

    Returns tuple of (node, node_type) or (None, None) if not found.
    """
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

    # Parse target specification
    if ':' not in target:
        raise ValueError(f"Invalid target format: {target}. Expected 'function:name', 'method:class.name', or 'class:name'")

    target_type, target_name = target.split(':', 1)

    # For method targets, parse class.method
    target_class = None
    if target_type == 'method' and '.' in target_name:
        target_class, target_name = target_name.rsplit('.', 1)

    def search(node, current_class=None):
        """Recursively search for target node."""
        node_type = node.type

        # Check for class definitions
        if node_type in class_types.get(lang, []):
            class_name = _extract_class_name(node, source_bytes, lang)

            if target_type == 'class' and class_name == target_name:
                return node, 'class'

            # Recurse into class with class context
            for child in node.children:
                result = search(child, current_class=class_name)
                if result[0]:
                    return result
            return None, None

        # Check for function definitions
        if node_type in func_types.get(lang, []):
            func_name = _extract_function_name(node, source_bytes, lang)

            if target_type == 'function' and func_name == target_name and current_class is None:
                return node, 'function'

            if target_type == 'method' and func_name == target_name:
                if target_class is None or current_class == target_class:
                    return node, 'method'

        # Recurse into children
        for child in node.children:
            result = search(child, current_class)
            if result[0]:
                return result

        return None, None

    return search(tree.root_node)


def _get_body_node(node, lang: str):
    """Get the body node of a function/method."""
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

    body_type = body_types.get(lang, 'block')
    for child in node.children:
        if child.type == body_type:
            return child
    return None


def _detect_indent(source: str, position: int) -> tuple[str, int]:
    """Detect indentation at a position in the source.

    Returns (indent_char, indent_width) where indent_char is ' ' or '\t'.
    """
    # Find the start of the line containing position
    line_start = source.rfind('\n', 0, position) + 1

    # Count leading whitespace
    indent = ''
    for ch in source[line_start:position]:
        if ch in ' \t':
            indent += ch
        else:
            break

    # Detect indent style
    if '\t' in indent:
        return '\t', indent.count('\t')
    else:
        # Assume 4-space indent if we can't detect
        width = len(indent)
        return ' ', width


def _reindent(code: str, target_indent: str) -> str:
    """Re-indent code to match target indentation.

    Assumes the first line of code has no indentation.
    """
    lines = code.split('\n')
    if not lines:
        return code

    # Detect the base indent of the input code
    base_indent = ''
    for line in lines:
        if line.strip():
            for ch in line:
                if ch in ' \t':
                    base_indent += ch
                else:
                    break
            break

    # Re-indent each line
    result = []
    for line in lines:
        if not line.strip():
            result.append('')
        elif line.startswith(base_indent):
            result.append(target_indent + line[len(base_indent):])
        else:
            result.append(target_indent + line.lstrip())

    return '\n'.join(result)


def writes(config: Optional[dict] = None) -> None:
    """Perform surgical code modifications.

    Reads JSON edit specifications from stdin, applies them, outputs result.

    Config:
        file: Path to source file (required)
        lang: Language override (default: auto-detect)

    Input JSON format (one per line):
        {
            "target": "function:name" | "method:class.name" | "class:name",
            "replace": "body" | "full",
            "code": "new code here",
            "dry_run": true/false (default: true)
        }

    Output JSON:
        {
            "success": true/false,
            "target": "...",
            "modified": "full modified source" (if dry_run),
            "error": "error message" (if failed)
        }
    """
    from tree_sitter import Parser

    config = config or {}
    file_path = config.get('file')
    lang = config.get('lang')

    if not file_path:
        yield {
            'success': False,
            'error': 'No file specified. Use --file option.'
        }
        return

    # Read source file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except FileNotFoundError:
        yield {
            'success': False,
            'error': f'File not found: {file_path}'
        }
        return

    source_bytes = source.encode('utf-8')

    # Auto-detect language
    if not lang:
        lang = _detect_language(file_path)

    # Parse with tree-sitter
    language = _get_language(lang)
    parser = Parser(language)
    tree = parser.parse(source_bytes)

    # Process each edit from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            edit = json.loads(line)
        except json.JSONDecodeError as e:
            yield {
                'success': False,
                'error': f'Invalid JSON: {e}'
            }
            continue

        target = edit.get('target')
        replace_mode = edit.get('replace', 'body')
        new_code = edit.get('code', '')
        dry_run = edit.get('dry_run', True)

        if not target:
            yield {
                'success': False,
                'error': 'No target specified'
            }
            continue

        # Find target node
        try:
            node, node_type = _find_target_node(tree, source_bytes, target, lang)
        except ValueError as e:
            yield {
                'success': False,
                'target': target,
                'error': str(e)
            }
            continue

        if not node:
            yield {
                'success': False,
                'target': target,
                'error': f'Target not found: {target}'
            }
            continue

        # Determine what to replace
        if replace_mode == 'body':
            if node_type == 'class':
                yield {
                    'success': False,
                    'target': target,
                    'error': 'Cannot replace body of class (use replace=full)'
                }
                continue

            body_node = _get_body_node(node, lang)
            if not body_node:
                yield {
                    'success': False,
                    'target': target,
                    'error': f'Could not find body in {target}'
                }
                continue

            replace_start = body_node.start_byte
            replace_end = body_node.end_byte

            # The body node doesn't include leading whitespace.
            # Find the newline before the body to get the actual indentation.
            newline_pos = source.rfind('\n', 0, replace_start)
            if newline_pos >= 0:
                # Everything between newline+1 and body start is the indent
                target_indent = source[newline_pos + 1:replace_start]
                # Start replacing from after the newline (include the indent in replacement)
                actual_replace_start = newline_pos + 1
            else:
                # No newline found, body is at start of file
                target_indent = ''
                actual_replace_start = replace_start

            reindented_code = _reindent(new_code.strip(), target_indent)

            # Build the new source (replace from after the newline to include indent)
            modified = source[:actual_replace_start] + reindented_code + source[replace_end:]

        elif replace_mode == 'full':
            replace_start = node.start_byte
            replace_end = node.end_byte

            # For full replacement, preserve the indentation of the original
            indent_char, indent_width = _detect_indent(source, replace_start)
            target_indent = indent_char * indent_width

            reindented_code = _reindent(new_code.strip(), target_indent)
            modified = source[:replace_start] + reindented_code + source[replace_end:]

        else:
            yield {
                'success': False,
                'target': target,
                'error': f'Invalid replace mode: {replace_mode}. Use "body" or "full".'
            }
            continue

        # Validate the modified code parses correctly
        modified_bytes = modified.encode('utf-8')
        modified_tree = parser.parse(modified_bytes)

        # Check for parse errors (ERROR nodes)
        def has_errors(node):
            if node.type == 'ERROR':
                return True
            for child in node.children:
                if has_errors(child):
                    return True
            return False

        if has_errors(modified_tree.root_node):
            yield {
                'success': False,
                'target': target,
                'error': 'Modified code has syntax errors',
                'modified': modified if dry_run else None
            }
            continue

        # Output result
        if dry_run:
            yield {
                'success': True,
                'target': target,
                'replace': replace_mode,
                'modified': modified
            }
        else:
            # Write to file
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified)
                yield {
                    'success': True,
                    'target': target,
                    'replace': replace_mode,
                    'file': file_path
                }
                # Re-parse for subsequent edits
                source = modified
                source_bytes = modified_bytes
                tree = modified_tree
            except IOError as e:
                yield {
                    'success': False,
                    'target': target,
                    'error': f'Failed to write file: {e}'
                }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Tree-sitter code analysis plugin')
    parser.add_argument('--mode', choices=['read', 'write'],
                       default='read', help='Plugin mode')
    parser.add_argument('--output-mode',
                       choices=['symbols', 'calls', 'imports', 'skeleton', 'strings', 'comments', 'decorators'],
                       default='symbols', help='What to extract (read mode)')
    parser.add_argument('--lang',
                       choices=['python', 'javascript', 'typescript', 'tsx', 'rust', 'go', 'java', 'c', 'cpp', 'ruby'],
                       help='Language (default: auto-detect)')
    parser.add_argument('--filename', default='input.py',
                       help='Filename for language detection (read mode)')
    parser.add_argument('--file',
                       help='Source file to modify (write mode)')

    args = parser.parse_args()

    if args.mode == 'write':
        config = {
            'file': args.file,
            'lang': args.lang,
        }
        for record in writes(config):
            print(json.dumps(record))
    else:
        config = {
            'mode': args.output_mode,
            'lang': args.lang,
            'filename': args.filename,
        }
        for record in reads(config):
            print(json.dumps(record))
