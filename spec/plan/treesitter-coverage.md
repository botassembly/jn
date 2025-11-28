# Code Analysis with Tree-sitter

## Status: ✅ Implemented

The `@code/` profile provides language-agnostic code structure analysis.

## Usage

```bash
# Functions with coverage
jn cat "@code/functions?root=src&lcov=coverage.lcov" | jn vd

# Dead code detection (with false-positive filtering)
jn cat @code/dead | jn vd

# Call graph
jn cat @code/calls | jn vd

# Low coverage functions
jn cat "@code/functions?lcov=coverage.lcov&max=50" | jn vd
```

## Components

| Component | Output |
|-----------|--------|
| `@code/functions` | Functions with `caller_count`, optional coverage |
| `@code/calls` | Caller → callee relationships |
| `@code/dead` | Uncalled functions (filters false positives) |
| `@code/classes` | Classes only |
| `@code/methods` | Methods only |

## Parameters

- `root` - Source directory (default: `.`)
- `globs` - File patterns (default: `**/*.py`)
- `lcov` - LCOV file for coverage enrichment
- `min/max` - Coverage % filter

## Supported Languages

Python, JavaScript/TypeScript, Go, Rust

## Location

`jn_home/plugins/protocols/code_.py`
