# Code Harvest from Old Implementation

**Purpose:** Identify reusable code, patterns, and logic from oldgen/ for next-gen implementation.

**Date:** 2025-11-09

---

## Excellent Code to Reuse

### 1. Auto-Detection Logic (`oldgen/src/jn/cli/cat.py`)

**Location:** Lines 31-94

**What it does:**
- `_is_url()` - Detects HTTP/FTP/S3 URLs
- `_detect_file_parser()` - Maps file extensions to JC parsers
- `_is_jc_command()` - Checks if command is in JC registry
- `_detect_source_type()` - Priority-based detection (URL > file > JC command > generic)

**Why it's valuable:**
- Core logic for automatic pipeline construction
- Well-tested priority order
- Clean function-based design (already matches next-gen philosophy!)

**Adaptation needed:**
- Change return format from `(driver, parser, args)` to plugin name
- Map extensions to plugin registry instead of drivers

**Harvest action:** ✅ Copy to `src/jn/detection.py` and adapt

---

### 2. JC Parser Integrations (`oldgen/src/jn/jcparsers/`)

**Files:**
- `tsv_s.py` - TSV streaming parser
- `psv_s.py` - Pipe-separated values
- `yaml_s.py` - YAML streaming
- `toml_s.py` - TOML streaming
- `xml_s.py` - XML streaming
- `generic_s.py` - Generic line-by-line wrapper

**Why valuable:**
- Already implement streaming NDJSON output
- Follow JC plugin conventions
- Well-tested against various inputs

**Adaptation needed:**
- Wrap each as standalone plugin with PEP 723 headers
- Add `# META:` comments for discovery
- Add `examples()` function

**Harvest action:** ✅ Convert to plugins in `plugins/` directory

---

### 3. Driver Subprocess Patterns (`oldgen/src/jn/drivers/`)

**Files:**
- `exec.py::spawn_exec()` - Safe subprocess execution
- `curl.py::spawn_curl()` - HTTP client with retries
- `file.py` - File I/O with streaming

**Why valuable:**
- Error handling done right
- Streaming support
- Security considerations (no shell injection)

**Adaptation needed:**
- Extract pure functions (no class dependencies)
- Use as library functions, not drivers

**Harvest action:** ✅ Copy patterns to `src/jn/subprocess_utils.py`

---

### 4. CSV/JSON Writers (`oldgen/src/jn/writers/`)

**Files:**
- `csv_writer.py` - NDJSON → CSV with header detection
- `json_writer.py` - NDJSON → JSON array
- `ndjson_writer.py` - Passthrough

**Why valuable:**
- Handle inconsistent keys correctly
- Efficient buffering strategies
- Good error messages

**Adaptation needed:**
- Convert to standalone plugins
- Add PEP 723 headers and metadata

**Harvest action:** ✅ Convert to plugins

---

### 5. Test Patterns (`oldgen/tests/`)

**Excellent patterns:**
- `conftest.py` - CliRunner fixture, temp file helpers
- `helpers.py` - Test data generators
- Integration tests with real subprocess execution
- Fixture-based approach (no tautological tests)

**Why valuable:**
- Already using pytest + CliRunner
- Good separation of unit vs integration
- Real-world test scenarios

**Adaptation needed:**
- Update imports for new structure
- Keep same testing philosophy

**Harvest action:** ✅ Copy test infrastructure patterns to `tests/conftest.py`

---

## Code to NOT Reuse

### ❌ Pydantic Models (`oldgen/src/jn/models/`)

**Why skip:**
- Class-based, not function-based
- Too heavy for plugin metadata
- Next-gen uses simple dicts + regex parsing

**What to do instead:** Simple dataclasses or TypedDicts if type hints needed

---

### ❌ Config System (`oldgen/src/jn/config/`)

**Why skip:**
- Import-based discovery
- Heavy catalog/mutation system
- Tied to 4-concept or Api/Filter model

**What to do instead:** Lightweight registry.json + filesystem discovery

---

### ❌ Complex CLI Structure (`oldgen/src/jn/cli/`)

**Why skip:**
- Multiple command files
- Tied to old config system
- Validation logic coupled to models

**What to do instead:** Single `cli.py` with simple Typer/Click commands

---

## Patterns to Harvest

### Pattern 1: Error Handling

**From:** `oldgen/src/jn/exceptions.py`
```python
class JnError(Exception):
    def __init__(self, context, source, code, message):
        self.context = context
        self.source = source
        self.code = code
        self.message = message
```

**Harvest:** Error structure with context + exit codes

---

### Pattern 2: Streaming Execution

**From:** `oldgen/src/jn/cli/cat.py::_execute_source()`
```python
for chunk in _execute_source(driver, parser, args):
    sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()
```

**Harvest:** Chunk-by-chunk streaming pattern

---

### Pattern 3: Test Data Generation

**From:** `oldgen/tests/helpers.py`
```python
def make_temp_csv(tmp_path, data):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text(data)
    return csv_file
```

**Harvest:** Fixture generation helpers

---

## CLI Framework Evaluation

### Current: Typer

**Used in oldgen:**
- `/oldgen/src/jn/cli/*.py`
- Heavy use of `@app.command()` decorators
- Type annotations for arguments

