"""Tests for Tree-sitter code analysis plugin."""

import json


SAMPLE_PYTHON = '''import os
from pathlib import Path

class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        result = a + b
        return result

    def multiply(self, a, b):
        return a * b

def main():
    calc = Calculator()
    result = calc.add(1, 2)
    print(result)

if __name__ == "__main__":
    main()
'''


def test_treesitter_symbols_mode(invoke):
    """Test extracting symbols (functions, classes, methods) from Python code."""
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--output-mode", "symbols", "--filename", "test.py"],
        input_data=SAMPLE_PYTHON,
    )

    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should find: 1 class + 2 methods + 1 function = 4 symbols
    assert len(records) == 4

    # Check class
    classes = [r for r in records if r["type"] == "class"]
    assert len(classes) == 1
    assert classes[0]["name"] == "Calculator"

    # Check methods
    methods = [r for r in records if r["type"] == "method"]
    assert len(methods) == 2
    method_names = {m["name"] for m in methods}
    assert method_names == {"add", "multiply"}

    # Check methods have parent_class
    for method in methods:
        assert method["parent_class"] == "Calculator"

    # Check function
    functions = [r for r in records if r["type"] == "function"]
    assert len(functions) == 1
    assert functions[0]["name"] == "main"
    assert functions[0]["parent_class"] is None


def test_treesitter_calls_mode(invoke):
    """Test extracting function calls from Python code."""
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--output-mode", "calls", "--filename", "test.py"],
        input_data=SAMPLE_PYTHON,
    )

    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should find several calls in main()
    assert len(records) >= 3

    # Check for specific calls
    callees = [r["callee"] for r in records]
    assert "Calculator" in callees  # Constructor call
    assert "print" in callees       # print call

    # Check that calls have caller context
    main_calls = [r for r in records if r["caller"] == "main"]
    assert len(main_calls) >= 3

    # Check module-level call
    module_calls = [r for r in records if r["caller"] == "<module>"]
    assert len(module_calls) == 1
    assert module_calls[0]["callee"] == "main"


def test_treesitter_imports_mode(invoke):
    """Test extracting imports from Python code."""
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--output-mode", "imports", "--filename", "test.py"],
        input_data=SAMPLE_PYTHON,
    )

    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    assert len(records) == 2

    imports = [r["raw"] for r in records]
    assert "import os" in imports
    assert "from pathlib import Path" in imports


def test_treesitter_skeleton_mode(invoke):
    """Test generating skeleton code (bodies stripped)."""
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--output-mode", "skeleton", "--filename", "test.py"],
        input_data=SAMPLE_PYTHON,
    )

    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    assert len(records) == 1
    record = records[0]

    assert record["type"] == "skeleton"
    assert record["functions_stripped"] == 3  # add, multiply, main

    content = record["content"]

    # Should have function signatures but not bodies
    assert "def add(self, a: int, b: int) -> int:" in content
    assert "def multiply(self, a, b):" in content
    assert "def main():" in content

    # Bodies should be replaced with ...
    assert "..." in content

    # Should NOT have implementation details
    assert "result = a + b" not in content
    assert "return result" not in content


def test_treesitter_strings_mode(invoke):
    """Test extracting string literals."""
    code = '''
def greet(name):
    message = "Hello, " + name
    return f"Welcome {name}!"
'''
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--output-mode", "strings", "--filename", "test.py"],
        input_data=code,
    )

    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    assert len(records) >= 2

    # All should be string type
    for r in records:
        assert r["type"] == "string"


def test_treesitter_comments_mode(invoke):
    """Test extracting comments."""
    code = '''# This is a comment
def foo():
    # Another comment
    pass
'''
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--output-mode", "comments", "--filename", "test.py"],
        input_data=code,
    )

    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    assert len(records) == 2

    comments = [r["value"] for r in records]
    assert "# This is a comment" in comments
    assert "# Another comment" in comments


def test_treesitter_language_detection(invoke):
    """Test language auto-detection from filename."""
    # Python file
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--filename", "test.py"],
        input_data="def foo(): pass",
    )
    assert res.exit_code == 0
    records = [json.loads(line) for line in res.output.strip().split("\n") if line]
    assert len(records) == 1
    assert records[0]["name"] == "foo"


def test_treesitter_explicit_language(invoke):
    """Test explicit language override."""
    # Use explicit --lang even with wrong extension
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--lang", "python", "--filename", "script"],
        input_data="def bar(): pass",
    )
    assert res.exit_code == 0
    records = [json.loads(line) for line in res.output.strip().split("\n") if line]
    assert len(records) == 1
    assert records[0]["name"] == "bar"


def test_treesitter_nested_class(invoke):
    """Test handling of nested classes and methods."""
    code = '''
class Outer:
    class Inner:
        def inner_method(self):
            pass

    def outer_method(self):
        pass
'''
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--output-mode", "symbols", "--filename", "test.py"],
        input_data=code,
    )

    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should find: 2 classes + 2 methods
    classes = [r for r in records if r["type"] == "class"]
    methods = [r for r in records if r["type"] == "method"]

    assert len(classes) == 2
    class_names = {c["name"] for c in classes}
    assert class_names == {"Outer", "Inner"}

    assert len(methods) == 2


def test_treesitter_empty_file(invoke):
    """Test handling of empty file."""
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "read", "--filename", "test.py"],
        input_data="",
    )

    assert res.exit_code == 0
    # Should produce no output for empty file
    assert res.output.strip() == ""


def test_treesitter_write_mode_error(invoke):
    """Test that write mode returns error (not implemented)."""
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "write"],
        input_data="",
    )

    assert res.exit_code == 1
    assert "write mode not implemented" in res.output.lower()
