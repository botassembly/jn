# JN Next-Gen: Ground-Up Implementation Plan

**Version:** 1.0
**Date:** 2025-11-09
**Approach:** Clean-slate build of next-gen architecture

---

## Overview

This document outlines building JN from scratch according to `nextgen-redesign.md`, without backward compatibility constraints.

**Goal:** Fastest path to a working agent-friendly ETL framework.

---

## Week 1: Minimal Core

**Philosophy:** Get something working end-to-end in week 1.

### Day 1-2: Project Bootstrap

```bash
# Create new project
mkdir jn-next
cd jn-next

# Project structure
jn-next/
  src/jn/
    __init__.py
    cli.py           # Typer app
    runner.py        # Pipeline execution
    discovery.py     # Plugin scanning
  plugins/
    csv_reader.py
    csv_writer.py
    jq_filter.py
  tests/
  pyproject.toml
```

**pyproject.toml:**
```toml
[project]
name = "jn"
version = "4.0.0"
dependencies = [
    "typer>=0.12.0",
    "uv>=0.4.0"
]

[project.scripts]
jn = "jn.cli:app"
```

**Core philosophy:** Zero dependencies except Typer and UV.

### Day 3-4: Plugin Discovery

**File:** `src/jn/discovery.py`

```python
import re
from pathlib import Path
from typing import Dict, Any

def discover_plugins(scan_paths: list[Path]) -> Dict[str, Dict[str, Any]]:
    """Scan for plugins without importing them."""
    plugins = {}

    for base_path in scan_paths:
        if not base_path.exists():
            continue

        for file in base_path.glob("*.py"):
            metadata = parse_metadata(file)
            if metadata:
                plugins[file.stem] = {
                    'path': file,
                    'name': file.stem,
                    **metadata,
                    'modified': file.stat().st_mtime
                }

    return plugins

def parse_metadata(file: Path) -> Dict[str, Any] | None:
    """Extract metadata from file header using regex."""
    content = file.read_text()

    # Match: # META: type=filter, handles=[".csv", ".json"]
    pattern = r'# META: type=(\w+)(?:, handles=\[(.*?)\])?'
    match = re.search(pattern, content)

    if not match:
        return None

    type_val = match.group(1)
    handles_str = match.group(2)

    handles = []
    if handles_str:
        # Parse list of quoted strings
        handles = re.findall(r'"([^"]+)"', handles_str)

    return {
        'type': type_val,
        'handles': handles
    }

def get_plugin_paths() -> list[Path]:
    """Get standard plugin search paths."""
    return [
        Path.cwd() / '.jn' / 'plugins',      # Project-local
        Path.home() / '.jn' / 'plugins',     # User global
        Path('/usr/local/share/jn/plugins')  # System-wide
    ]
```

**Test it:**
```python
# tests/test_discovery.py
def test_discover_plugins(tmp_path):
    # Create test plugin
    plugin = tmp_path / "test_filter.py"
    plugin.write_text('# META: type=filter, handles=[".json"]')

    plugins = discover_plugins([tmp_path])

    assert 'test_filter' in plugins
    assert plugins['test_filter']['type'] == 'filter'
    assert '.json' in plugins['test_filter']['handles']
```

### Day 5: Simple CLI

**File:** `src/jn/cli.py`

```python
import typer
from pathlib import Path
from .discovery import discover_plugins, get_plugin_paths

app = typer.Typer(help="JN: Agent-native ETL with JSON pipelines")

@app.command()
def discover(
    type: str = typer.Option(None, help="Filter by type")
):
    """List available plugins."""
    plugins = discover_plugins(get_plugin_paths())

    if type:
        plugins = {k: v for k, v in plugins.items() if v['type'] == type}

    for name, info in plugins.items():
        handles = ', '.join(info['handles']) if info['handles'] else 'none'
        typer.echo(f"{name:20} {info['type']:10} handles: {handles}")

@app.command()
def show(name: str):
    """Show plugin details."""
    plugins = discover_plugins(get_plugin_paths())

    if name not in plugins:
        typer.echo(f"Plugin not found: {name}", err=True)
        raise typer.Exit(1)

    info = plugins[name]
    typer.echo(f"Plugin: {name}")
    typer.echo(f"Type: {info['type']}")
    typer.echo(f"Path: {info['path']}")
    typer.echo(f"Handles: {info['handles']}")
    typer.echo(f"Modified: {info['modified']}")

if __name__ == '__main__':
    app()
```

