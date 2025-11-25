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
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--output-mode",
            "symbols",
            "--filename",
            "test.py",
        ],
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

    # Check methods have parent_class and 'function' field for LCOV compatibility
    for method in methods:
        assert method["parent_class"] == "Calculator"
        # Qualified function name: Class.method for LCOV join
        assert method["function"] == f"Calculator.{method['name']}"

    # Check function
    functions = [r for r in records if r["type"] == "function"]
    assert len(functions) == 1
    assert functions[0]["name"] == "main"
    assert (
        functions[0]["function"] == "main"
    )  # Top-level functions: function == name
    assert functions[0]["parent_class"] is None

    # Check class has both 'name' and 'class' fields
    assert classes[0]["class"] == "Calculator"


def test_treesitter_calls_mode(invoke):
    """Test extracting function calls from Python code."""
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--output-mode",
            "calls",
            "--filename",
            "test.py",
        ],
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
    assert "print" in callees  # print call

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
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--output-mode",
            "imports",
            "--filename",
            "test.py",
        ],
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
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--output-mode",
            "skeleton",
            "--filename",
            "test.py",
        ],
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
    code = """
def greet(name):
    message = "Hello, " + name
    return f"Welcome {name}!"
"""
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--output-mode",
            "strings",
            "--filename",
            "test.py",
        ],
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
    code = """# This is a comment
def foo():
    # Another comment
    pass
"""
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--output-mode",
            "comments",
            "--filename",
            "test.py",
        ],
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
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--filename",
            "test.py",
        ],
        input_data="def foo(): pass",
    )
    assert res.exit_code == 0
    records = [
        json.loads(line) for line in res.output.strip().split("\n") if line
    ]
    assert len(records) == 1
    assert records[0]["name"] == "foo"


def test_treesitter_explicit_language(invoke):
    """Test explicit language override."""
    # Use explicit --lang even with wrong extension
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--lang",
            "python",
            "--filename",
            "script",
        ],
        input_data="def bar(): pass",
    )
    assert res.exit_code == 0
    records = [
        json.loads(line) for line in res.output.strip().split("\n") if line
    ]
    assert len(records) == 1
    assert records[0]["name"] == "bar"


def test_treesitter_nested_class(invoke):
    """Test handling of nested classes and methods."""
    code = """
class Outer:
    class Inner:
        def inner_method(self):
            pass

    def outer_method(self):
        pass
"""
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--output-mode",
            "symbols",
            "--filename",
            "test.py",
        ],
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
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--filename",
            "test.py",
        ],
        input_data="",
    )

    assert res.exit_code == 0
    # Should produce no output for empty file
    assert res.output.strip() == ""


def test_treesitter_write_mode_no_file(invoke):
    """Test that write mode requires --file option."""
    res = invoke(
        ["plugin", "call", "treesitter_", "--mode", "write"],
        input_data='{"target": "function:foo", "code": "pass"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is False
    assert "No file specified" in result["error"]


def test_treesitter_decorators_mode(invoke):
    """Test extracting decorators from Python code."""
    code = """
from flask import Flask
app = Flask(__name__)

@app.route("/users", methods=["GET"])
def get_users():
    return []

@app.route("/users/<id>")
def get_user(id):
    return {}

@pytest.fixture
def client():
    return app.test_client()

@dataclass
class User:
    name: str
"""
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--output-mode",
            "decorators",
            "--filename",
            "test.py",
        ],
        input_data=code,
    )

    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Should find 4 decorators
    assert len(records) == 4

    # Check decorator types
    for r in records:
        assert r["type"] == "decorator"
        assert "decorator" in r
        assert "target" in r
        assert "target_type" in r

    # Check specific decorators
    decorators = {r["decorator"]: r for r in records}

    # Flask routes
    assert "app.route" in decorators
    route_decorators = [r for r in records if r["decorator"] == "app.route"]
    assert len(route_decorators) == 2

    # pytest.fixture
    assert "pytest.fixture" in decorators
    assert decorators["pytest.fixture"]["target"] == "client"
    assert decorators["pytest.fixture"]["target_type"] == "function"

    # dataclass on class
    assert "dataclass" in decorators
    assert decorators["dataclass"]["target"] == "User"
    assert decorators["dataclass"]["target_type"] == "class"


def test_treesitter_decorators_with_args(invoke):
    """Test extracting decorators with arguments."""
    code = """
@app.route("/api/v1/users", methods=["GET", "POST"])
def users_endpoint():
    pass
"""
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "read",
            "--output-mode",
            "decorators",
            "--filename",
            "test.py",
        ],
        input_data=code,
    )

    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    assert len(records) == 1
    dec = records[0]

    assert dec["decorator"] == "app.route"
    assert dec["target"] == "users_endpoint"
    assert len(dec["args"]) > 0  # Has arguments
    assert "/api/v1/users" in dec["raw"]


