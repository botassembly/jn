# JN Plugin Specification v1.0

**Date:** 2025-11-11
**Status:** Draft
**Purpose:** Formal definition of what constitutes a valid JN plugin

## Overview

This document formally defines the structure, components, and requirements for JN plugins. It serves as the authoritative specification for:
- Plugin developers (what to implement)
- Plugin checker tool (what to validate)
- Framework code (what to expect)

**Design Philosophy:**
- **Duck typing:** Plugins are identified by functions they expose, not inheritance
- **Minimal requirements:** Only define what you need for your plugin type
- **Standard Python:** Use PEP 723, type hints, docstrings
- **Self-contained:** Each plugin is independently executable

---

## Plugin Taxonomy

JN plugins are categorized by **capability** (which functions they expose), not by explicit type declaration.

### 1. Format Plugin

**Purpose:** Convert between external formats (CSV, JSON, YAML, etc.) and NDJSON

**Required Functions:**
- `reads()` - Parse format from stdin → yield NDJSON records
- `writes()` - Read NDJSON from stdin → write format to stdout

**OR at minimum one of:**
- Read-only format plugin (only `reads()`)
- Write-only format plugin (only `writes()`)

**Examples:** csv_.py, json_.py, yaml_.py, toml_.py, markdown_.py

**Detection:** Has `reads()` and/or `writes()` function + matches file extensions in [tool.jn]

---

### 2. Protocol Plugin

**Purpose:** Fetch data from remote sources (HTTP, S3, databases, APIs)

**Required Functions:**
- `reads()` - Fetch from remote source → yield NDJSON records

**Optional Functions:**
- `writes()` - Push NDJSON to remote destination (rare)

**Examples:** http_.py, s3.py (planned), sql.py (planned)

**Detection:** Has `reads()` function + matches URL patterns (^https?://, ^s3://, etc.)

---

### 3. Filter Plugin

**Purpose:** Transform NDJSON streams (wraps external tools like jq, SQLite, etc.)

**Required:** None - may have no reads/writes functions at all

**Pattern:** Often just wraps subprocess call, inherits stdin/stdout

**Examples:** jq_.py (wraps jq command-line tool)

**Detection:** No reads/writes, invoked explicitly by name (not file matching)

---

### 4. Display Plugin

**Purpose:** Format NDJSON for human viewing (tables, charts, pretty-print)

**Required Functions:**
- `writes()` - Read NDJSON → write human-readable format

**No `reads()`** - Display is output-only

**Examples:** tabulate_.py (pretty tables)

**Detection:** Has `writes()` only + matches stdout/display patterns (-, stdout, *.table)

---

### 5. Shell Plugin (Planned)

**Purpose:** Wrap shell commands and parse output to NDJSON

**Required Functions:**
- `reads()` - Execute shell command → parse output → yield NDJSON

**Examples:** ls.py, ps.py, df.py (from roadmap)

**Detection:** Has `reads()` + no file extension matches (invoked by command name)

---

## Self-Contained Protocol Plugins

**Status:** ✅ Implemented pattern for DuckDB, recommended for all protocol plugins
**Date:** 2025-11-22

### Architecture Pattern

Protocol plugins that manage profiles (DuckDB, PostgreSQL, MySQL, etc.) should be **self-contained**: they vendor all profile-related logic and expose it via `--mode` flags.

### Problem: Framework Coupling

**Before (coupled):**
```
Framework (profiles/service.py)
├── _parse_duckdb_profile()    # DuckDB-specific logic (~200 lines)
├── _parse_postgres_profile()  # PostgreSQL-specific logic
└── list_all_profiles()        # Framework scans filesystem

Plugin (duckdb_.py)
└── reads()                    # Just executes queries
```

**Issues:**
- Framework contains plugin-specific code
- Can't add new database plugins without modifying framework
- Plugin not independently testable
- Violates separation of concerns

### Solution: Self-Contained Plugins

**After (self-contained):**
```
Framework (profiles/service.py)
└── list_all_profiles()        # Calls plugins, aggregates results

Plugin (duckdb_.py)
├── inspect_profiles()         # Scans filesystem for profiles
├── _load_profile()            # Parses profile metadata
├── _get_profile_paths()       # Resolves profile directories
└── reads()                    # Executes queries
```

**Benefits:**
✅ Framework is generic (no plugin-specific code)
✅ Plugin is standalone (testable via `--mode` flags)
✅ Easy to add new database plugins (copy pattern)
✅ Plugin owns its own profile discovery logic

### Implementation Pattern

#### Plugin Implements `inspect_profiles()`

```python
def inspect_profiles() -> Iterator[dict]:
    """List all available profiles for this plugin.

    Called by framework with --mode inspect-profiles.
    Returns ProfileInfo-compatible NDJSON records.
    """
    for profile_root in _get_profile_paths():
        for namespace_dir in sorted(profile_root.iterdir()):
            # Plugin-specific logic to discover profiles
            for profile_file in namespace_dir.glob("*.sql"):
                # Parse metadata from file
                yield {
                    "reference": f"@{namespace}/{name}",
                    "type": "duckdb",
                    "namespace": namespace,
                    "name": name,
                    "path": str(profile_file),
                    "description": description,
                    "params": params,
                    "examples": []
                }
```

#### Plugin CLI Supports `--mode inspect-profiles`

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["read", "write", "inspect-profiles", "inspect-container"])
    parser.add_argument("address", nargs="?")

    args = parser.parse_args()

    if args.mode == "inspect-profiles":
        # Discovery mode
        for profile in inspect_profiles():
            print(json.dumps(profile))
    elif args.mode == "read":
        # Execution mode
        for record in reads(config_from_address(args.address)):
            print(json.dumps(record))