**Pros:**
- ✅ Great for traditional CLI apps
- ✅ Auto-generates help from docstrings
- ✅ Type safety via Pydantic

**Cons for our use case:**
- ❌ Designed for monolithic apps, not composable tools
- ❌ Adds ~2MB to installation
- ❌ Each plugin would need Typer dependency

---

### Alternative 1: Click

**What it is:** Lower-level CLI framework (Typer is built on Click)

**Pros:**
- ✅ Lighter weight than Typer
- ✅ More flexible
- ✅ Better for composable commands
- ✅ Used by major projects (Flask, pytest)

**Cons:**
- ⚠️ Less type safety
- ⚠️ More boilerplate

**Example:**
```python
import click

@click.command()
@click.argument('source')
@click.option('--parser', help='JC parser')
def cat(source, parser):
    """Output source as NDJSON."""
    pass
```

---

### Alternative 2: argparse (stdlib)

**What it is:** Python standard library

**Pros:**
- ✅ Zero dependencies
- ✅ Always available
- ✅ Lightweight
- ✅ Perfect for plugins (no external deps)

**Cons:**
- ❌ More verbose
- ❌ Less elegant API

**Example:**
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('--parser', help='JC parser')
args = parser.parse_args()
```

---

### Alternative 3: Custom Minimal Framework

**What it is:** Build our own lightweight wrapper

**Pros:**
- ✅ Exactly what we need, nothing more
- ✅ Can optimize for agent workflows
- ✅ Educational value

**Cons:**
- ❌ More maintenance
- ❌ Reinventing wheel

---

## Recommendation: Click for Core, argparse for Plugins

### For `src/jn/cli.py` (core orchestrator):

**Use Click** because:
- Lighter than Typer but still elegant
- Better for composable commands
- Standard in ecosystem (pytest, flask)
- Good documentation generation

### For `plugins/*.py` (individual tools):

**Use argparse** because:
- Zero dependencies (stdlib only)
- Plugins should be maximally independent
- Simple argument parsing is all we need
- Agents can generate argparse code easily

### Migration from Typer:

**Easy conversion:**
```python
# Old (Typer)
@app.command()
def cat(source: str, parser: str = None):
    pass

# New (Click)
@click.command()
@click.argument('source')
@click.option('--parser', default=None)
def cat(source, parser):
    pass
```

---

## Harvest Action Plan

### Phase 1: Extract Core Functions (Week 1, Days 1-2)

1. ✅ `src/jn/detection.py` - Copy auto-detection logic from cat.py
2. ✅ `src/jn/subprocess_utils.py` - Extract spawn_exec/spawn_curl patterns
3. ✅ `src/jn/streaming.py` - Extract streaming patterns

### Phase 2: Convert to Plugins (Week 1, Days 3-5)

1. ✅ `plugins/csv_reader.py` - From jcparsers/csv
2. ✅ `plugins/csv_writer.py` - From writers/csv_writer
3. ✅ `plugins/json_passthrough.py` - From writers/ndjson_writer
4. ✅ `plugins/yaml_reader.py` - From jcparsers/yaml_s
5. ✅ `plugins/xml_reader.py` - From jcparsers/xml_s
6. ✅ `plugins/toml_reader.py` - From jcparsers/toml_s

### Phase 3: Port Test Infrastructure (Week 2, Days 1-2)

1. ✅ `tests/conftest.py` - Copy CliRunner, temp file fixtures
2. ✅ `tests/helpers.py` - Copy test data generators
3. ✅ `tests/unit/test_detection.py` - Port detection tests
4. ✅ `tests/integration/test_cat.py` - Port cat tests

---

## Files Generated from Harvest

```
src/jn/
  detection.py        # From oldgen cat.py lines 31-94
  subprocess_utils.py # From oldgen drivers/*.py
  streaming.py        # Streaming patterns

plugins/
  csv_reader.py       # From oldgen jcparsers/tsv_s + csv logic
  csv_writer.py       # From oldgen writers/csv_writer
  json_passthrough.py # From oldgen writers/ndjson_writer
  yaml_reader.py      # From oldgen jcparsers/yaml_s
  xml_reader.py       # From oldgen jcparsers/xml_s
  toml_reader.py      # From oldgen jcparsers/toml_s

tests/
  conftest.py         # From oldgen tests/conftest.py
  helpers.py          # From oldgen tests/helpers.py
```

---

## Summary

**Keep:**
- ✅ Auto-detection logic (pure functions, well-designed)
- ✅ JC parser integrations (streaming, tested)
- ✅ Subprocess patterns (security, error handling)
- ✅ Writer implementations (correct buffering)
- ✅ Test infrastructure (pytest + CliRunner)

**Discard:**
- ❌ Pydantic models (too heavy)
- ❌ Config system (wrong paradigm)
- ❌ Complex CLI structure (monolithic)

**CLI Framework Choice:**
- **Core:** Click (lighter than Typer, composable)
- **Plugins:** argparse (stdlib, zero deps)

**Next Steps:**
1. Create `src/jn/detection.py` with harvested auto-detection
2. Create first plugin with argparse + PEP 723
3. Port test infrastructure
4. Build Click-based CLI