**Test it:**
```bash
uv run jn discover
uv run jn show csv_reader
```

---

## Week 2: Essential Plugins

**Goal:** Create minimal plugin set to enable basic pipelines.

### CSV Reader Plugin

**File:** `plugins/csv_reader.py`

```python
#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=source, handles=[".csv", ".tsv"]

import csv
import json
import sys

def run(input_stream=None, config=None):
    """Read CSV from stdin, output NDJSON to stdout."""
    config = config or {}
    delimiter = config.get('delimiter', ',')

    reader = csv.DictReader(sys.stdin, delimiter=delimiter)
    for row in reader:
        print(json.dumps(row), flush=True)

def examples():
    """Return test cases."""
    return [{
        "description": "Basic CSV to NDJSON",
        "input": "name,age\nAlice,30\nBob,25",
        "expected": [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"}
        ]
    }]

if __name__ == '__main__':
    # Parse args
    if '--test' in sys.argv:
        # Run tests
        from io import StringIO
        for ex in examples():
            sys.stdin = StringIO(ex['input'])
            sys.stdout = StringIO()
            run()
            output = sys.stdout.getvalue()
            # Validate output matches expected
            print(f"✓ {ex['description']}")
    else:
        run()
```

### CSV Writer Plugin

**File:** `plugins/csv_writer.py`

```python
#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=target, handles=[".csv"]

import csv
import json
import sys

def run(input_stream=None, config=None):
    """Read NDJSON from stdin, write CSV to stdout."""
    records = []
    for line in sys.stdin:
        if line.strip():
            records.append(json.loads(line))

    if not records:
        return

    # Get all unique keys (union)
    keys = []
    seen = set()
    for record in records:
        for key in record.keys():
            if key not in seen:
                keys.append(key)
                seen.add(key)

    writer = csv.DictWriter(sys.stdout, fieldnames=keys)
    writer.writeheader()
    writer.writerows(records)

if __name__ == '__main__':
    run()
```

### JSON Passthrough

**File:** `plugins/json_passthrough.py`

```python
#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=source, handles=[".json", ".ndjson", ".jsonl"]

import sys

def run(input_stream=None, config=None):
    """Pass NDJSON through unchanged."""
    for line in sys.stdin:
        sys.stdout.write(line)
        sys.stdout.flush()

if __name__ == '__main__':
    run()
```

### JQ Filter Wrapper

**File:** `plugins/jq_filter.py`

```python
#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=filter

import subprocess
import sys
import json

def run(input_stream=None, config=None):
    """Apply jq filter to NDJSON stream."""
    config = config or {}
    query = config.get('query', '.')

    # Pipe through jq
    proc = subprocess.Popen(
        ['jq', '-c', query],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    return proc.wait()

if __name__ == '__main__':
    # Parse query from command line
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', default='.')
    args = parser.parse_args()

    run(config={'query': args.query})
```

---

## Week 3: Pipeline Execution

**Goal:** Wire plugins together automatically.

### Extension Registry

**File:** `src/jn/registry.py`

```python
import json
from pathlib import Path

def load_registry() -> dict:
    """Load extension → plugin mapping."""
    registry_path = Path.home() / '.jn' / 'registry.json'

    if registry_path.exists():
        return json.loads(registry_path.read_text())

    # Default registry
    return {
        "extensions": {
            ".csv": {"read": "csv_reader", "write": "csv_writer"},
            ".tsv": {"read": "csv_reader", "write": "csv_writer"},
            ".json": {"read": "json_passthrough", "write": "json_passthrough"},
            ".ndjson": {"read": "json_passthrough", "write": "json_passthrough"}
        }
    }

def save_registry(registry: dict):
    """Save registry to disk."""
    registry_path = Path.home() / '.jn' / 'registry.json'
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2))
```