```

#### Framework Calls Plugin Subprocess

```python
# Framework code: profiles/service.py
def list_all_profiles(discovered_plugins: Optional[Dict] = None) -> List[ProfileInfo]:
    """Scan filesystem and call plugins to discover profiles."""
    profiles = []

    # ... scan filesystem for HTTP, JQ, MCP profiles ...

    # Call plugins with --mode inspect-profiles
    if discovered_plugins:
        for plugin in discovered_plugins.values():
            try:
                # Use uv run --script to ensure PEP 723 dependencies available
                process = subprocess.Popen(
                    ["uv", "run", "--script", str(plugin.path), "--mode", "inspect-profiles"],
                    stdout=subprocess.PIPE,
                    text=True
                )
                stdout, _ = process.communicate(timeout=5)

                if process.returncode == 0 and stdout.strip():
                    for line in stdout.strip().split("\n"):
                        data = json.loads(line)
                        profiles.append(ProfileInfo(**data))
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

    return profiles
```

### Why Use `uv run --script`?

**Critical:** Framework must call plugin via `uv run --script`, not `sys.executable`.

**Reason:** PEP 723 dependencies need to be installed.

```python
# ❌ WRONG - Bypasses PEP 723 dependency installation
subprocess.Popen([sys.executable, str(plugin.path), "--mode", "inspect-profiles"])
# Plugin fails with: ImportError: No module named 'duckdb'

# ✅ CORRECT - Installs PEP 723 dependencies first
subprocess.Popen(["uv", "run", "--script", str(plugin.path), "--mode", "inspect-profiles"])
# UV reads # dependencies = ["duckdb>=0.9.0"] and installs before running
```

### Communication Protocol

**Framework → Plugin:**
```bash
uv run --script duckdb_.py --mode inspect-profiles
```

**Plugin → Framework (NDJSON):**
```json
{"reference": "@analytics/sales", "type": "duckdb", "namespace": "analytics", "name": "sales", "path": "/path/to/sales.sql", "description": "Sales summary", "params": [], "examples": []}
{"reference": "@analytics/revenue", "type": "duckdb", "namespace": "analytics", "name": "revenue", "path": "/path/to/revenue.sql", "description": "Revenue report", "params": ["year"], "examples": []}
```

### Vendor Profile Logic

Self-contained plugins **vendor** profile resolution logic from framework:

**Pattern:**
```python
def _get_profile_paths() -> list[Path]:
    """Get profile search paths in priority order.

    Vendored from framework to make plugin self-contained.
    """
    paths = []

    # 1. Project profiles (highest priority)
    project_dir = Path.cwd() / ".jn" / "profiles" / "duckdb"
    if project_dir.exists():
        paths.append(project_dir)

    # 2. User profiles
    jn_home = os.getenv("JN_HOME")
    if jn_home:
        user_dir = Path(jn_home) / "profiles" / "duckdb"
    else:
        user_dir = Path.home() / ".jn" / "profiles" / "duckdb"

    if user_dir.exists():
        paths.append(user_dir)

    return paths