def test_treesitter_write_body_replacement(invoke, tmp_path):
    """Test surgical body replacement in write mode."""
    # Create test file
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def calculate(a, b):
    result = a + b
    return result
"""
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "function:calculate", "replace": "body", "code": "return a * b"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert "return a * b" in result["modified"]
    assert "result = a + b" not in result["modified"]
    # Signature should be preserved
    assert "def calculate(a, b):" in result["modified"]


def test_treesitter_write_method_replacement(invoke, tmp_path):
    """Test method body replacement in write mode."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """class Calculator:
    def add(self, x, y):
        return x + y

    def multiply(self, x, y):
        return x * y
"""
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "method:Calculator.add", "replace": "body", "code": "return x + y + 1"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert "return x + y + 1" in result["modified"]
    # Other method should be unchanged
    assert "return x * y" in result["modified"]


def test_treesitter_write_full_replacement(invoke, tmp_path):
    """Test full function replacement in write mode."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def old_func():
    return 42

def keep_this():
    return 1
"""
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "function:old_func", "replace": "full", "code": "def new_func(x):\\n    return x * 2"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert "def new_func(x):" in result["modified"]
    assert "def old_func" not in result["modified"]
    # Other function should be unchanged
    assert "def keep_this():" in result["modified"]


def test_treesitter_write_target_not_found(invoke, tmp_path):
    """Test error when target function not found."""
    test_file = tmp_path / "test.py"
    test_file.write_text("def foo(): pass\n")

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "function:nonexistent", "replace": "body", "code": "pass"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_treesitter_write_multiline_body(invoke, tmp_path):
    """Test multi-line body replacement with proper indentation."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def process(x):
    return x
"""
    )

    new_code = "if x < 0:\\n    return 0\\nresult = x * 2\\nreturn result"

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data=f'{{"target": "function:process", "replace": "body", "code": "{new_code}"}}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert "if x < 0:" in result["modified"]
    assert "return result" in result["modified"]


def test_treesitter_write_multi_edit_batch(invoke, tmp_path):
    """Test batch multi-edit mode replacing multiple functions at once."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def foo():
    return 1

def bar():
    return 2

def baz():
    return 3
"""
    )

    # Multi-edit: replace foo and baz, leave bar unchanged
    batch_input = json.dumps(
        {
            "edits": [
                {
                    "target": "function:foo",
                    "replace": "body",
                    "code": "return 10",
                },
                {
                    "target": "function:baz",
                    "replace": "body",
                    "code": "return 30",
                },
            ]
        }
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data=batch_input,
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert result["target"] == "batch"
    assert result["edits_applied"] == 2
    assert "function:foo" in result["targets"]
    assert "function:baz" in result["targets"]

    # Check modified code
    modified = result["modified"]
    assert "return 10" in modified  # foo was changed
    assert "return 2" in modified  # bar unchanged
    assert "return 30" in modified  # baz was changed


def test_treesitter_write_multi_edit_error_handling(invoke, tmp_path):
    """Test batch mode fails atomically if any edit fails."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def foo():
    return 1

def bar():
    return 2
"""
    )

    # One valid edit, one invalid (nonexistent function)
    batch_input = json.dumps(
        {
            "edits": [
                {
                    "target": "function:foo",
                    "replace": "body",
                    "code": "return 10",
                },
                {
                    "target": "function:nonexistent",
                    "replace": "body",
                    "code": "return 99",
                },
            ]
        }
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data=batch_input,
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is False
    assert "failed" in result["error"].lower()
    assert "errors" in result  # Should have errors array


def test_treesitter_write_multi_edit_reverse_order(invoke, tmp_path):
    """Test that multi-edit applies in reverse order to preserve positions."""
    test_file = tmp_path / "test.py"
    # Create file with functions at specific positions
    test_file.write_text(
        """def first():
    pass

def second():
    pass

def third():
    pass
"""
    )

    # Edit all three functions - should work regardless of order in input
    batch_input = json.dumps(
        {
            "edits": [
                {
                    "target": "function:first",
                    "replace": "body",
                    "code": "return 'first_modified'",
                },
                {
                    "target": "function:second",
                    "replace": "body",
                    "code": "return 'second_modified'",
                },
                {
                    "target": "function:third",
                    "replace": "body",
                    "code": "return 'third_modified'",
                },
            ]
        }
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data=batch_input,
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert result["edits_applied"] == 3

    # All three should be modified correctly
    modified = result["modified"]
    assert "first_modified" in modified
    assert "second_modified" in modified
    assert "third_modified" in modified


def test_treesitter_write_multi_edit_empty(invoke, tmp_path):
    """Test that empty edits array returns error."""
    test_file = tmp_path / "test.py"
    test_file.write_text("def foo(): pass\n")

    batch_input = json.dumps({"edits": []})

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data=batch_input,
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is False
    assert "empty" in result["error"].lower()


def test_treesitter_write_delete_function(invoke, tmp_path):
    """Test deleting a function."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def keep_this():
    return 1

