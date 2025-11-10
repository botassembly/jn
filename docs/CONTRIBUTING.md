# Contributing to JN

Thank you for your interest in contributing to JN! This guide will help you get started.

---

## Quick Start

### Prerequisites

- Python 3.9+
- `uv` for package management (install via `pip install uv`)
- `jq` for testing (optional but recommended)

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/jn.git
cd jn

# Install in development mode
pip install -e .

# Run tests
python -m pytest

# Check coverage
python -m pytest --cov=src/jn --cov-report=html

# Verify installation
jn --help
```

---

## Development Workflow

### 1. Outside-In Development

We always develop **outside-in**, starting from the CLI:

```python
# Step 1: Write a failing CLI test
def test_new_command(runner):
    result = runner.invoke(main, ['new-command', 'arg'])
    assert result.exit_code == 0
    assert 'expected output' in result.output

# Step 2: Run test (it will fail)
pytest tests/unit/test_cli.py::test_new_command -v

# Step 3: Implement the minimal code to make it pass
@main.command()
def new_command(arg):
    click.echo('expected output')

# Step 4: Test passes, commit
git add -A
git commit -m "Add new-command"
```

### 2. Testing Strategy

**Three levels of tests:**

1. **CLI tests** (outside-in, primary)
   - Test user-facing commands
   - Use Click's CliRunner
   - Mock filesystem/network when needed

2. **Integration tests** (end-to-end)
   - Test complete workflows
   - Real filesystem operations
   - Real subprocess execution

3. **Plugin self-tests** (built-in)
   - Every plugin tests itself
   - Uses examples() function
   - Runs via `jn test <plugin>`

**Example CLI test:**
```python
from click.testing import CliRunner
from jn.cli import main

def test_cat_csv_file(runner):
    """Test jn cat with CSV file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as f:
        f.write('name,age\nAlice,30\nBob,25\n')
        f.flush()

        result = runner.invoke(main, ['cat', f.name, '--limit', '1'])

        assert result.exit_code == 0
        lines = result.output.strip().split('\n')
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record['name'] == 'Alice'
```

### 3. Code Style

We follow standard Python conventions:

- **PEP 8** for style
- **Type hints** for all functions
- **Docstrings** for all public functions
- **Keep it simple** - favor readability over cleverness

```python
def resolve_plugin(
    source: str,
    registry: Optional[Registry] = None
) -> Optional[str]:
    """Resolve source string to plugin name.

    Args:
        source: File path, URL, or command
        registry: Optional registry (uses default if None)

    Returns:
        Plugin name or None if no match

    Examples:
        >>> resolve_plugin('data.csv')
        'csv_reader'
        >>> resolve_plugin('https://api.example.com')
        'http_get'
    """
    # Implementation...
```

### 4. Commit Messages

Use conventional commits:

```
feat: add YAML reader plugin
fix: handle empty CSV files correctly
docs: update plugin development guide
test: add tests for jq filter
refactor: simplify registry resolution
perf: optimize plugin discovery caching
```

---

## How to Contribute

### Reporting Bugs

**Before filing a bug:**
1. Search existing issues
2. Try to reproduce with minimal example
3. Check if it's fixed in main branch

**When filing a bug:**
- Describe what you expected to happen
- Describe what actually happened
- Provide a minimal reproduction
- Include version (`jn --version`)
- Include OS and Python version

**Template:**
```markdown
**Bug Description:**
Brief description of the bug

**To Reproduce:**
1. Run `jn cat data.csv`
2. Error occurs

**Expected Behavior:**
Should output NDJSON

**Actual Behavior:**
Crashes with error

**Environment:**
- JN version: 4.0.0-alpha1
- Python version: 3.11
- OS: Ubuntu 22.04

**Additional Context:**
Any other relevant information
```

### Suggesting Features

**Before suggesting a feature:**
1. Check if it's already in the [roadmap](../spec/ROADMAP.md)
2. Search existing feature requests
3. Consider if it fits JN's philosophy

**When suggesting a feature:**
- Describe the use case
- Explain why existing features don't work
- Provide examples of desired behavior
- Consider implementation complexity

**Template:**
```markdown
**Feature Request:**
Add Excel reader plugin

**Use Case:**
Need to read .xlsx files in data pipelines

**Proposed Solution:**
Create excel_reader.py using openpyxl

**Alternatives Considered:**
- Convert to CSV first (extra step)
- Use pandas (heavy dependency)

**Examples:**
```bash
jn cat report.xlsx | jq '.[] | select(.amount > 100)' | jn put filtered.json
```
```

### Contributing Code

**Step-by-step:**

1. **Fork and clone**
   ```bash
   git clone https://github.com/yourusername/jn.git
   cd jn
   git remote add upstream https://github.com/original/jn.git
   ```

2. **Create a branch**
   ```bash
   git checkout -b feat/excel-reader
   ```

3. **Write tests first**
   ```bash
   # Add test in tests/unit/test_cli.py or tests/integration/
   pytest tests/unit/test_cli.py::test_cat_excel_file -v
   # Should fail
   ```

4. **Implement feature**
   ```bash
   # Add code to make test pass
   # Follow outside-in approach
   ```

5. **Run all tests**
   ```bash
   pytest
   python -m pytest --cov=src/jn
   ```

6. **Update documentation**
   ```bash
   # Update README.md, docs/, etc.
   ```

7. **Commit and push**
   ```bash
   git add -A
   git commit -m "feat: add Excel reader plugin"
   git push origin feat/excel-reader
   ```

8. **Open pull request**
   - Describe what changed
   - Reference any related issues
   - Include test results
   - Update CHANGELOG if needed

---

## Creating a New Plugin

### Using the Template

```bash
# Create plugin from template
jn create source excel_reader --handles .xlsx --description "Read Excel files"

# This creates: plugins/readers/excel_reader.py
```

### Plugin Structure

```python
#!/usr/bin/env python3
"""Excel reader - Read Excel files and output NDJSON."""
# /// script
# dependencies = [
#   "openpyxl>=3.0.0",
# ]
# ///
# META: type=source, handles=[".xlsx", ".xls"], streaming=false

import sys
import json
from typing import Iterator, Optional

def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Read Excel file and yield records.

    Config keys:
        sheet: Sheet name or index (default: 0)
        header_row: Row number for headers (default: 0)
    """
    config = config or {}
    sheet = config.get('sheet', 0)

    import openpyxl

    # Read from stdin or file
    workbook = openpyxl.load_workbook(sys.stdin.buffer)
    worksheet = workbook.worksheets[sheet]

    # Get headers from first row
    headers = [cell.value for cell in worksheet[1]]

    # Yield rows as dicts
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        record = dict(zip(headers, row))
        yield record