```

**Why vendor?** Plugin must work standalone without importing framework code.

### Profile Metadata in PEP 723

Self-contained plugins declare `role = "protocol"` in PEP 723:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["duckdb>=0.9.0"]
# [tool.jn]
# matches = ["^@.*", "^duckdb://.*"]
# role = "protocol"
# ///
```

**Fields:**
- `matches` - Address patterns this plugin handles
- `role = "protocol"` - Identifies as protocol plugin (not format/filter)

### Testing Self-Contained Plugins

**Test discovery independently:**
```bash
# Call plugin directly
uv run --script jn_home/plugins/databases/duckdb_.py --mode inspect-profiles

# Should output NDJSON
{"reference": "@test/query1", ...}
{"reference": "@test/query2", ...}
```

**Test execution independently:**
```bash
# Call plugin with profile reference
echo '{}' | uv run --script jn_home/plugins/databases/duckdb_.py --mode read "@test/query1"

# Should output query results as NDJSON
{"id": 1, "name": "Alice"}
{"id": 2, "name": "Bob"}
```

**No framework required!** Plugin works standalone.

### When to Use This Pattern

**✅ Use self-contained pattern for:**
- Database plugins (DuckDB, PostgreSQL, MySQL, SQLite)
- Any plugin with complex profile discovery logic
- Plugins where profile structure varies by use case
- Plugins that need to parse custom file formats (`.sql`, `.graphql`, etc.)

**❌ Don't need self-contained pattern for:**
- HTTP plugin (framework scans JSON files efficiently)
- MCP plugin (framework scans JSON files efficiently)
- JQ plugin (framework scans `.jq` files efficiently)
- Format plugins (no profiles)

**Rule of thumb:** If profile discovery requires plugin-specific parsing logic, make it self-contained.

### Migration from Coupled to Self-Contained

**Steps:**

1. **Move parsing logic to plugin**
   - Copy `_parse_X_profile()` from framework to plugin
   - Rename to `_load_profile()` in plugin

2. **Add `inspect_profiles()` function**
   - Implement profile scanning
   - Return ProfileInfo-compatible dicts

3. **Add `--mode inspect-profiles` to CLI**
   - Handle in `if __name__ == "__main__"`
   - Print NDJSON to stdout

4. **Remove framework code**
   - Delete `_parse_X_profile()` from `profiles/service.py`
   - Remove plugin-specific scanning logic

5. **Update framework to call plugin**
   - Add plugin subprocess call in `list_all_profiles()`
   - Parse NDJSON output

6. **Test independently**
   - `uv run --script plugin.py --mode inspect-profiles`
   - Verify output format matches ProfileInfo

**Example:** See `spec/done/duckdb-plugin.md` for complete migration.

### Summary

Self-contained protocol plugins:

✅ **Vendor all logic** - Profile discovery, parsing, validation
✅ **Framework-independent** - Testable via `--mode` flags
✅ **Discoverable** - Implement `--mode inspect-profiles`
✅ **PEP 723 dependencies** - Use `uv run --script` for deps
✅ **NDJSON communication** - Stream ProfileInfo records
✅ **Standalone execution** - No framework imports required

**Result:** Clean separation. Framework routes, plugin executes and discovers.

---

## Plugin Components

### Required Components (All Plugins)

#### 1. UV Shebang (Line 1)

```python
#!/usr/bin/env -S uv run --script
```

**Why:** Makes plugin directly executable with UV managing dependencies

**Checker Rule:** MUST be exactly this line (no variations)