def delete_me():
    return 2

def also_keep():
    return 3
"""
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"operation": "delete", "target": "function:delete_me"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert result["operation"] == "delete"

    # Check the function was removed
    modified = result["modified"]
    assert "def keep_this" in modified
    assert "def delete_me" not in modified
    assert "def also_keep" in modified


def test_treesitter_write_insert_after(invoke, tmp_path):
    """Test inserting a function after another function."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def first():
    return 1

def third():
    return 3
"""
    )

    new_func = "def second():\\n    return 2"
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data=f'{{"operation": "insert", "after": "function:first", "code": "{new_func}"}}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert result["operation"] == "insert"

    # Check the function was inserted
    modified = result["modified"]
    assert "def first" in modified
    assert "def second" in modified
    assert "def third" in modified

    # Check order: first should come before second
    first_pos = modified.find("def first")
    second_pos = modified.find("def second")
    third_pos = modified.find("def third")
    assert first_pos < second_pos < third_pos


def test_treesitter_write_insert_before(invoke, tmp_path):
    """Test inserting a function before another function."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def second():
    return 2

def third():
    return 3
"""
    )

    new_func = "def first():\\n    return 1"
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data=f'{{"operation": "insert", "before": "function:second", "code": "{new_func}"}}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert result["operation"] == "insert"

    # Check the function was inserted
    modified = result["modified"]
    assert "def first" in modified
    assert "def second" in modified
    assert "def third" in modified

    # Check order: first should come before second
    first_pos = modified.find("def first")
    second_pos = modified.find("def second")
    assert first_pos < second_pos


def test_treesitter_write_batch_with_delete(invoke, tmp_path):
    """Test batch mode with mixed operations including delete."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def foo():
    return 1

def bar():
    return 2

def baz():
    return 3
"""
    )

    batch_input = json.dumps(
        {
            "edits": [
                {
                    "target": "function:foo",
                    "replace": "body",
                    "code": "return 10",
                },
                {"operation": "delete", "target": "function:bar"},
            ]
        }
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data=batch_input,
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert result["edits_applied"] == 2

    # Check modifications
    modified = result["modified"]
    assert "return 10" in modified  # foo was modified
    assert "def bar" not in modified  # bar was deleted
    assert "def baz" in modified  # baz unchanged


def test_treesitter_write_delete_nonexistent(invoke, tmp_path):
    """Test deleting a nonexistent function returns error."""
    test_file = tmp_path / "test.py"
    test_file.write_text("def foo(): pass\n")

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"operation": "delete", "target": "function:nonexistent"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_treesitter_write_insert_requires_position(invoke, tmp_path):
    """Test insert without after/before returns error."""
    test_file = tmp_path / "test.py"
    test_file.write_text("def foo(): pass\n")

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"operation": "insert", "code": "def bar(): pass"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is False
    assert (
        "after" in result["error"].lower()
        or "before" in result["error"].lower()
    )


# ============================================================================
# Phase 4: Advanced Targets Tests
# ============================================================================


def test_treesitter_write_line_range_target(invoke, tmp_path):
    """Test targeting a function by line range."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def first():
    return 1

def second():
    return 2

def third():
    return 3
"""
    )

    # Target lines 4-5 which contain def second(): return 2
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "lines:4-5", "replace": "body", "code": "return 22"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True

    # second() should be modified
    modified = result["modified"]
    assert "return 1" in modified  # first unchanged
    assert "return 22" in modified  # second modified
    assert "return 3" in modified  # third unchanged


def test_treesitter_write_decorator_target(invoke, tmp_path):
    """Test targeting a function by its decorator."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def regular_func():
    return 1

@deprecated
def old_func():
    return 2

@cached
def expensive_func():
    return 3
"""
    )

    # Target function decorated with @deprecated
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "decorator:deprecated", "replace": "body", "code": "raise NotImplementedError()"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True

    # old_func should be modified
    modified = result["modified"]
    assert "return 1" in modified  # regular_func unchanged
    assert "NotImplementedError" in modified  # old_func modified
    assert "return 3" in modified  # expensive_func unchanged


def test_treesitter_write_wildcard_function(invoke, tmp_path):
    """Test wildcard pattern matching for function names."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 2 - 1 == 1

def helper():
    return 42
"""
    )

    # Target first test_* function
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "function:test_*", "replace": "body", "code": "pass  # TODO"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True

    # First matching test function should be modified
    modified = result["modified"]
    assert "pass  # TODO" in modified


def test_treesitter_write_wildcard_method(invoke, tmp_path):
    """Test wildcard pattern matching for method names in a class."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def helper(self):
        pass