### Pipeline Auto-Builder

**File:** `src/jn/auto_pipeline.py`

```python
from pathlib import Path
from typing import List, Dict, Any
from .registry import load_registry
from .discovery import discover_plugins, get_plugin_paths

def build_pipeline(args: List[str]) -> List[Dict[str, Any]]:
    """Auto-detect pipeline from arguments.

    Args:
        args: [input, filter1, filter2, ..., output]

    Returns:
        Pipeline steps as list of dicts
    """
    if len(args) < 2:
        raise ValueError("Need at least input and output")

    registry = load_registry()
    plugins = discover_plugins(get_plugin_paths())

    steps = []

    # First: source
    steps.append(detect_source(args[0], registry, plugins))

    # Middle: filters
    for arg in args[1:-1]:
        steps.append(detect_filter(arg, plugins))

    # Last: target
    steps.append(detect_target(args[-1], registry, plugins))

    return steps

def detect_source(arg: str, registry: dict, plugins: dict) -> dict:
    """Detect source type."""
    path = Path(arg)

    # File exists?
    if path.exists():
        ext = path.suffix
        plugin_name = registry['extensions'].get(ext, {}).get('read')
        if plugin_name:
            return {
                'type': 'source',
                'plugin': plugin_name,
                'input': str(path)
            }

    # URL?
    if arg.startswith(('http://', 'https://')):
        return {
            'type': 'source',
            'plugin': 'http_get',
            'url': arg
        }

    raise ValueError(f"Cannot detect source: {arg}")

def detect_filter(arg: str, plugins: dict) -> dict:
    """Detect filter type."""
    # Named filter in registry?
    if arg in plugins and plugins[arg]['type'] == 'filter':
        return {
            'type': 'filter',
            'plugin': arg
        }

    # Inline jq expression?
    if arg.startswith('.') or 'select(' in arg:
        return {
            'type': 'filter',
            'plugin': 'jq_filter',
            'query': arg
        }

    raise ValueError(f"Cannot detect filter: {arg}")

def detect_target(arg: str, registry: dict, plugins: dict) -> dict:
    """Detect target type."""
    path = Path(arg)
    ext = path.suffix

    plugin_name = registry['extensions'].get(ext, {}).get('write')
    if plugin_name:
        return {
            'type': 'target',
            'plugin': plugin_name,
            'output': str(path)
        }

    raise ValueError(f"Cannot detect target: {arg}")
```

### Pipeline Executor

**File:** `src/jn/runner.py`

```python
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from .discovery import discover_plugins, get_plugin_paths

def execute_pipeline(steps: List[Dict[str, Any]]):
    """Execute pipeline by chaining UV subprocesses."""
    plugins = discover_plugins(get_plugin_paths())

    # Build command chain
    processes = []

    for i, step in enumerate(steps):
        plugin_name = step['plugin']
        plugin_info = plugins.get(plugin_name)

        if not plugin_info:
            raise ValueError(f"Plugin not found: {plugin_name}")

        plugin_path = plugin_info['path']

        # Build command
        cmd = ['uv', 'run', str(plugin_path)]

        # Add plugin-specific args
        if step['type'] == 'filter' and 'query' in step:
            cmd.extend(['--query', step['query']])

        # Setup stdin/stdout
        if i == 0:
            # First step: read from file or stdin
            if 'input' in step:
                stdin = open(step['input'], 'r')
            else:
                stdin = None
        else:
            # Pipe from previous process
            stdin = processes[-1].stdout

        if i == len(steps) - 1:
            # Last step: write to file or stdout
            if 'output' in step:
                stdout = open(step['output'], 'w')
            else:
                stdout = None
        else:
            # Pipe to next process
            stdout = subprocess.PIPE

        # Start process
        proc = subprocess.Popen(
            cmd,
            stdin=stdin,
            stdout=stdout,
            stderr=subprocess.PIPE
        )
        processes.append(proc)

    # Wait for all processes
    for proc in processes:
        proc.wait()

    # Check for errors
    for i, proc in enumerate(processes):
        if proc.returncode != 0:
            stderr = proc.stderr.read().decode()
            raise RuntimeError(f"Step {i} failed: {stderr}")
```

