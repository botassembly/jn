# JN Next-Gen Refactoring Plan

**Version:** 1.0
**Date:** 2025-11-09
**Approach:** Incremental refactoring of existing codebase to next-gen architecture

---

## Overview

This document outlines how to evolve the current JN codebase (3,582 lines, working implementation) to the next-gen architecture defined in `nextgen-redesign.md`.

**Key principle:** Maintain backward compatibility while adding new capabilities incrementally.

---

## Current State Analysis

### What Works Well (Keep)

✅ **CLI Commands (`jn cat`, `jn put`, `jn run`)**
- Already implemented in `/src/jn/cli/cat.py`
- Auto-detection logic working (`_detect_source_type()`)
- Good UX for exploration

✅ **Driver System (`/src/jn/drivers/`)**
- Clean subprocess execution (exec, shell, curl, file)
- Already isolated
- Can be wrapped as plugins easily

✅ **JC Integration (`/src/jn/jcparsers/`)**
- Custom parsers (tsv_s, psv_s, yaml_s, xml_s, toml_s, generic_s)
- Already streaming
- Good foundation for source plugins

✅ **Format Adapters (`/src/jn/adapters/`)**
- CSV, JSON, YAML, XML, TOML conversion
- Can become reader/writer plugins

✅ **Test Infrastructure**
- 86% coverage
- Fixture-based testing
- Good foundation to build on

### What Needs Changing (Evolve)

⚠️ **Config System (`/src/jn/config/`)**
- Current: Heavy Pydantic models (sources/converters/targets/pipelines)
- Target: Lightweight extension registry + plugin discovery
- Strategy: Keep for backward compat, add new system alongside

⚠️ **Models (`/src/jn/models/`)**
- Current: Pydantic classes for everything
- Target: Simple dicts for plugin configs
- Strategy: Deprecate gradually

⚠️ **Import-based Discovery**
- Current: Python imports required
- Target: Regex-based file scanning
- Strategy: Add new discovery system, keep old for transition

---

## Refactoring Strategy

### Phase 1: Add Plugin Infrastructure (Weeks 1-2)

**Goal:** Create plugin system alongside existing code

#### Step 1.1: Create Plugin Directory Structure
```bash
mkdir -p ~/.jn/plugins
mkdir -p ~/.jn/templates
mkdir -p ~/.jn/schemas
```

#### Step 1.2: Build Plugin Discovery Engine

New file: `/src/jn/plugins/discovery.py`
```python
def discover_plugins(scan_paths):
    """Scan filesystem for plugins without importing."""
    plugins = {}
    for path in scan_paths:
        for file in Path(path).glob("*.py"):
            # Parse metadata with regex (no import!)
            metadata = parse_plugin_metadata(file)
            if metadata:
                plugins[file.stem] = {
                    'path': file,
                    'type': metadata['type'],
                    'handles': metadata.get('handles', []),
                    'modified': file.stat().st_mtime
                }
    return plugins

def parse_plugin_metadata(file_path):
    """Extract metadata from file header using regex."""
    content = file_path.read_text()
    # Look for: # META: type=filter, handles=[".csv"]
    pattern = r'# META: type=(\w+)(?:, handles=\[(.*?)\])?'
    if match := re.search(pattern, content):
        return {
            'type': match.group(1),
            'handles': match.group(2).split(',') if match.group(2) else []
        }
    return None
```

#### Step 1.3: Build Extension Registry

New file: `/src/jn/plugins/registry.py`
```python
def load_extension_registry():
    """Load extension → plugin mapping."""
    registry_path = Path.home() / '.jn' / 'extensions.json'
    if registry_path.exists():
        return json.loads(registry_path.read_text())
    return default_registry()

def default_registry():
    return {
        "extensions": {
            ".csv": {"read": "csv_reader", "write": "csv_writer"},
            ".json": {"read": "json_reader", "write": "json_writer"},
            ".ndjson": {"read": "ndjson_passthrough", "write": "ndjson_passthrough"}
        }
    }
```

#### Step 1.4: Convert Existing Adapters to Plugins

**Example:** Convert CSV adapter to standalone plugin