---

#### 2. Module Docstring (Lines 2-3)

```python
"""Short description of what this plugin does."""
```

**Why:** Self-documenting, shown in `jn plugin info <name>`

**Checker Rule:** MUST exist, SHOULD be 1-3 sentences

---

#### 3. PEP 723 Script Block (Lines 4-13)

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests>=2.31.0",
#   "beautifulsoup4>=4.12.0",
# ]
# [tool.jn]
# matches = [
#   "^https?://.*",
#   ".*\\.html$"
# ]
# ///
```

**Required Fields:**
- `requires-python` - Minimum Python version
- `dependencies` - List of PyPI packages (empty list `[]` is valid)
- `[tool.jn]` section - JN-specific metadata

**[tool.jn] Required Fields:**
- `matches` - List of regex patterns for file/URL matching

**[tool.jn] Optional Fields:**
- `description` - Long-form description
- `version` - Plugin version
- `author` - Plugin author

**Checker Rules:**
- MUST have PEP 723 block
- MUST declare all non-stdlib imports in dependencies
- `matches` MAY be empty list (filters invoked by name)

---

#### 4. if __name__ == '__main__' Block

```python
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="...")
    parser.add_argument("--mode", choices=["read", "write"], help="...")
    # ... plugin-specific args ...

    args = parser.parse_args()

    if args.mode == "read":
        for record in reads(...):
            print(json.dumps(record), flush=True)  # MUST have flush=True
    elif args.mode == "write":
        writes(...)
```

**Requirements:**
- MUST accept `--mode` argument (read, write, or both depending on plugin)
- MUST call plugin functions (reads/writes)
- MUST use `flush=True` when printing NDJSON (prevents buffering)
- MAY accept additional plugin-specific arguments

**Checker Rules:**
- MUST have if __name__ == '__main__' block
- MUST have argparse CLI interface
- MUST have flush=True in print(json.dumps(...))

---

### Plugin Interface Functions

#### reads() Function

**Signature (Legacy - Config Dict):**
```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read <format> from stdin, yield NDJSON records.

    Args:
        config: Configuration dict with plugin-specific options
            - option1: Description (default: value)
            - option2: Description (default: value)

    Yields:
        Dict per record/row/document
    """
    config = config or {}
    option1 = config.get('option1', default_value)

    # Implementation
    for record in source:
        yield record
```

**Signature (Modern - Direct Args):**
```python
def reads(
    url: str,
    method: str = "GET",
    headers: dict = None,
    timeout: int = 30
) -> Iterator[dict]:
    """Read data from URL, yield NDJSON records.

    Args:
        url: The URL to fetch (required)
        method: HTTP method (default: 'GET')
        headers: HTTP headers dict (default: None)
        timeout: Request timeout in seconds (default: 30)

    Yields:
        Dict per record from the response
    """
    headers = headers or {}

    # Implementation
    for record in source:
        yield record
```

**Requirements:**
- MUST yield dict objects (NDJSON records)
- SHOULD have type hints
- MUST have docstring explaining args and behavior
- SHOULD process streaming (not buffer entire input if possible)
- SHOULD yield error records instead of raising exceptions during iteration

**Error Handling:**
```python
# GOOD: Yield error records (errors as data)
def reads(url: str) -> Iterator[dict]:
    try:
        response = requests.get(url)
    except requests.RequestException as e:
        yield {"_error": True, "type": "request_failed", "message": str(e)}
        return

    for record in parse(response):
        yield record

# BAD: Raising exceptions during iteration (breaks pipeline)
def reads(url: str) -> Iterator[dict]:
    response = requests.get(url)  # Raises exception
    for record in parse(response):
        if error:
            raise ValueError("Bad data")  # Breaks pipeline
        yield record
```

**Pattern:** Validation errors at start (before yielding) can raise. Data errors should yield error records.

---

#### writes() Function

**Signature (Legacy - Config Dict):**
```python
def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write <format> to stdout.

    Args:
        config: Configuration dict with plugin-specific options
            - option1: Description (default: value)
            - option2: Description (default: value)
    """
    config = config or {}
    option1 = config.get('option1', default_value)

    # Read all records (if format requires knowing structure upfront)
    records = []
    for line in sys.stdin:
        records.append(json.loads(line))

    # Write output
    write_format(records)