### Add `jn run` Command

**File:** `src/jn/cli.py` (add to existing)

```python
from .auto_pipeline import build_pipeline
from .runner import execute_pipeline

@app.command()
def run(args: List[str] = typer.Argument(..., help="Pipeline: input [filters...] output")):
    """Execute automatic pipeline."""
    try:
        # Auto-detect pipeline
        steps = build_pipeline(args)

        # Show what we're doing
        typer.echo("Pipeline:", err=True)
        for i, step in enumerate(steps):
            typer.echo(f"  {i+1}. {step['type']}: {step['plugin']}", err=True)

        # Execute
        execute_pipeline(steps)

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
```

---

## Week 4: Agent Creation Tools

**Goal:** Enable agents to create/test plugins.

### Plugin Templates

**File:** `templates/filter_basic.py`

```python
#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=filter, streaming=true

import json
import sys

def run(input_stream=None, config=None):
    """TODO: Implement filter logic."""
    for line in sys.stdin:
        record = json.loads(line)
        # TODO: Transform record
        yield record

def examples():
    """Return test cases."""
    return [{
        "description": "TODO: Describe what this filter does",
        "input": [{"example": "data"}],
        "expected": [{"example": "data"}]
    }]

if __name__ == '__main__':
    for record in run():
        print(json.dumps(record))
```

### `jn create` Command

**File:** `src/jn/cli.py` (add)

```python
@app.command()
def create(
    type: str = typer.Argument(..., help="Plugin type: source|filter|target"),
    name: str = typer.Argument(..., help="Plugin name"),
    query: str = typer.Option(None, help="jq query (for filters)")
):
    """Create new plugin from template."""

    # Special case: jq filter
    if type == 'filter' and query:
        code = f'''#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=filter, streaming=true

import subprocess
import sys

def run(input_stream=None, config=None):
    """Apply jq filter: {query}"""
    proc = subprocess.Popen(
        ['jq', '-c', '{query}'],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    return proc.wait()

if __name__ == '__main__':
    run()
'''
    else:
        # Load template
        template_path = Path(__file__).parent.parent / 'templates' / f'{type}_basic.py'
        if not template_path.exists():
            typer.echo(f"Template not found: {type}_basic", err=True)
            raise typer.Exit(1)
        code = template_path.read_text()

    # Write to user plugins
    output_path = Path.home() / '.jn' / 'plugins' / f'{name}.py'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code)

    typer.echo(f"Created: {output_path}")
```

### `jn test` Command

**File:** `src/jn/cli.py` (add)

```python
@app.command()
def test(
    name: str = typer.Argument(..., help="Plugin name"),
    input_file: Path = typer.Option(None, help="Test input file")
):
    """Run plugin tests."""
    plugins = discover_plugins(get_plugin_paths())

    if name not in plugins:
        typer.echo(f"Plugin not found: {name}", err=True)
        raise typer.Exit(1)

    plugin_path = plugins[name]['path']

    if input_file:
        # Test with provided input
        result = subprocess.run(
            ['uv', 'run', str(plugin_path)],
            stdin=open(input_file),
            capture_output=True
        )
        typer.echo(result.stdout.decode())
        if result.returncode != 0:
            typer.echo(result.stderr.decode(), err=True)
            raise typer.Exit(result.returncode)
    else:
        # Run built-in tests
        result = subprocess.run(
            ['uv', 'run', str(plugin_path), '--test'],
            capture_output=True
        )
        typer.echo(result.stdout.decode())
        if result.returncode != 0:
            typer.echo(result.stderr.decode(), err=True)
            raise typer.Exit(result.returncode)
```

---

## Week 5-6: Advanced Plugins

**Goal:** Add more capable plugins.

### HTTP GET Source

**File:** `plugins/http_get.py`