Current: `/src/jn/adapters/target_adapters.py::_convert_to_csv()`
New: `~/.jn/plugins/csv_writer.py`

```python
#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# META: type=target, handles=[".csv"]

import csv
import json
import sys

def run(input_stream, config=None):
    """Write NDJSON to CSV."""
    records = []
    for line in input_stream:
        records.append(json.loads(line))

    if not records:
        return

    fieldnames = list(records[0].keys())
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)

if __name__ == '__main__':
    run(sys.stdin)
```

**Migration checklist:**
- [ ] csv_reader.py (from jcparsers/csv_s)
- [ ] csv_writer.py (from adapters/target_adapters)
- [ ] json_reader.py (passthrough)
- [ ] json_writer.py (from adapters/target_adapters)
- [ ] yaml_reader.py (from jcparsers/yaml_s)
- [ ] xml_reader.py (from jcparsers/xml_s)

---

### Phase 2: Dual-Mode Operation (Weeks 3-4)

**Goal:** Support both old config and new plugin discovery

#### Step 2.1: Add Plugin Execution via UV

New file: `/src/jn/plugins/executor.py`
```python
def run_plugin(plugin_path, input_data=None, config=None):
    """Execute plugin via UV subprocess."""
    cmd = ['uv', 'run', str(plugin_path)]

    # Add config as JSON arg if provided
    if config:
        cmd.extend(['--config', json.dumps(config)])

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    stdout, stderr = proc.communicate(input=input_data)
    return stdout, stderr, proc.returncode
```

#### Step 2.2: Enhance `jn run` to Support Plugins

Update `/src/jn/cli/run.py`:
```python
@app.command()
def run(
    inputs: list[str],
    # ... existing args
    use_plugins: bool = typer.Option(False, "--plugins", help="Use new plugin system")
):
    if use_plugins:
        # New path: auto-detect and compose plugins
        pipeline = build_plugin_pipeline(inputs)
        execute_plugin_pipeline(pipeline)
    else:
        # Old path: use config.json
        config.run_pipeline(pipeline_name, ...)
```

#### Step 2.3: Add New Discovery Commands

New file: `/src/jn/cli/discover.py`:
```python
@app.command()
def discover(
    type: Optional[str] = typer.Option(None, help="Filter by type"),
    changed_since: Optional[str] = typer.Option(None, help="ISO timestamp")
):
    """List available plugins."""
    plugins = discover_plugins([
        Path.cwd() / '.jn' / 'plugins',
        Path.home() / '.jn' / 'plugins'
    ])

    # Filter by type
    if type:
        plugins = {k: v for k, v in plugins.items() if v['type'] == type}

    # Filter by modification time
    if changed_since:
        cutoff = datetime.fromisoformat(changed_since).timestamp()
        plugins = {k: v for k, v in plugins.items() if v['modified'] > cutoff}

    # Display
    for name, info in plugins.items():
        typer.echo(f"{name} ({info['type']}) - {info['path']}")
```

---

### Phase 3: Enhanced Auto-Detection (Weeks 5-6)

**Goal:** Smarter automatic pipeline construction

#### Step 3.1: Build Pipeline Auto-Constructor

New file: `/src/jn/pipeline/auto.py`:
```python
def auto_build_pipeline(args):
    """Automatically construct pipeline from arguments.

    Example:
        args = ['sales.csv', 'select(.amount > 1000)', 'output.xlsx']

    Returns:
        [
            {'type': 'source', 'plugin': 'csv_reader', 'input': 'sales.csv'},
            {'type': 'filter', 'jq': 'select(.amount > 1000)'},
            {'type': 'target', 'plugin': 'xlsx_writer', 'output': 'output.xlsx'}
        ]
    """
    pipeline = []
    registry = load_extension_registry()
    plugins = discover_plugins(get_plugin_paths())

    # First arg: source
    source = detect_source(args[0], registry, plugins)
    pipeline.append(source)

    # Middle args: filters
    for arg in args[1:-1]:
        filter_step = detect_filter(arg, plugins)
        pipeline.append(filter_step)

    # Last arg: target
    target = detect_target(args[-1], registry, plugins)
    pipeline.append(target)

    return pipeline

def detect_source(arg, registry, plugins):
    """Detect source type and return config."""
    # Check if file exists
    path = Path(arg)
    if path.exists():
        ext = path.suffix
        reader = registry['extensions'].get(ext, {}).get('read')
        if reader:
            return {'type': 'source', 'plugin': reader, 'input': str(path)}

    # Check if URL
    if arg.startswith(('http://', 'https://')):
        return {'type': 'source', 'plugin': 'http_get', 'url': arg}

    # Check if command (JC parser)
    if is_jc_command(arg):
        return {'type': 'source', 'plugin': 'jc_parser', 'command': arg}

    raise ValueError(f"Cannot detect source type for: {arg}")
```