```

**Signature (Modern - Direct Args):**
```python
def writes(
    output_format: str = "array",
    indent: int = None,
    sort_keys: bool = False
) -> None:
    """Read NDJSON from stdin, write JSON to stdout.

    Args:
        output_format: Output format ('array', 'ndjson', 'object')
        indent: Indentation spaces (default: None for compact)
        sort_keys: Sort keys alphabetically (default: False)
    """
    records = []
    for line in sys.stdin:
        records.append(json.loads(line))

    # Write output
    output = format_output(records, output_format, indent, sort_keys)
    print(output)
```

**Requirements:**
- MUST read NDJSON from sys.stdin
- MUST write to sys.stdout (or sys.stderr for errors)
- SHOULD have type hints
- MUST have docstring
- MAY buffer records (some formats like CSV need all records for headers)

**Streaming vs Buffering:**
- **Streaming preferred:** Process line-by-line when possible
- **Buffering acceptable:** When format requires (CSV headers, JSON arrays)

---

### Helper Functions

#### Public Helpers

**Allowed:** Utility functions used by plugin, potentially useful to tests

```python
def error_record(error_type: str, message: str, **extra) -> dict:
    """Create standardized error record.

    Args:
        error_type: Error category (e.g., 'http_error', 'parse_error')
        message: Human-readable error message
        **extra: Additional context fields

    Returns:
        Dict with _error flag and details
    """
    return {"_error": True, "type": error_type, "message": message, **extra}
```

**Rules:**
- MAY have public helper functions
- SHOULD have docstrings
- SHOULD have type hints
- Common pattern: `error_record()` for error standardization

---

#### Private Helpers

**Allowed:** Internal implementation details

```python
def _parse_json(response: requests.Response, url: str) -> Iterator[dict]:
    """Parse JSON response and yield records (private helper)."""
    try:
        data = response.json()
    except json.JSONDecodeError as e:
        yield error_record("json_decode_error", str(e), url=url)
        return

    # ... parsing logic ...
```

**Rules:**
- MUST start with underscore `_` to indicate private
- SHOULD be simple (< 30 lines recommended)
- SHOULD have docstring if complex
- MAY omit docstring if trivial (<10 lines, obvious purpose)

**Checker Rules:**
- Private functions MUST start with `_`
- Warn if private function >50 lines (should be split)
- Warn if >5 private functions (plugin too complex)

---

### Optional Components

#### Test Function (Recommended)

```python
def test() -> None:
    """Self-test with real data (no mocks).

    Tests plugin functions with actual sample data to verify behavior.
    Framework can call this for integration testing.
    """
    # Test reads()
    sample_input = io.StringIO("col1,col2\nval1,val2\n")
    sys.stdin = sample_input
    records = list(reads())
    assert len(records) == 1
    assert records[0] == {"col1": "val1", "col2": "val2"}

    # Test writes()
    # ...
```

**Rules:**
- SHOULD have test() function (not required but recommended)
- Tests MAY use simple assertions (no pytest required)
- Tests SHOULD use real data (not mocks)

---

## Forbidden Patterns

### 1. Framework Imports

**❌ FORBIDDEN:**
```python
from jn.core import pipeline  # NO
from jn.plugins import registry  # NO
import jn  # NO
```

**Why:** Plugins must be self-contained, framework-independent

**Checker Rule:** ERROR if any `import jn` or `from jn` found

---

### 2. Global State / Mutable Globals

**❌ FORBIDDEN:**
```python
# NO global mutable state
CACHE = {}  # Shared across invocations in long-running process

def reads(config):
    global CACHE  # NO
    if url in CACHE:
        return CACHE[url]