```python
#!/usr/bin/env python3
# /// script
# dependencies = ["requests>=2.28.0"]
# ///
# META: type=source

import json
import sys
import requests

def run(input_stream=None, config=None):
    """Fetch from URL, output NDJSON."""
    url = config.get('url')
    if not url:
        print("Error: url required", file=sys.stderr)
        return 1

    response = requests.get(url)
    response.raise_for_status()

    data = response.json()

    # If list, emit each item
    if isinstance(data, list):
        for item in data:
            print(json.dumps(item))
    else:
        # Single object
        print(json.dumps(data))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    args = parser.parse_args()

    run(config={'url': args.url})
```

### Excel Reader

**File:** `plugins/xlsx_reader.py`

```python
#!/usr/bin/env python3
# /// script
# dependencies = ["openpyxl>=3.0.0"]
# ///
# META: type=source, handles=[".xlsx"]

import json
import sys
from openpyxl import load_workbook

def run(input_stream=None, config=None):
    """Read Excel file, output NDJSON."""
    file_path = config.get('input')
    sheet_name = config.get('sheet', None)  # None = first sheet

    wb = load_workbook(file_path, read_only=True)
    sheet = wb[sheet_name] if sheet_name else wb.active

    # Get headers from first row
    headers = [cell.value for cell in next(sheet.iter_rows())]

    # Emit rows as NDJSON
    for row in sheet.iter_rows(min_row=2):
        record = {headers[i]: cell.value for i, cell in enumerate(row)}
        print(json.dumps(record, default=str))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--sheet', default=None)
    args = parser.parse_args()

    run(config=vars(args))
```

### JC Integration

**File:** `plugins/jc_parse.py`

```python
#!/usr/bin/env python3
# /// script
# dependencies = ["jc>=1.24.0"]
# ///
# META: type=source

import json
import sys
import subprocess
import jc

def run(input_stream=None, config=None):
    """Run command through JC parser."""
    command = config.get('command', [])
    parser = config.get('parser', None)

    if not command:
        print("Error: command required", file=sys.stderr)
        return 1

    # Run command
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Command failed: {result.stderr}", file=sys.stderr)
        return result.returncode

    # Parse with JC
    if parser:
        # Use specific parser
        parsed = jc.parse(parser, result.stdout)
    else:
        # Try to auto-detect parser from command name
        cmd_name = command[0]
        if cmd_name in jc.parser_mod_list():
            parsed = jc.parse(cmd_name, result.stdout)
        else:
            print(f"No JC parser for: {cmd_name}", file=sys.stderr)
            return 1

    # Emit as NDJSON
    if isinstance(parsed, list):
        for item in parsed:
            print(json.dumps(item))
    else:
        print(json.dumps(parsed))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command', nargs='+')
    parser.add_argument('--parser', default=None)
    args = parser.parse_args()

    run(config={'command': args.command, 'parser': args.parser})
```

---

## Week 7: Polish

**Goal:** Make it production-ready.

### Better Error Messages

```python
# src/jn/errors.py
class JnError(Exception):
    """Base error with helpful messages."""

    def __init__(self, message: str, suggestion: str = None):
        self.message = message
        self.suggestion = suggestion

    def __str__(self):
        msg = f"Error: {self.message}"
        if self.suggestion:
            msg += f"\nTry: {self.suggestion}"
        return msg
```

### Schema Support

```python
# src/jn/schemas.py
def read_schema(plugin_name: str) -> dict | None:
    """Read .schema.json if exists."""
    plugins = discover_plugins(get_plugin_paths())
    if plugin_name not in plugins:
        return None

    plugin_path = plugins[plugin_name]['path']
    schema_path = plugin_path.with_suffix('.schema.json')

    if schema_path.exists():
        return json.loads(schema_path.read_text())
    return None
```

### Caching

