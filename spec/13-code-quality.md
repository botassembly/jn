# Code Quality

> **Purpose**: Standards for code coverage, complexity, linting, and formatting.

---

## Quality Gates

All code must pass these checks before merge:

| Check | Tool | Threshold |
|-------|------|-----------|
| Code coverage | coverage.py | ≥70% |
| Linting | ruff | Zero errors |
| Formatting | black (Python), zig fmt (Zig) | Zero diffs |
| Type checking | mypy | Zero errors (subset) |
| Import structure | lint-imports | Zero violations |
| Plugin validation | jn check | Zero violations |

---

## Running Quality Checks

### All Checks

```bash
make check
```

This runs:
1. `black` - Format Python code
2. `ruff` - Lint and fix Python code
3. `mypy` - Type check critical modules
4. `lint-imports` - Verify import boundaries
5. `jn check plugins` - Validate plugin architecture
6. `zig fmt` - Format Zig code (if installed)

### Individual Checks

```bash
# Python formatting
uv run black src/jn tests

# Python linting
uv run ruff check src/jn tests

# Type checking
uv run mypy src/jn/core/streaming.py

# Import linting
uv run lint-imports --config importlinter.ini

# Plugin validation
uv run jn check plugins

# Zig formatting
zig fmt zq/src/ zq/tests/
```

---

## Code Coverage

### Running Coverage

```bash
make coverage
```

This generates:
- `htmlcov/` - HTML report
- `coverage.xml` - XML report (for CI)
- `coverage.json` - JSON report
- `coverage.lcov` - LCOV format

### Coverage Requirements

| Component | Minimum | Target |
|-----------|---------|--------|
| Core (`src/jn/core/`) | 70% | 85% |
| CLI (`src/jn/cli/`) | 60% | 75% |
| Plugins (`jn_home/plugins/`) | 50% | 70% |

### Coverage Configuration

`.coveragerc`:
```ini
[run]
branch = True
source = src/jn
omit =
    */tests/*
    */__pycache__/*

[report]
exclude_lines =
    pragma: no cover
    if TYPE_CHECKING:
    raise NotImplementedError
```

### Viewing Coverage

```bash
# Open HTML report
open htmlcov/index.html

# Quick summary
uv run coverage report
```

---

## Linting (Python)

### Ruff Configuration

`pyproject.toml`:
```toml
[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
]
ignore = [
    "E501",  # Line too long (handled by black)
]
```

### Common Issues

| Code | Issue | Fix |
|------|-------|-----|
| F401 | Unused import | Remove or use |
| F841 | Unused variable | Remove or prefix with `_` |
| E722 | Bare `except:` | Use specific exception |
| B007 | Unused loop variable | Prefix with `_` |

### Auto-Fix

```bash
# Fix automatically
uv run ruff check --fix src/jn tests

# Fix imports
uv run ruff check --select I --fix src/jn tests
```

---

## Formatting

### Python (Black)

```bash
# Format all Python
uv run black src/jn tests

# Check without modifying
uv run black --check src/jn tests
```

Configuration in `pyproject.toml`:
```toml
[tool.black]
line-length = 88
target-version = ["py311"]
```

### Zig (zig fmt)

```bash
# Format Zig code
zig fmt zq/src/ zq/tests/

# Check without modifying
zig fmt --check zq/src/ zq/tests/
```

---

## Type Checking (Mypy)

### Current Scope

Mypy checks a subset of high-value modules:

```bash
uv run mypy \
    src/jn/core/streaming.py \
    src/jn/addressing/types.py \
    src/jn/addressing/parser.py
```

### Expanding Coverage

Add modules incrementally:
1. Start with data models (`types.py`, `models.py`)
2. Add core logic (`parser.py`, `registry.py`)
3. Expand to CLI commands

### Configuration

`pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.11"
strict = false
warn_return_any = true
warn_unused_configs = true
```

---

## Import Structure

### Boundary Rules

`importlinter.ini` defines import boundaries:

```ini
[importlinter]
root_package = jn

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    jn.cli
    jn.core
    jn.addressing
    jn.plugins
```

### Violations

```bash
# Check imports
uv run lint-imports --config importlinter.ini
```

Common violations:
- CLI importing from core internals
- Plugins importing framework code
- Circular imports

---

## Plugin Validation

### AST-Based Checking

```bash
# Check all plugins
uv run jn check plugins

# Check specific plugin
uv run jn check plugin path/to/plugin.py

# Check core code
uv run jn check core
```

### What Gets Checked

| Rule | Description |
|------|-------------|
| `stdin_buffer_read` | No buffering entire stdin |
| `sys_exit_in_function` | No sys.exit() in plugins |
| `missing_stdout_close` | Proper pipe handling |
| `missing_dependency` | Dependencies declared |

### Whitelist

`.jncheck.toml` allows exemptions with justification:

```toml
[[whitelist]]
file = "jn_home/plugins/formats/xlsx_.py"
rule = "stdin_buffer_read"
lines = [38]
reason = "ZIP archives require complete file access"
```

---

## Cyclomatic Complexity

### Measuring Complexity

```bash
# Install radon
uv pip install radon

# Check complexity
radon cc src/jn -a -s
```

### Thresholds

| Grade | Complexity | Action |
|-------|------------|--------|
| A | 1-5 | Good |
| B | 6-10 | Acceptable |
| C | 11-20 | Consider refactoring |
| D/E/F | >20 | Must refactor |

### Reducing Complexity

- Extract helper functions
- Use early returns
- Replace nested conditionals with guard clauses
- Use dispatch tables instead of long if/elif chains

---

## CI Integration

### GitHub Actions Workflow

```yaml
name: Quality Checks

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Run checks
        run: make check

      - name: Run tests with coverage
        run: make coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml
```

### Pre-Commit Hooks

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
```

Install:
```bash
pip install pre-commit
pre-commit install
```

---

## Zig Quality

### Formatting

```bash
# Format all Zig files
make zq-fmt

# Check formatting in CI
zig fmt --check zq/src/
```

### Testing

```bash
# Run unit tests
make zq-test

# Run plugin tests
make zig-plugins-test
```

### Build Warnings

Treat warnings as errors in release builds:
```bash
zig build -Doptimize=ReleaseSafe
```

---

## Quality Dashboard

### Metrics to Track

| Metric | Tool | Target |
|--------|------|--------|
| Line coverage | coverage.py | ≥70% |
| Branch coverage | coverage.py | ≥60% |
| Lint errors | ruff | 0 |
| Type coverage | mypy | Expanding |
| Cyclomatic complexity | radon | Avg ≤10 |
| Plugin violations | jn check | 0 |

### Badges

Add to README:
```markdown
[![Coverage](https://codecov.io/gh/owner/jn/branch/main/graph/badge.svg)](https://codecov.io/gh/owner/jn)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
```

---

## See Also

- [12-testing-strategy.md](12-testing-strategy.md) - Testing approach
- [00-plan.md](00-plan.md) - Implementation plan
- [04-project-layout.md](04-project-layout.md) - Where code lives