```

**Why:** Plugins run as subprocesses, global state is anti-pattern

**✅ ALLOWED:**
```python
# Constants are fine
DEFAULT_TIMEOUT = 30
STDLIB_MODULES = frozenset(['sys', 'os', 'json'])
```

**Checker Rule:** WARN on global variables (except constants)

---

### 3. Subprocess Buffering Anti-Patterns

**❌ FORBIDDEN:**
```python
# From backpressure.md violations
result = subprocess.run(cmd, capture_output=True)  # Buffers everything
all_data = process.stdout.read()  # Reads all before processing
```

**Why:** Defeats streaming, breaks backpressure

**See:** spec/arch/backpressure.md, plugin-checker-investigation.md

---

### 4. Uncontrolled Recursion

**❌ FORBIDDEN:**
```python
def reads(config):
    # No max depth check
    yield from reads(config)  # Infinite recursion
```

**Checker Rule:** WARN on recursive calls without obvious termination

---

### 5. Sys.exit() in Plugin Functions

**❌ FORBIDDEN:**
```python
def reads(url: str):
    if not url:
        sys.exit(1)  # NO - exits entire process
```

**✅ ALLOWED:**
```python
# In CLI block only
if __name__ == "__main__":
    if not args.url:
        parser.error("URL required")  # OK
        sys.exit(1)  # OK here
```

**Checker Rule:** ERROR if sys.exit() found in reads/writes functions

---

## Component Matrix

| Component | Format | Protocol | Filter | Display | Shell |
|-----------|--------|----------|--------|---------|-------|
| **UV Shebang** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Module Docstring** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **PEP 723 Block** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **[tool.jn] matches** | ✅ Required (non-empty) | ✅ Required (non-empty) | ⚠️ Optional (may be empty) | ✅ Required (non-empty) | ⚠️ Optional (by name) |
| **reads() function** | ✅ Required (or writes) | ✅ Required | ❌ Optional | ❌ Not used | ✅ Required |
| **writes() function** | ✅ Required (or reads) | ⚠️ Optional (rare) | ❌ Optional | ✅ Required | ❌ Not used |
| **if __name__** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Helper functions** | ⚠️ Optional | ⚠️ Optional | ⚠️ Optional | ⚠️ Optional | ⚠️ Optional |
| **test() function** | 💡 Recommended | 💡 Recommended | 💡 Recommended | 💡 Recommended | 💡 Recommended |

**Legend:**
- ✅ Required - Must have
- ⚠️ Optional - May have
- ❌ Not used - Typically not present
- 💡 Recommended - Should have

---

## Validation Rules for Checker

### Phase 1: Critical (ERROR - Block PRs)

1. **Missing UV shebang** - First line must be `#!/usr/bin/env -S uv run --script`
2. **Missing PEP 723 block** - Must have valid `# /// script` block
3. **Undeclared dependencies** - All imports must be in dependencies list
4. **Missing flush=True** - print(json.dumps(...)) must have flush=True
5. **Framework imports** - No `import jn` or `from jn`
6. **sys.exit() in plugin functions** - Only allowed in if __name__ block
7. **Subprocess anti-patterns** - From backpressure.md checks

### Phase 2: Important (WARNING - Should fix)

8. **Missing module docstring** - Module should have docstring
9. **Missing function docstrings** - reads/writes should have docstrings
10. **No type hints** - Functions should have type hints
11. **Missing [tool.jn] matches** - Format/Protocol plugins need matches
12. **Config dict pattern** - Prefer direct args over config dict (legacy pattern)
13. **Too many private functions** - >5 suggests plugin too complex
14. **Large private function** - >50 lines suggests should be split

### Phase 3: Code Quality (INFO - Nice to have)

15. **Missing test() function** - Recommended for self-testing
16. **Inconsistent import order** - stdlib, third-party, local
17. **Long reads/writes** - >100 lines suggests split into helpers
18. **Global mutable variables** - Use constants only

---

## Examples

### Minimal Format Plugin