```python
# src/jn/cache.py
import pickle
from pathlib import Path

def cache_plugins(plugins: dict):
    """Cache plugin discovery results."""
    cache_path = Path.home() / '.jn' / 'cache' / 'plugins.pkl'
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(pickle.dumps(plugins))

def load_cached_plugins() -> dict | None:
    """Load cached plugins if fresh."""
    cache_path = Path.home() / '.jn' / 'cache' / 'plugins.pkl'
    if not cache_path.exists():
        return None

    # Check if any plugin changed since cache
    cached = pickle.loads(cache_path.read_bytes())
    for name, info in cached.items():
        if info['path'].stat().st_mtime > cache_path.stat().st_mtime:
            return None  # Cache is stale

    return cached
```

---

## Week 8: Documentation & Testing

**Goal:** Complete documentation and test coverage.

### Documentation Structure

```
docs/
  README.md          # Quick start
  architecture.md    # Copy of nextgen-redesign.md
  plugins.md         # Plugin authoring guide
  agents.md          # Guide for agents
  examples/
    basic-etl.md
    agent-workflow.md
```

### Test Coverage

```python
# tests/test_discovery.py
# tests/test_auto_pipeline.py
# tests/test_runner.py
# tests/test_plugins.py
# tests/integration/test_end_to_end.py
```

**Goal:** 90%+ coverage

### Integration Tests

```python
def test_csv_to_json_pipeline(tmp_path):
    """Test full pipeline: CSV → filter → JSON."""
    # Create input
    input_csv = tmp_path / 'data.csv'
    input_csv.write_text('name,amount\nAlice,500\nBob,1500')

    output_json = tmp_path / 'output.json'

    # Run pipeline
    result = runner.invoke(app, [
        'run',
        str(input_csv),
        'select(.amount > 1000)',
        str(output_json)
    ])

    assert result.exit_code == 0

    # Verify output
    output = json.loads(output_json.read_text())
    assert len(output) == 1
    assert output[0]['name'] == 'Bob'
```

---

## Week 9: Agent Integration

**Goal:** Optimize for agent workflows.

### JSON Output Mode

All commands support `--json` for machine-readable output:

```python
@app.command()
def discover(
    type: str = typer.Option(None),
    json_output: bool = typer.Option(False, '--json')
):
    """List plugins."""
    plugins = discover_plugins(get_plugin_paths())

    if type:
        plugins = {k: v for k, v in plugins.items() if v['type'] == type}

    if json_output:
        # Machine-readable output
        output = {
            name: {
                'type': info['type'],
                'handles': info['handles'],
                'path': str(info['path'])
            }
            for name, info in plugins.items()
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        for name, info in plugins.items():
            print(f"{name:20} {info['type']}")
```

### Example Extraction

Agents can read examples without execution:

```python
@app.command()
def show_examples(name: str, format: str = typer.Option('text', help='text|json')):
    """Show plugin examples."""
    plugins = discover_plugins(get_plugin_paths())
    plugin_path = plugins[name]['path']

    # Parse examples from source (regex, no import)
    content = plugin_path.read_text()
    pattern = r'def examples\(\):.*?return (\[.*?\])'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        print("No examples found")
        return

    if format == 'json':
        # Just print the raw list
        print(match.group(1))
    else:
        # Parse and display nicely
        examples = eval(match.group(1))  # Safe in this context
        for i, ex in enumerate(examples, 1):
            print(f"{i}. {ex['description']}")
            if 'input' in ex:
                print(f"   Input: {ex['input'][:50]}...")
```

---

## Week 10: Performance

**Goal:** Optimize hot paths.

### Benchmarking

```python
# tests/benchmark.py
import time

def benchmark_discovery():
    """Measure plugin discovery speed."""
    start = time.time()
    plugins = discover_plugins(get_plugin_paths())
    elapsed = time.time() - start
    print(f"Discovered {len(plugins)} plugins in {elapsed:.3f}s")

def benchmark_pipeline():
    """Measure pipeline execution overhead."""
    # Generate 10k records
    # Run through 3 filters
    # Measure total time
    pass
```

**Targets:**
- Plugin discovery: <10ms (with caching)
- Pipeline overhead: <100ms per step
- Throughput: >10k records/sec for simple filters

### Optimizations

