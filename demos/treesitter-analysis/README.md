# Tree-sitter Analysis Demo

This demo showcases the Tree-sitter plugin for code analysis and surgical refactoring.

## Quick Start

```bash
./run_demo.sh
```

## Features Demonstrated

### Part 1: Code Analysis (Read Mode)

1. **Symbols** - Extract functions, classes, and methods with line numbers
2. **Calls** - Extract function call graph showing caller/callee relationships
3. **Imports** - Extract import statements
4. **Skeleton** - Generate code skeleton with bodies replaced by `...` (great for LLM context)
5. **Decorators** - Extract decorators and their targets (routes, fixtures, dataclasses)

### Part 2: Surgical Refactoring (Write Mode)

6. **Body Replacement** - Replace function body while preserving signature
7. **Method Replacement** - Replace method body in a class
8. **Full Replacement** - Replace entire function/class definition

### Part 3: LCOV Join Compatibility

The Tree-sitter symbols output includes `function` field matching LCOV format, enabling joins between coverage data and code structure.

## Output Files

After running the demo:

- `symbols.json` - Functions, classes, methods with line numbers
- `calls.json` - Function call graph
- `imports.json` - Import statements
- `skeleton.json` - Code skeleton (bodies stripped)
- `decorators.json` - Decorators and their targets
- `modified_*.py` - Examples of surgical code modifications

## Example Commands

```bash
# Extract symbols
cat mycode.py | jn plugin call treesitter_ --mode read --output-mode symbols --filename mycode.py

# Generate skeleton for LLM context
cat mycode.py | jn plugin call treesitter_ --mode read --output-mode skeleton --filename mycode.py

# Replace function body
echo '{"target": "function:foo", "replace": "body", "code": "return 42"}' | \
  jn plugin call treesitter_ --mode write --file mycode.py

# Find API routes
cat app.py | jn plugin call treesitter_ --mode read --output-mode decorators --filename app.py | \
  jn filter 'select(.decorator | contains("route"))'
```