#### Step 3.2: Update `jn run` to Use Auto-Constructor

```python
@app.command()
def run(
    args: list[str] = typer.Argument(..., help="Pipeline: input [filters...] output")
):
    # Auto-detect pipeline structure
    pipeline = auto_build_pipeline(args)

    # Execute via UV subprocesses
    execute_pipeline(pipeline)
```

---

### Phase 4: Agent Tools (Weeks 7-8)

**Goal:** Add commands for agents to create/modify plugins

#### Step 4.1: Add `jn create` Command

New file: `/src/jn/cli/create.py`:
```python
@app.command()
def create(
    type: str = typer.Argument(..., help="Plugin type: source|filter|target"),
    name: str = typer.Argument(..., help="Plugin name"),
    template: Optional[str] = typer.Option(None, help="Template to use"),
    query: Optional[str] = typer.Option(None, help="jq query (for filters)")
):
    """Create new plugin from template."""

    if type == 'filter' and query:
        # Generate simple jq filter
        code = generate_jq_filter_plugin(name, query)
    else:
        # Load template
        template_path = Path(__file__).parent.parent / 'templates' / f'{type}_{template or "basic"}.py'
        code = template_path.read_text()

    # Write to user plugins directory
    output_path = Path.home() / '.jn' / 'plugins' / f'{name}.py'
    output_path.write_text(code)
    typer.echo(f"Created plugin: {output_path}")
```

#### Step 4.2: Add `jn test` Command

```python
@app.command()
def test(
    plugin_name: str = typer.Argument(..., help="Plugin to test"),
    input_file: Optional[str] = typer.Option(None, help="Test input file")
):
    """Run plugin tests."""

    # Find plugin
    plugin_path = find_plugin(plugin_name)

    if input_file:
        # Test with provided input
        with open(input_file, 'rb') as f:
            stdout, stderr, code = run_plugin(plugin_path, f.read())
        typer.echo(stdout.decode())
    else:
        # Run built-in examples
        result = subprocess.run(
            ['uv', 'run', str(plugin_path), '--test'],
            capture_output=True
        )
        typer.echo(result.stdout.decode())
```

#### Step 4.3: Add `jn show` Command

```python
@app.command()
def show(
    plugin_name: str = typer.Argument(..., help="Plugin name"),
    examples: bool = typer.Option(False, "--examples", help="Show examples"),
    schema: bool = typer.Option(False, "--schema", help="Show schema")
):
    """Show plugin details without executing."""

    plugin_path = find_plugin(plugin_name)

    if examples:
        # Parse examples from docstring/function
        code = plugin_path.read_text()
        examples_match = re.search(r'def examples\(\):.*?return \[(.*?)\]', code, re.DOTALL)
        if examples_match:
            typer.echo(examples_match.group(0))
    elif schema:
        # Read .schema.json if exists
        schema_path = plugin_path.with_suffix('.schema.json')
        if schema_path.exists():
            typer.echo(schema_path.read_text())
    else:
        # Show metadata and docstring
        metadata = parse_plugin_metadata(plugin_path)
        docstring = extract_docstring(plugin_path)
        typer.echo(f"Plugin: {plugin_name}")
        typer.echo(f"Type: {metadata['type']}")
        typer.echo(f"Handles: {metadata.get('handles', [])}")
        typer.echo(f"\n{docstring}")
```

---

### Phase 5: Deprecate Old System (Weeks 9-10)

**Goal:** Migrate all functionality to new system

#### Step 5.1: Migration Tool

```bash
jn migrate config.json
```