```python
#!/usr/bin/env -S uv run --script
"""Parse JSON files and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.json$"]
# ///

import json
import sys
from typing import Iterator

def reads() -> Iterator[dict]:
    """Read JSON from stdin, yield NDJSON records."""
    data = json.loads(sys.stdin.read())
    if isinstance(data, list):
        yield from data
    else:
        yield data

def writes() -> None:
    """Read NDJSON from stdin, write JSON array to stdout."""
    records = [json.loads(line) for line in sys.stdin if line.strip()]
    print(json.dumps(records, indent=2))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["read", "write"], required=True)
    args = parser.parse_args()

    if args.mode == "read":
        for record in reads():
            print(json.dumps(record), flush=True)
    else:
        writes()
```

### Modern Protocol Plugin (Direct Args)

```python
#!/usr/bin/env -S uv run --script
"""Fetch data from HTTP/HTTPS endpoints."""
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.31.0"]
# [tool.jn]
# matches = ["^https?://.*"]
# ///

import json
import sys
from typing import Iterator

import requests

def error_record(error_type: str, message: str, **extra) -> dict:
    """Create standardized error record."""
    return {"_error": True, "type": error_type, "message": message, **extra}

def reads(url: str, method: str = "GET", timeout: int = 30) -> Iterator[dict]:
    """Fetch data from URL, yield NDJSON records.

    Args:
        url: The URL to fetch (required)
        method: HTTP method (default: 'GET')
        timeout: Request timeout in seconds (default: 30)

    Yields:
        Dict records from the response
    """
    try:
        response = requests.request(method, url, timeout=timeout, stream=True)
        response.raise_for_status()
    except requests.RequestException as e:
        yield error_record("request_failed", str(e), url=url)
        return

    # Parse JSON response
    try:
        data = response.json()
    except json.JSONDecodeError as e:
        yield error_record("json_decode_error", str(e), url=url)
        return

    if isinstance(data, list):
        yield from data
    else:
        yield data

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HTTP protocol plugin")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--mode", choices=["read"], required=True)
    parser.add_argument("--method", default="GET")
    parser.add_argument("--timeout", type=int, default=30)

    args = parser.parse_args()

    for record in reads(url=args.url, method=args.method, timeout=args.timeout):
        print(json.dumps(record), flush=True)
```

### Filter Plugin (Subprocess Wrapper)

```python
#!/usr/bin/env -S uv run --script
"""Filter NDJSON using jq expressions."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = []  # Invoked by name, not file matching
# ///

import subprocess
import sys

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "."

    # Use Popen (not run) for streaming, inherit stdin/stdout
    proc = subprocess.Popen(
        ["jq", "-c", query],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    sys.exit(proc.wait())
```

---

## Migration Guide

### Legacy → Modern

**Old pattern (config dict):**
```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    config = config or {}
    delimiter = config.get('delimiter', ',')
    skip_rows = config.get('skip_rows', 0)
    # ...
```

**New pattern (direct args):**
```python
def reads(delimiter: str = ',', skip_rows: int = 0) -> Iterator[dict]:
    """Read CSV from stdin, yield NDJSON records.

    Args:
        delimiter: Field delimiter (default: ',')
        skip_rows: Number of rows to skip (default: 0)
    """
    # ...
```

**Benefits:**
- Type safety (mypy can check)
- IDE autocomplete works
- Clearer signature
- Easier to validate

**Migration:** Both patterns are currently allowed, but direct args are preferred for new plugins.

---

## Summary

**A valid JN plugin MUST have:**
1. UV shebang (line 1)
2. Module docstring
3. PEP 723 block with dependencies
4. [tool.jn] section with matches (may be empty for filters)
5. At least one of: reads(), writes(), or subprocess wrapper
6. if __name__ == '__main__' CLI interface
7. flush=True in NDJSON print statements
8. No framework imports (jn.*)

**A good JN plugin SHOULD have:**
- Type hints on functions
- Docstrings on all public functions
- Direct function args (not config dict)
- error_record() helper for error handling
- test() function for self-validation
- Private helpers (prefixed with _) for complex logic

**Plugin types are duck-typed:**
- Has reads/writes + matches files → Format plugin
- Has reads + matches URLs → Protocol plugin
- Has writes only → Display plugin
- Has neither → Filter plugin (subprocess wrapper)

This specification enables the checker tool to validate plugins automatically and guides developers in creating well-structured, maintainable plugins.
