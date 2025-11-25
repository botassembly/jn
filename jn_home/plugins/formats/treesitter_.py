#!/usr/bin/env -S uv run --script
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

            # Create qualified name (Class.method or just function) for LCOV join
            qualified_name = f"{parent_class}.{func_name}" if parent_class else func_name

            yield {
                'file': filename,
                'filename': Path(filename).name,
                'type': symbol_type,
                'function': qualified_name,  # Qualified name for LCOV join (Class.method)
                'name': func_name,           # Keep 'name' for backward compat
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
        lines:start-end     - Find node spanning line range
        decorator:name      - Find decorated function by decorator name
        function:*pattern*  - Wildcard pattern matching (fnmatch)
        method:Class.*      - All methods in a class

    Returns tuple of (node, node_type) or (None, None) if not found.
    """
    import fnmatch

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

    decorator_types = {
        'python': ['decorator'],
        'javascript': ['decorator'],
        'typescript': ['decorator'],
        'tsx': ['decorator'],
        'java': ['annotation', 'marker_annotation'],
    }

    # Parse target specification
    if ':' not in target:
        raise ValueError(f"Invalid target format: {target}. Expected 'function:name', 'method:class.name', 'class:name', 'lines:start-end', or 'decorator:name'")

    target_type, target_name = target.split(':', 1)

    # Handle line range targeting: lines:10-20
    if target_type == 'lines':
        if '-' not in target_name:
            raise ValueError(f"Invalid line range: {target_name}. Expected 'lines:start-end'")
        try:
            start_line, end_line = map(int, target_name.split('-'))
        except ValueError:
            raise ValueError(f"Invalid line numbers in: {target_name}")

        def find_spanning_node(node):
            """Find the smallest node that spans the given line range."""
            node_start = node.start_point[0] + 1  # 1-indexed
            node_end = node.end_point[0] + 1

            # Check if this node spans our target range
            if node_start <= start_line and node_end >= end_line:
                # Check if any child is a better (smaller) match
                for child in node.children:
                    result = find_spanning_node(child)
                    if result[0]:  # Check if node was found (not None)
                        return result
                # This node is the smallest spanning node
                # Only return if it's a meaningful node (function, class, etc.)
                if node.type in func_types.get(lang, []):
                    return node, 'function'
                if node.type in class_types.get(lang, []):
                    return node, 'class'
            return None, None

        return find_spanning_node(tree.root_node)

    # Handle decorator targeting: decorator:route
    if target_type == 'decorator':
        def find_decorated(node, pending_decorators=None):
            """Find function decorated with specified decorator."""
            if pending_decorators is None:
                pending_decorators = []

            # Collect decorators
            if node.type in decorator_types.get(lang, []):
                dec_text = _get_node_text(node, source_bytes)
                pending_decorators.append(dec_text)

            # Check if this is a decorated function
            if node.type in func_types.get(lang, []):
                for dec in pending_decorators:
                    # Match decorator name (handle @name, @name(...), @module.name)
                    if target_name in dec or fnmatch.fnmatch(dec, f'*{target_name}*'):
                        return node, 'function'
                pending_decorators.clear()

            # For decorated_definition in Python, pass decorators to children
            if node.type == 'decorated_definition':
                for child in node.children:
                    result = find_decorated(child, pending_decorators)
                    if result[0]:
                        return result
                return None, None

            # Recurse into children
            for child in node.children:
                result = find_decorated(child, [] if node.type not in ['decorated_definition'] else pending_decorators)
                if result[0]:
                    return result

            return None, None

        return find_decorated(tree.root_node)

    # Check for wildcard pattern
    has_wildcard = '*' in target_name or '?' in target_name

    # For method targets, parse class.method
    target_class = None
    if target_type == 'method' and '.' in target_name:
        target_class, target_name = target_name.rsplit('.', 1)

    def matches_name(actual_name, pattern):
        """Check if actual_name matches pattern (supports wildcards)."""
        if has_wildcard:
            return fnmatch.fnmatch(actual_name, pattern)
        return actual_name == pattern

    def matches_class(actual_class, pattern):
        """Check if class matches (supports wildcards)."""
        if pattern is None:
            return True
        if '*' in pattern or '?' in pattern:
            return fnmatch.fnmatch(actual_class or '', pattern)
        return actual_class == pattern

    def search(node, current_class=None):
        """Recursively search for target node."""
        node_type = node.type

        # Check for class definitions
        if node_type in class_types.get(lang, []):
            class_name = _extract_class_name(node, source_bytes, lang)

            if target_type == 'class' and matches_name(class_name, target_name):
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

            if target_type == 'function' and matches_name(func_name, target_name) and current_class is None:
                return node, 'function'

            if target_type == 'method' and matches_name(func_name, target_name):
                if matches_class(current_class, target_class):
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


def _compute_edit_range(node, source: str, lang: str, replace_mode: str) -> tuple:
    """Compute the byte range and target indent for an edit.

    Returns (start_byte, end_byte, target_indent) or raises ValueError.
    """
    if replace_mode == 'body':
        body_node = _get_body_node(node, lang)
        if not body_node:
            raise ValueError(f'Could not find body node')

        replace_start = body_node.start_byte
        replace_end = body_node.end_byte

        # The body node doesn't include leading whitespace.
        # Find the newline before the body to get the actual indentation.
        newline_pos = source.rfind('\n', 0, replace_start)
        if newline_pos >= 0:
            target_indent = source[newline_pos + 1:replace_start]
            actual_start = newline_pos + 1
        else:
            target_indent = ''
            actual_start = replace_start

        return actual_start, replace_end, target_indent

    elif replace_mode == 'full':
        replace_start = node.start_byte
        replace_end = node.end_byte

        # For full replacement, preserve the indentation of the original
        indent_char, indent_width = _detect_indent(source, replace_start)
        target_indent = indent_char * indent_width

        return replace_start, replace_end, target_indent

    else:
        raise ValueError(f'Invalid replace mode: {replace_mode}')


def _check_git_status(file_path: str) -> Optional[str]:
    """Check if file has uncommitted changes in git.

    Returns error message if file is dirty, None if clean or not in git.
    """
    import subprocess
    from pathlib import Path

    file_abs = Path(file_path).resolve()

    # Check if file is in a git repo
    try:
        result = subprocess.run(  # jn:ignore[subprocess_capture_output]: git status check, not streaming
            ['git', 'rev-parse', '--git-dir'],
            cwd=file_abs.parent,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return None  # Not in a git repo, allow modification
    except FileNotFoundError:
        return None  # git not installed

    # Check if file has uncommitted changes
    result = subprocess.run(  # jn:ignore[subprocess_capture_output]: git status check, not streaming
        ['git', 'status', '--porcelain', str(file_abs)],
        cwd=file_abs.parent,
        capture_output=True,
        text=True
    )

    if result.stdout.strip():
        return f'File has uncommitted changes. Commit or stash changes first, or use --no-git-safe to bypass.'

    return None


def _create_backup(file_path: str) -> Optional[str]:
    """Create a backup of the file before modification.

    Returns the backup path on success, or None if backup failed.
    """
    from pathlib import Path
    import shutil
    from datetime import datetime

    file_path = Path(file_path)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = file_path.with_suffix(f'.{timestamp}.bak')

    try:
        shutil.copy2(file_path, backup_path)
        return str(backup_path)
    except (IOError, OSError):
        return None


def writes(config: Optional[dict] = None) -> None:
    """Perform surgical code modifications.

    Reads JSON edit specifications from stdin, applies them, outputs result.

    Config:
        file: Path to source file (required)
        lang: Language override (default: auto-detect)
        write: If True, actually write to file (default: dry run only)
        backup: If True, create backup before writing (default: True when write=True)
        git_safe: If True, refuse to modify files with uncommitted changes (default: True)

    Input JSON formats:

    Single replacement (one per line):
        {
            "target": "function:name" | "method:class.name" | "class:name",
            "replace": "body" | "full",
            "code": "new code here",
            "dry_run": true/false (default: true, overridden by --write flag)
        }

    Insert operation:
        {
            "operation": "insert",
            "after": "function:name",  (or "before": "function:name")
            "code": "def new_func(): pass",
            "dry_run": true/false
        }

    Delete operation:
        {
            "operation": "delete",
            "target": "function:name",
            "dry_run": true/false
        }

    Multi-edit (batch mode):
        {
            "edits": [
                {"target": "function:foo", "replace": "body", "code": "..."},
                {"operation": "delete", "target": "function:bar"},
                {"operation": "insert", "after": "function:foo", "code": "..."}
            ],
            "dry_run": true/false (default: true)
        }

    Output JSON:
        {
            "success": true/false,
            "target": "..." or "batch",
            "operation": "replace" | "insert" | "delete",
            "edits_applied": N (for batch),
            "modified": "full modified source" (if dry_run),
            "backup": "path/to/backup.py" (if backup created),
            "file": "path/to/file.py" (if written),
            "error": "error message" (if failed)
        }
    """
    from tree_sitter import Parser

    config = config or {}
    file_path = config.get('file')
    lang = config.get('lang')
    force_write = config.get('write', False)  # CLI --write flag overrides dry_run
    create_backup = config.get('backup', True)  # Default: create backups
    git_safe = config.get('git_safe', True)  # Default: check git status

    if not file_path:
        yield {
            'success': False,
            'error': 'No file specified. Use --file option.'
        }
        return

    # Check git status if git_safe is enabled and we're doing actual writes
    if force_write and git_safe:
        git_error = _check_git_status(file_path)
        if git_error:
            yield {
                'success': False,
                'error': git_error
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

    # Track if we've created a backup (only do once per session)
    backup_created = None

    # Parse with tree-sitter
    language = _get_language(lang)
    parser = Parser(language)
    tree = parser.parse(source_bytes)

    # Helper to process a single edit and compute its replacement info
    def process_single_edit(edit_spec, current_source, current_tree, current_bytes):
        """Process a single edit specification.

        Returns dict with 'start', 'end', 'replacement', 'target', 'operation' on success,
        or dict with 'error', 'target' on failure.

        Supports operations: replace (default), insert, delete
        """
        operation = edit_spec.get('operation', 'replace')
        new_code = edit_spec.get('code', '')

        # Handle DELETE operation
        if operation == 'delete':
            target = edit_spec.get('target')
            if not target:
                return {'error': 'No target specified for delete', 'target': None}

            try:
                node, node_type = _find_target_node(current_tree, current_bytes, target, lang)
            except ValueError as e:
                return {'error': str(e), 'target': target}

            if not node:
                return {'error': f'Target not found: {target}', 'target': target}

            # Delete the entire node, including any preceding newlines/whitespace
            start = node.start_byte
            end = node.end_byte

            # Try to include the newline after the node for cleaner deletion
            if end < len(current_source) and current_source[end] == '\n':
                end += 1

            return {
                'start': start,
                'end': end,
                'replacement': '',  # Empty replacement = deletion
                'target': target,
                'operation': 'delete'
            }

        # Handle INSERT operation
        if operation == 'insert':
            after_target = edit_spec.get('after')
            before_target = edit_spec.get('before')

            if not after_target and not before_target:
                return {'error': 'Insert requires "after" or "before" target', 'target': None}

            if after_target and before_target:
                return {'error': 'Specify either "after" or "before", not both', 'target': None}

            target = after_target or before_target
            is_after = after_target is not None

            try:
                node, node_type = _find_target_node(current_tree, current_bytes, target, lang)
            except ValueError as e:
                return {'error': str(e), 'target': target}

            if not node:
                return {'error': f'Target not found: {target}', 'target': target}

            # Determine insertion point and indentation
            if is_after:
                # Insert after the target node
                insert_pos = node.end_byte
                # Find the indentation of the target node
                indent_char, indent_width = _detect_indent(current_source, node.start_byte)
                target_indent = indent_char * indent_width
                # Add newlines before and after for proper spacing
                prefix = '\n\n'
                suffix = ''
            else:
                # Insert before the target node
                insert_pos = node.start_byte
                indent_char, indent_width = _detect_indent(current_source, node.start_byte)
                target_indent = indent_char * indent_width
                prefix = ''
                suffix = '\n\n'

            reindented_code = _reindent(new_code.strip(), target_indent)

            return {
                'start': insert_pos,
                'end': insert_pos,  # No deletion for insert
                'replacement': prefix + reindented_code + suffix,
                'target': target,
                'operation': 'insert',
                'position': 'after' if is_after else 'before'
            }

        # Handle REPLACE operation (default)
        target = edit_spec.get('target')
        replace_mode = edit_spec.get('replace', 'body')

        if not target:
            return {'error': 'No target specified', 'target': None}

        # Find target node
        try:
            node, node_type = _find_target_node(current_tree, current_bytes, target, lang)
        except ValueError as e:
            return {'error': str(e), 'target': target}

        if not node:
            return {'error': f'Target not found: {target}', 'target': target}

        # Check for class body replacement
        if replace_mode == 'body' and node_type == 'class':
            return {'error': 'Cannot replace body of class (use replace=full)', 'target': target}

        # Compute edit range
        try:
            start, end, target_indent = _compute_edit_range(node, current_source, lang, replace_mode)
        except ValueError as e:
            return {'error': str(e), 'target': target}

        # Re-indent the new code
        reindented_code = _reindent(new_code.strip(), target_indent)

        return {
            'start': start,
            'end': end,
            'replacement': reindented_code,
            'target': target,
            'operation': 'replace',
            'replace_mode': replace_mode
        }

    # Helper to check for syntax errors
    def has_errors(node):
        if node.type == 'ERROR':
            return True
        for child in node.children:
            if has_errors(child):
                return True
        return False

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

        # Check for batch mode (edits array)
        if 'edits' in edit:
            edits_list = edit.get('edits', [])
            # force_write from CLI overrides dry_run in JSON
            dry_run = not force_write and edit.get('dry_run', True)

            if not edits_list:
                yield {
                    'success': False,
                    'error': 'Empty edits array'
                }
                continue

            # Process all edits to compute their ranges
            edit_results = []
            errors = []

            for edit_spec in edits_list:
                result = process_single_edit(edit_spec, source, tree, source_bytes)
                if 'error' in result:
                    errors.append(result)
                else:
                    edit_results.append(result)

            if errors:
                yield {
                    'success': False,
                    'target': 'batch',
                    'error': f'{len(errors)} edit(s) failed',
                    'errors': errors
                }
                continue

            # Sort edits by start position in REVERSE order
            # This ensures earlier edits don't shift positions of later ones
            edit_results.sort(key=lambda x: x['start'], reverse=True)

            # Apply all edits
            modified = source
            for edit_result in edit_results:
                modified = (
                    modified[:edit_result['start']] +
                    edit_result['replacement'] +
                    modified[edit_result['end']:]
                )

            # Validate final result
            modified_bytes = modified.encode('utf-8')
            modified_tree = parser.parse(modified_bytes)

            if has_errors(modified_tree.root_node):
                yield {
                    'success': False,
                    'target': 'batch',
                    'error': 'Modified code has syntax errors',
                    'edits_applied': len(edit_results),
                    'modified': modified if dry_run else None
                }
                continue

            # Output batch result
            if dry_run:
                yield {
                    'success': True,
                    'target': 'batch',
                    'edits_applied': len(edit_results),
                    'targets': [e['target'] for e in edit_results],
                    'modified': modified
                }
            else:
                try:
                    # Create backup before first write (if enabled)
                    if create_backup and backup_created is None:
                        backup_created = _create_backup(file_path)

                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(modified)

                    result_obj = {
                        'success': True,
                        'target': 'batch',
                        'edits_applied': len(edit_results),
                        'targets': [e['target'] for e in edit_results],
                        'file': file_path
                    }
                    if backup_created:
                        result_obj['backup'] = backup_created
                    yield result_obj

                    # Update state for subsequent edits
                    source = modified
                    source_bytes = modified_bytes
                    tree = modified_tree
                except IOError as e:
                    yield {
                        'success': False,
                        'target': 'batch',
                        'error': f'Failed to write file: {e}'
                    }
            continue

        # Single edit mode - use the helper function
        # force_write from CLI overrides dry_run in JSON
        dry_run = not force_write and edit.get('dry_run', True)

        # Process the edit
        result = process_single_edit(edit, source, tree, source_bytes)

        if 'error' in result:
            yield {
                'success': False,
                'target': result.get('target'),
                'error': result['error']
            }
            continue

        # Apply the edit
        modified = (
            source[:result['start']] +
            result['replacement'] +
            source[result['end']:]
        )

        # Validate the modified code parses correctly
        modified_bytes = modified.encode('utf-8')
        modified_tree = parser.parse(modified_bytes)

        if has_errors(modified_tree.root_node):
            yield {
                'success': False,
                'target': result['target'],
                'operation': result.get('operation', 'replace'),
                'error': 'Modified code has syntax errors',
                'modified': modified if dry_run else None
            }
            continue

        # Output result
        if dry_run:
            yield {
                'success': True,
                'target': result['target'],
                'operation': result.get('operation', 'replace'),
                'replace': result.get('replace_mode'),
                'modified': modified
            }
        else:
            # Write to file
            try:
                # Create backup before first write (if enabled)
                if create_backup and backup_created is None:
                    backup_created = _create_backup(file_path)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified)

                result_obj = {
                    'success': True,
                    'target': result['target'],
                    'operation': result.get('operation', 'replace'),
                    'replace': result.get('replace_mode'),
                    'file': file_path
                }
                if backup_created:
                    result_obj['backup'] = backup_created
                yield result_obj

                # Re-parse for subsequent edits
                source = modified
                source_bytes = modified_bytes
                tree = modified_tree
            except IOError as e:
                yield {
                    'success': False,
                    'target': result['target'],
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

    # Write mode options (Phase 5)
    parser.add_argument('--write', action='store_true',
                       help='Actually write changes to file (default: dry run)')
    parser.add_argument('--backup', dest='backup', action='store_true', default=True,
                       help='Create backup before writing (default: True)')
    parser.add_argument('--no-backup', dest='backup', action='store_false',
                       help='Skip backup creation')
    parser.add_argument('--git-safe', dest='git_safe', action='store_true', default=True,
                       help='Refuse to modify files with uncommitted changes (default: True)')
    parser.add_argument('--no-git-safe', dest='git_safe', action='store_false',
                       help='Allow modifying files with uncommitted changes')

    args = parser.parse_args()

    if args.mode == 'write':
        config = {
            'file': args.file,
            'lang': args.lang,
            'write': args.write,
            'backup': args.backup,
            'git_safe': args.git_safe,
        }
        for record in writes(config):
            print(json.dumps(record), flush=True)
    else:
        config = {
            'mode': args.output_mode,
            'lang': args.lang,
            'filename': args.filename,
        }
        for record in reads(config):
            print(json.dumps(record), flush=True)