Converts old `jn.json` to new plugin-based structure:
- Sources → source plugins in `~/.jn/plugins/`
- Converters → filter plugins
- Targets → target plugins
- Pipelines → saved shell commands or plugin chains

#### Step 5.2: Backward Compatibility Mode

Keep old system working:
```python
# Detect if using old config.json
if config_path.exists() and not plugins_dir.exists():
    # Run in legacy mode
    use_old_system()
else:
    # Run in plugin mode
    use_new_system()
```

#### Step 5.3: Documentation Updates

- Update all examples to use new commands
- Add migration guide
- Deprecation notices in CLI help

---

### Phase 6: Cleanup (Weeks 11-12)

**Goal:** Remove old code, optimize new system

#### Step 6.1: Remove Deprecated Code

After migration period:
- Remove `/src/jn/models/` (Pydantic models)
- Remove old config system
- Simplify CLI commands

#### Step 6.2: Performance Optimization

- Cache plugin discovery results
- Pre-compile regex patterns
- Optimize UV subprocess spawning

#### Step 6.3: Polish

- Better error messages
- Shell completions for new commands
- Agent-friendly output formats (JSON mode for all commands)

---

## Migration Checklist

### Infrastructure
- [ ] Create plugin directory structure
- [ ] Build plugin discovery engine (regex-based)
- [ ] Build extension registry system
- [ ] Add UV execution wrapper

### Convert Existing Components
- [ ] CSV reader/writer → plugins
- [ ] JSON reader/writer → plugins
- [ ] YAML reader → plugin
- [ ] XML reader → plugin
- [ ] TOML reader → plugin
- [ ] JC parsers → plugins
- [ ] HTTP fetcher → plugin

### New CLI Commands
- [ ] `jn discover` - list plugins
- [ ] `jn show <plugin>` - show details without execution
- [ ] `jn create <type> <name>` - create from template
- [ ] `jn test <plugin>` - run tests
- [ ] `jn validate <plugin>` - lint and check
- [ ] `jn find --reads X --writes Y` - capability search

### Enhanced Commands
- [ ] `jn run` - auto-detect pipeline from args
- [ ] `jn cat` - keep working with new plugins
- [ ] `jn put` - keep working with new plugins

### Migration Tools
- [ ] `jn migrate config.json` - convert old to new
- [ ] Backward compatibility mode
- [ ] Migration guide documentation

### Cleanup
- [ ] Remove old models
- [ ] Remove old config system
- [ ] Update all tests
- [ ] Update all documentation

---

## Risk Mitigation

### Risk: Breaking existing workflows
**Mitigation:** Maintain backward compatibility mode for 6 months

### Risk: Performance regression
**Mitigation:** Benchmark each phase, optimize hot paths

### Risk: UV dependency issues
**Mitigation:** Fallback to venv if UV fails, document requirements

### Risk: Plugin API instability
**Mitigation:** Version plugin interface, support multiple versions

---

## Success Criteria

Refactoring succeeds when:

1. ✅ All existing CLI commands work with plugins
2. ✅ Agents can discover plugins without executing Python
3. ✅ Agents can create new plugins from templates
4. ✅ Auto-pipeline construction works for common cases
5. ✅ All existing tests pass
6. ✅ Performance is equal or better than current
7. ✅ Old config.json can be migrated automatically
8. ✅ Documentation reflects new architecture

---

## Timeline Summary

| Phase | Duration | Key Deliverable |
|-------|----------|-----------------|
| 1. Plugin Infrastructure | 2 weeks | Discovery engine, first plugins |
| 2. Dual-Mode Operation | 2 weeks | `--plugins` flag works |
| 3. Auto-Detection | 2 weeks | `jn run` auto-builds pipelines |
| 4. Agent Tools | 2 weeks | create/test/show/find commands |
| 5. Deprecation | 2 weeks | Migration complete |
| 6. Cleanup | 2 weeks | Old code removed |
| **Total** | **12 weeks** | Full next-gen system |

---

## Notes

- Keep existing tests green throughout
- Each phase should be shippable
- Feature flags for gradual rollout
- Document breaking changes clearly
- Communicate deprecation timeline early