1. **Cache plugin discovery results**
2. **Pre-compile regex patterns**
3. **Reuse UV environments** (UV already does this)
4. **Stream large datasets** (don't buffer in memory)

---

## Week 11-12: Ecosystem

**Goal:** Make it easy to share and extend.

### Plugin Distribution

Support publishing plugins as packages:

```toml
# pyproject.toml for a plugin package
[project]
name = "jn-plugin-github"
version = "1.0.0"

[project.entry-points."jn.plugins"]
github_repos = "jn_plugin_github:github_repos"
```

### Community Repository

```bash
# Install plugin from PyPI
uv pip install jn-plugin-github

# Plugins auto-discovered in site-packages
```

### Templates Gallery

```bash
# List available templates
jn templates

# Create from community template
jn create filter my-filter --template community/date-parser
```

---

## Timeline Summary

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | Core | Discovery + basic CLI |
| 2 | Plugins | CSV, JSON, jq plugins |
| 3 | Execution | Auto-pipeline + runner |
| 4 | Agent Tools | create/test/show commands |
| 5-6 | Advanced | HTTP, Excel, JC plugins |
| 7 | Polish | Errors, schemas, caching |
| 8 | Quality | Docs + tests (90% coverage) |
| 9 | Agents | JSON mode, example extraction |
| 10 | Performance | Benchmarks + optimization |
| 11-12 | Ecosystem | Distribution + templates |

---

## Success Criteria

Ground-up build succeeds when:

1. ✅ `jn run data.csv 'select(...)' output.xlsx` works
2. ✅ Agent can `jn discover` without Python imports
3. ✅ Agent can `jn create filter` from template
4. ✅ All plugins have working `--test` flags
5. ✅ 90%+ test coverage
6. ✅ Full documentation
7. ✅ <10ms plugin discovery (cached)
8. ✅ Can distribute plugins via PyPI

---

## Dependencies

**Minimal required:**
- Python 3.10+
- UV
- jq (system binary)

**Optional:**
- JC (for shell command parsing)
- jtbl (for table display)
- Various libraries for specific plugins (openpyxl, requests, etc.)

**Philosophy:** Core has zero dependencies. Plugins declare their own.

---

## File Structure (Final)

```
jn-next/
  src/jn/
    __init__.py
    cli.py              # Typer app
    discovery.py        # Plugin scanning (regex-based)
    registry.py         # Extension → plugin mapping
    auto_pipeline.py    # Auto-detect pipeline structure
    runner.py           # Execute via UV subprocesses
    cache.py            # Cache discovery results
    schemas.py          # Schema file support
    errors.py           # Custom exceptions
  plugins/
    csv_reader.py
    csv_writer.py
    json_passthrough.py
    jq_filter.py
    http_get.py
    xlsx_reader.py
    xlsx_writer.py
    jc_parse.py
  templates/
    source_basic.py
    filter_basic.py
    target_basic.py
  tests/
    test_discovery.py
    test_auto_pipeline.py
    test_runner.py
    integration/
      test_end_to_end.py
  docs/
    README.md
    architecture.md
    plugins.md
    agents.md
  pyproject.toml
  README.md
```

---

## Advantages of Ground-Up Approach

✅ **Clean architecture** - No legacy baggage
✅ **Simpler codebase** - ~1000 LOC vs 3500 LOC
✅ **Faster** - Optimized from start
✅ **Better tested** - TDD from day 1
✅ **Agent-first** - Designed for agents, not retrofitted
✅ **Modern stack** - UV, Typer, PEP 723

---

## Risks

⚠️ **No migration path** - Users must rewrite configs
⚠️ **Greenfield unknowns** - May discover issues late
⚠️ **Learning curve** - New plugin API

**Mitigation:** Build migration tool in week 11-12

---

## Decision: Refactor or Ground-Up?

**Choose refactor if:**
- Have existing users
- Need backward compatibility
- Have working test suite to maintain

**Choose ground-up if:**
- Codebase is early/experimental
- Architecture needs fundamental change
- Want clean-slate optimization

**Recommendation:** Given current state (3500 LOC, working but complex), **refactoring is safer**. Ground-up is faster but riskier.