"""
    )

    # Target Calculator.* (first method in Calculator)
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "method:Calculator.*", "replace": "body", "code": "return 0"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert "return 0" in result["modified"]


def test_treesitter_write_line_range_invalid(invoke, tmp_path):
    """Test invalid line range format returns error."""
    test_file = tmp_path / "test.py"
    test_file.write_text("def foo(): pass\n")

    # Missing end line
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "lines:5", "replace": "body", "code": "pass"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is False
    assert (
        "line range" in result["error"].lower()
        or "start-end" in result["error"].lower()
    )


def test_treesitter_write_decorator_target_not_found(invoke, tmp_path):
    """Test decorator target not found returns error."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def regular_func():
    return 1
"""
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "decorator:nonexistent", "replace": "body", "code": "pass"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_treesitter_write_delete_by_decorator(invoke, tmp_path):
    """Test deleting a function by its decorator."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def keep():
    return 1

@deprecated
def remove_me():
    return 2

def also_keep():
    return 3
"""
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"operation": "delete", "target": "decorator:deprecated"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True

    modified = result["modified"]
    assert "def keep" in modified
    assert "def remove_me" not in modified
    assert "def also_keep" in modified


# ============================================================================
# Phase 5: Write-Back Support Tests
# ============================================================================


def test_treesitter_write_flag_writes_file(invoke, tmp_path):
    """Test --write flag actually writes to file."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def foo():
    return 1
"""
    )
    original_content = test_file.read_text()

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
            "--write",
            "--no-backup",
            "--no-git-safe",
        ],
        input_data='{"target": "function:foo", "replace": "body", "code": "return 42"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert "file" in result  # Returns file path when written
    assert "modified" not in result  # No modified field when writing

    # Verify file was actually modified
    new_content = test_file.read_text()
    assert new_content != original_content
    assert "return 42" in new_content


def test_treesitter_write_creates_backup(invoke, tmp_path):
    """Test --write with --backup creates a backup file."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def foo():
    return 1
"""
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
            "--write",
            "--backup",
            "--no-git-safe",
        ],
        input_data='{"target": "function:foo", "replace": "body", "code": "return 42"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert "backup" in result

    # Verify backup file exists and contains original content
    from pathlib import Path

    backup_path = Path(result["backup"])
    assert backup_path.exists()
    backup_content = backup_path.read_text()
    assert "return 1" in backup_content  # Original content

    # Clean up backup
    backup_path.unlink()


def test_treesitter_write_no_backup(invoke, tmp_path):
    """Test --no-backup skips backup creation."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def foo():
    return 1
"""
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
            "--write",
            "--no-backup",
            "--no-git-safe",
        ],
        input_data='{"target": "function:foo", "replace": "body", "code": "return 42"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert "backup" not in result  # No backup created

    # Verify no backup files were created
    from pathlib import Path

    backup_files = list(tmp_path.glob("*.bak"))
    assert len(backup_files) == 0


def test_treesitter_dry_run_default(invoke, tmp_path):
    """Test default behavior is dry-run (no file modification)."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def foo():
    return 1
"""
    )
    original_content = test_file.read_text()

    # No --write flag
    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
        ],
        input_data='{"target": "function:foo", "replace": "body", "code": "return 42"}',
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert "modified" in result  # Returns modified code
    assert "file" not in result  # No file path (not written)

    # Verify file was NOT modified
    new_content = test_file.read_text()
    assert new_content == original_content


def test_treesitter_write_batch_with_backup(invoke, tmp_path):
    """Test batch mode with --write creates single backup."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """def foo():
    return 1

def bar():
    return 2
"""
    )

    batch_input = json.dumps(
        {
            "edits": [
                {
                    "target": "function:foo",
                    "replace": "body",
                    "code": "return 10",
                },
                {
                    "target": "function:bar",
                    "replace": "body",
                    "code": "return 20",
                },
            ]
        }
    )

    res = invoke(
        [
            "plugin",
            "call",
            "treesitter_",
            "--mode",
            "write",
            "--file",
            str(test_file),
            "--write",
            "--backup",
            "--no-git-safe",
        ],
        input_data=batch_input,
    )

    assert res.exit_code == 0
    result = json.loads(res.output.strip())
    assert result["success"] is True
    assert result["edits_applied"] == 2
    assert "backup" in result

    # Verify only one backup created
    from pathlib import Path

    backup_path = Path(result["backup"])
    assert backup_path.exists()
    backup_files = list(tmp_path.glob("*.bak"))
    assert len(backup_files) == 1

    # Verify file was modified
    new_content = test_file.read_text()
    assert "return 10" in new_content
    assert "return 20" in new_content

    # Clean up
    backup_path.unlink()