def examples() -> list[dict]:
    """Test cases for this plugin."""
    return [
        {
            "description": "Read simple Excel file",
            "input": "test.xlsx",
            "expected": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]
        }
    ]

def test() -> bool:
    """Run built-in tests."""
    # Test implementation...
    return True

if __name__ == '__main__':
    # Parse args, run plugin
    for record in run():
        print(json.dumps(record))
```

### Plugin Checklist

- [ ] Includes PEP 723 dependencies
- [ ] Has META header with type and handles
- [ ] Implements run(config) function
- [ ] Implements examples() function
- [ ] Implements test() function
- [ ] Reads from stdin (sources/filters)
- [ ] Writes NDJSON to stdout
- [ ] Handles errors gracefully
- [ ] Has docstrings
- [ ] Self-tests pass (`python plugin.py --test`)

### Testing Your Plugin

```bash
# Run self-test
python plugins/readers/excel_reader.py --test

# Use with jn CLI
jn cat test.xlsx

# Register in CLI tests
def test_cat_excel_file(runner):
    result = runner.invoke(main, ['cat', 'test.xlsx'])
    assert result.exit_code == 0
```

---

## Code Review Process

### What We Look For

1. **Tests pass** - All tests must pass
2. **Coverage maintained** - Don't decrease coverage
3. **Outside-in tested** - CLI tests exist
4. **Documentation updated** - Docs match code
5. **Code quality** - Follows style guide
6. **Commit quality** - Clean, logical commits

### PR Review Checklist

- [ ] Tests pass (`pytest`)
- [ ] Coverage ≥78% (`pytest --cov=src/jn`)
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] CHANGELOG updated (if needed)
- [ ] Commits are clean and logical
- [ ] No merge conflicts

### Review Timeline

- Initial review: Within 2 days
- Follow-up: Within 1 day
- Approval: When all checks pass

---

## Development Tips

### Fast Feedback Loop

```bash
# Run specific test file
pytest tests/unit/test_cli.py -v

# Run specific test
pytest tests/unit/test_cli.py::test_cat_csv_file -v

# Run with coverage for one module
pytest tests/unit/test_cli.py --cov=src/jn/cli --cov-report=term-missing

# Watch mode (requires pytest-watch)
ptw tests/unit/test_cli.py
```

### Debugging

```bash
# Run test with pdb
pytest tests/unit/test_cli.py::test_cat_csv_file -v --pdb

# Print plugin output
jn cat data.csv --verbose

# Trace plugin execution
jn run data.csv output.json --trace
```

### Common Patterns

**Reading files in tests:**
```python
import tempfile
from pathlib import Path

def test_feature():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write('name,age\nAlice,30\n')
        f.flush()

        # Use f.name
        result = runner.invoke(main, ['cat', f.name])

        # Cleanup
        Path(f.name).unlink()
```

**Mocking subprocess:**
```python
from unittest.mock import patch, MagicMock

def test_plugin_execution():
    with patch('subprocess.Popen') as mock_popen:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Test code...
```

---

## Release Process

### Version Bumping

```bash
# Patch release (4.0.0 → 4.0.1)
# Update pyproject.toml, README.md

# Minor release (4.0.0 → 4.1.0)
# Update pyproject.toml, README.md, CHANGELOG.md

# Major release (4.0.0 → 5.0.0)
# Update pyproject.toml, README.md, CHANGELOG.md, docs/
```

### Release Checklist

- [ ] All tests pass
- [ ] Coverage ≥78%
- [ ] Documentation updated
- [ ] CHANGELOG updated
- [ ] Version bumped
- [ ] Git tag created
- [ ] PyPI package published
- [ ] GitHub release created
- [ ] Announcement posted

---

## Getting Help

### Questions?

- **Documentation:** Check [README.md](../README.md) and [docs/](.)
- **Issues:** Search [existing issues](https://github.com/yourusername/jn/issues)
- **Discussions:** Ask in [GitHub Discussions](https://github.com/yourusername/jn/discussions)
- **Chat:** Join our Discord (link TBD)

### Stuck?

Don't hesitate to ask! We're here to help:
- Comment on your PR
- Open a discussion
- Mention `@maintainers` in issues

---

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone.

### Our Standards

**Positive behavior:**
- Be respectful and inclusive
- Give constructive feedback
- Accept constructive criticism
- Focus on what's best for the community

**Unacceptable behavior:**
- Harassment or discrimination
- Trolling or insulting comments
- Personal or political attacks
- Publishing others' private information

### Enforcement

Report violations to: jn-conduct@example.com

Maintainers will review and take appropriate action.

---

## Thank You!

Every contribution matters, whether it's:
- Reporting a bug
- Fixing a typo
- Adding a feature
- Improving docs
- Sharing feedback

**Thank you for making JN better!** 🎉
