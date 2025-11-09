# Code Quality Analysis - Branch: claude/refactor-registry-architecture

## Overview
This analysis covers 47 files changed across CLI commands, models, config management, and writers. The refactor simplifies the registry architecture from complex pipelines/converters to a simpler APIs + Filters model. Total scope: ~1095 lines in key files.

---

## 1. CODE ORGANIZATION & ARCHITECTURE

### 1.1 Critical Issues: Massive Code Duplication

**Finding**: `api.py` and `filter.py` are nearly identical (244 lines vs 182 lines)

**Details**:
- Both files have identical callback structure (`default()` function)
- Both have identical command pattern: `add()`, `show()`, `update()`, `rm()` with nearly identical logic
- Both have identical confirmation flows for replacement with before/after diffs
- Same error handling patterns repeated verbatim

**Example - Identical structure**:
```python
# api.py (lines 99-149)
existing = config.get_api(name)
if existing:
    if skip_if_exists:
        typer.echo(f"API '{name}' already exists, skipping.")
        return
    
    typer.echo(f"API '{name}' already exists.", err=True)
    typer.echo()
    typer.echo("BEFORE:")
    typer.echo(json.dumps(existing.model_dump(exclude_none=True), indent=2))
    # ... confirmation logic

# filter.py (lines 57-95) - Identical pattern with s/API/Filter/g
```

**Impact**: 
- Violates DRY principle
- Maintenance burden doubled
- Changes needed in two places
- Code review complexity increased

**Recommendation**: 
Extract a generic registry command handler or use a factory pattern to create both CLI apps.

### 1.2 Inconsistent Module Organization

**Finding**: Writers are function-based, not class-based

**Files Affected**: 
- `/home/user/jn/src/jn/writers/csv_writer.py` (68 lines)
- `/home/user/jn/src/jn/writers/json_writer.py` (42 lines)
- `/home/user/jn/src/jn/writers/ndjson_writer.py` (34 lines)

**Issue**: Three separate modules doing similar work (converting NDJSON to formats) with no shared base abstraction.

**Better approach**: 
```python
class Writer(ABC):
    @abstractmethod
    def write(self, records: Iterator[Dict], output: Path | None): ...

class CSVWriter(Writer): ...
class JSONWriter(Writer): ...
class NDJSONWriter(Writer): ...

# Then dispatch via: WRITERS[format] = Writer instance
```

### 1.3 Config Module Architecture is Sound

**Positive**: The separation of `catalog.py` (read), `mutate.py` (write), and `core.py` (state) is clean.

---

## 2. ERROR HANDLING PATTERNS

### 2.1 Inconsistent Error Handling Strategy

**Problem 1: Union Return Types Used Inconsistently**

`mutate.py` returns `Api | Error` and `Filter | Error`:
```python
# mutate.py, lines 48, 110
def add_api(...) -> Api | Error:
    if config_obj.has_api(name):
        return Error(message=f"API '{name}' already exists")
    ...
    return api

def add_filter(...) -> Filter | Error:
    if config_obj.has_filter(name):
        return Error(message=f"Filter '{name}' already exists")
```

But CLI commands (api.py, filter.py) handle errors inconsistently:

```python
# api.py, lines 99-105
existing = config.get_api(name)
if existing:
    # ... show before/after
    # Manual removal: cfg.apis = [a for a in cfg.apis if a.name != name]
    config.persist(cfg)

# Then call add_api which ALSO checks if exists (redundant!)
result = config.add_api(...)
if isinstance(result, Error):
    typer.echo(f"Error: {result.message}", err=True)
    raise typer.Exit(1)
```

**Problem 2: Exception Handling is Inconsistent**

`put.py` has three different error handling approaches:
```python
# Line 54-61: Specific JSONDecodeError
try:
    yield json.loads(line)
except json.JSONDecodeError as e:
    typer.echo(f"Error: Invalid JSON...", err=True)
    raise typer.Exit(1)

# Line 177-179: Broad Exception catch-all
try:
    if format == "csv": ...
except Exception as e:
    typer.echo(f"Error writing output: {e}", err=True)
    raise typer.Exit(1)

# run.py Line 59: CalledProcessError only
except subprocess.CalledProcessError as e:
    typer.echo(f"Error executing filter: {e.stderr.decode()}", err=True)
    raise typer.Exit(e.returncode)
```

**Problem 3: Stderr vs Typer Logging**

`put.py` uses inconsistent signaling:
```python
# Line 182 - Success info on stderr (wrong)
typer.echo(f"Wrote {output_path}", err=True)
```
Success messages should go to stdout, not stderr.

**Recommendation**:
1. Pick Union return type OR exceptions, not both
2. Create exception hierarchy: `RegistryError(Exception)` with subclasses
3. Centralize error formatting
4. Consistent stderr/stdout usage

### 2.2 Missing Error Context

`catalog.py` provides no error information:
```python
# Line 38-39
def _collection(config_obj: Config, kind: CollectionName) -> Sequence[_Item]:
    return getattr(config_obj, kind)
```
If kind is invalid, `getattr` will raise `AttributeError` - no validation.

`run.py` line 60 doesn't preserve stderr:
```python
except subprocess.CalledProcessError as e:
    typer.echo(f"Error executing filter: {e.stderr.decode()}", err=True)
    # e.stderr is None by default! Need stderr=subprocess.PIPE in run()
```

---

## 3. CODE DUPLICATION

### 3.1 Removal Pattern Duplicated (3 times)

**Locations**:
- `api.py`, lines 240-242
- `filter.py`, lines 178-180
- Both use identical pattern

```python
cfg = config.require().model_copy(deep=True)
cfg.apis = [a for a in cfg.apis if a.name != name]
config.persist(cfg)
```

**Better**: Extract to `config.remove_item(kind, name)`

### 3.2 Replacement Preview Pattern (2 times)

**Locations**: `api.py` lines 105-143 and `filter.py` lines 63-84

Both show BEFORE/AFTER confirmation identically:
```python
typer.echo(f"{item} '{name}' already exists.", err=True)
typer.echo()
typer.echo("BEFORE:")
typer.echo(json.dumps(existing.model_dump(exclude_none=True), indent=2))
typer.echo()
typer.echo("AFTER:")
typer.echo(json.dumps(new_item.model_dump(exclude_none=True), indent=2))
typer.echo()
if not yes:
    confirm = typer.confirm(f"Replace existing {item}?")
    if not confirm:
        typer.echo("Cancelled.")
        raise typer.Exit(0)
```

**Better**: Extract to `show_replacement_prompt(existing, new, item_type, yes) -> bool`

### 3.3 CSV Format Variants (3 code paths)

**Location**: `put.py`, lines 137-160

```python
if format == "csv":
    write_csv(records, output_path, delimiter=delimiter, ...)
elif format == "tsv":
    write_csv(records, output_path, delimiter="\t", ...)  # Duplicated call
elif format == "psv":
    write_csv(records, output_path, delimiter="|", ...)   # Duplicated call
```

**Better**:
```python
DELIMITERS = {"csv": ",", "tsv": "\t", "psv": "|"}
if format in DELIMITERS:
    write_csv(records, output_path, delimiter=DELIMITERS[format], ...)
```

---

## 4. COMPLEX FUNCTIONS NEEDING SIMPLIFICATION

### 4.1 `api.add()` is Too Complex (76 parameters, many nested conditionals)

**Location**: `api.py`, lines 29-176

**Complexity Issues**:
1. 15 optional parameters for adding an API (lines 31-75)
2. Nested header parsing logic (lines 86-96)
3. Manual model construction for preview (lines 114-133)
4. Pre-removal logic before calling `add_api` (lines 146-148)
5. After-call error checking and output (lines 163-175)

**Functions are doing too much**:
- Parameter validation
- Header parsing
- Confirmation UI
- Error handling
- Post-creation output

**Recommendation**: Break into helper functions:
```python
def _parse_headers(header_list: List[str]) -> Dict[str, str]:
    """Parse KEY:VALUE format headers."""
    
def _show_replacement_confirm(existing: Api, new_api: Api, yes: bool) -> bool:
    """Show before/after and get confirmation."""

@app.command()
def add(name: str, ..., yes: bool = False, jn: ConfigPathType = ConfigPath):
    config.set_config_path(jn)
    headers = _parse_headers(header) if header else {}
    existing = config.get_api(name)
    
    if existing and not (_show_replacement_confirm(existing, new_api, yes)):
        raise typer.Exit(0)
    
    result = config.add_api(...)  # Single responsibility
    # Handle result...
```

### 4.2 CSV Writer Buffers All Records Unnecessarily

**Location**: `csv_writer.py`, lines 31-50

```python
# Line 31-32: Collects ALL records in memory
records_list = list(records)
if not records_list:
    # ...special case handling...

# Lines 44-50: Iterates again to find all unique keys
for record in records_list:
    for key in record:
        if key not in seen:
            all_keys.append(key)
```

**Problems**:
1. Breaks streaming advantage (entire file in memory)
2. Two iterations over data
3. Special case for empty input (lines 34-41)

**Better approach**: Stream and discover columns on-the-fly, or document that CSV requires buffering.

### 4.3 `put()` Function Has Too Many Concerns

**Location**: `put.py`, lines 65-182

**Responsibilities**:
1. Argument validation (lines 110-126)
2. Format detection (lines 129-130)
3. Format-specific writing (lines 137-175)
4. Exception handling (lines 177-179)
5. User feedback (line 182)

**Better structure**:
```python
@app.command()
def put(output_file: str, format: Optional[str], ...) -> None:
    config_path = _validate_output_file(output_file, overwrite, append)
    fmt = format or _detect_format(output_file)
    records = read_ndjson_from_stdin()
    
    writer = _get_writer(fmt, config_path, ...)
    writer.write(records)
    
    typer.echo(f"Wrote {config_path}")
```

---

## 5. MISSING TYPE ANNOTATIONS

### 5.1 Type Ignores in api.py

**Locations**: Lines 119, 127, 152, 154

```python
auth = AuthConfig(
    type=auth_type,  # type: ignore  <- BAD
    token=token,
)
```

**Issue**: `auth_type` is `Optional[str]` but `AuthConfig.type` expects `Literal["bearer", ...]`

**Root cause**: Typer options are strings; need validation

**Better fix**:
```python
from typing import Literal

auth_types = Literal["bearer", "basic", "oauth2", "api_key"]

def _validate_auth_type(auth_type: str | None) -> auth_types | None:
    if auth_type and auth_type not in ("bearer", "basic", "oauth2", "api_key"):
        raise ValueError(f"Invalid auth type: {auth_type}")
    return auth_type  # type: ignore only here

# Then in add():
auth = AuthConfig(
    type=_validate_auth_type(auth_type),  # No type: ignore needed
    token=token,
)
```

### 5.2 Missing Return Type on get_item()

**Location**: `catalog.py`, lines 96-103

```python
def get_item(
    name: str,
    kind: CollectionName,
    path: Optional[Path | str] = None,
):  # Missing return type!
    """Get an item by name from the requested collection."""
    return _get_by_name(name, kind, path)
```

**Should be**: `-> Optional[_Item]:`

### 5.3 Overly Generic Types in Writers

**Location**: `csv_writer.py`, `json_writer.py`, `ndjson_writer.py`

```python
def write_csv(
    records: Iterator[Dict[str, Any]],  # <- Should be TypeVar or Protocol
    output_file: str | Path | None = None,
    ...
) -> None:
```

**Better**:
```python
from typing import Protocol

class JsonRecord(Protocol):
    """Protocol for JSON-serializable objects."""
    def model_dump(self) -> Dict[str, Any]: ...
    # or just use TypedDict
```

### 5.4 Missing TypeVar Constraints in catalog.py

**Location**: `catalog.py`, lines 35, 84-93

```python
_Item = TypeVar("_Item", bound=_HasName)  # Good!

def _get_by_name(
    name: str,
    kind: CollectionName,
    path: Optional[Path | str] = None,
) -> Optional[_Item]:  # But _Item not constrained in function context
```

This is actually fine - using TypeVar correctly. NO ISSUE HERE.

---

## 6. INCONSISTENT PATTERNS

### 6.1 Config Path Handling Inconsistency

**Location**: Multiple files

Three different patterns for config path:
```python
# Pattern 1: api.py line 19
config.set_config_path(jn)  # Side effect

# Pattern 2: run.py line 35
config.set_config_path(jn)  # Same side effect

# Pattern 3: core.py line 41-55
def use(path: Path | str | None = None) -> Config:
    """Load config from ``path`` and cache it."""
    # Returns the config object
```

**Inconsistency**: 
- `set_config_path()` is an alias for `use()` (config/__init__.py line 26)
- But `use()` returns Config, `set_config_path()` doesn't
- CLI doesn't capture return value (wasted computation)

**Better**:
```python
# In CLI
cfg = config.set_config_path(jn)  # Return the config!
names = cfg.api_names()  # Use returned config
```

### 6.2 Header Parsing Logic Not Reusable

**Location**: `api.py`, lines 86-96

```python
headers = {}
if header:
    for h in header:
        if ":" not in h:
            typer.echo(f"Error: Invalid header format: {h}. Expected KEY:VALUE", err=True)
            raise typer.Exit(1)
        key, value = h.split(":", 1)
        headers[key.strip()] = value.strip()
```

This logic would be needed if other commands add headers. Should be in `config.utils` or options.

### 6.3 Inconsistent Collection Item Naming

**Location**: Multiple files

Terms used:
- `apis`, `filters` - Collection names
- `get_api()`, `get_filter()` - Getters (specific)
- `get_item()` - Generic getter (not used consistently)
- `fetch_item()` - Compatibility alias (catalog.py line 127-134)

**Recommendation**: Pick one pattern and stick to it. `fetch_item()` is redundant.

---

## 7. TECHNICAL DEBT & POTENTIAL RISKS

### 7.1 Unimplemented Update Commands

**Location**: `api.py` line 209 and `filter.py` line 147

```python
@app.command()
def update(name: str, ...) -> None:
    """Update an existing API configuration (opens in $EDITOR)."""
    typer.echo("TODO: Implement update command (edit in $EDITOR)", err=True)
    raise typer.Exit(1)
```

**Risk**: Public API surface that doesn't work. Users will try it.

**Recommendation**: 
- Either implement it now
- Or remove from CLI (remove `@app.command()`)
- Document as planned feature

### 7.2 Global State Management

**Location**: `core.py`, lines 11-12, 33-38

```python
_CONFIG: Config | None = None
_CONFIG_PATH: Path | None = None

def _store(config_obj: Config, path: Path) -> Config:
    global _CONFIG, _CONFIG_PATH
    _CONFIG = config_obj
    _CONFIG_PATH = path
```

**Issues**:
1. Global mutable state (hard to test in parallel)
2. Thread-unsafe
3. Makes testing complex (need `reset()` between tests)

**Recommendation**: 
- Consider dependency injection instead
- Or wrap in a class: `class ConfigCache: ...`

### 7.3 Path Handling Edge Cases Not Validated

**Location**: `put.py`, lines 110-126

```python
if output_file == "-":
    if not format:
        typer.echo("Error: --format is required when writing to stdout", err=True)
        raise typer.Exit(1)
    output_path = None
else:
    output_path = Path(output_file)
    if output_path.exists() and not overwrite and not append:
        typer.echo(f"Error: File {output_file} already exists...", err=True)
        raise typer.Exit(1)
```

**Missing cases**:
- Parent directory doesn't exist (Path.write_text() will fail)
- Permission errors not handled
- Special files (pipes, devices) not validated

**Recommendation**: Add validation function:
```python
def _validate_output_path(output_path: Path) -> None:
    if output_path.parent and not output_path.parent.exists():
        raise ValueError(f"Parent directory doesn't exist: {output_path.parent}")
    # etc.
```

### 7.4 Security Concern: subprocess.run() with shell

**Location**: `run.py`, line 52

```python
subprocess.run(  # noqa: S603
    [jq_path, "-c", filter_obj.query],
```

**Good**: Using list form (not shell=True) - secure!

**Note**: The `noqa: S603` comment suggests this was flagged by a security linter, but the code is actually safe. Consider removing the noqa comment for clarity.

### 7.5 Deprecated subprocess Usage

**Location**: `run.py`, lines 56-57

```python
stderr=subprocess.PIPE,
check=True,
```

**Better**: Use `capture_output=True` (Python 3.7+) instead of `stderr=PIPE, stdout=PIPE`

### 7.6 NDJSON Reading Doesn't Handle EOF Gracefully

**Location**: `put.py`, lines 43-61

```python
def read_ndjson_from_stdin():
    """Read NDJSON records from stdin."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue  # Skip empty lines
        try:
            yield json.loads(line)
        except json.JSONDecodeError as e:
            typer.echo(f"Error: Invalid JSON on line: {line[:50]}...", err=True)
            typer.echo(f"  {e}", err=True)
            raise typer.Exit(1)  # Aborts processing - harsh!
```

**Issue**: One bad line aborts entire stream. Consider:
- Line number in error
- Option to skip bad lines with warning
- Max line length truncation (currently `[:50]`)

---

## Summary of Issues by Severity

### CRITICAL (Refactoring required)
1. **Massive code duplication between api.py and filter.py** - Extract common patterns
2. **Type ignores in api.py** - Implement proper validation instead of suppressing types
3. **Global mutable state in core.py** - Consider dependency injection

### HIGH (Should fix)
1. **Inconsistent error handling** - Pick Union OR exceptions, not both
2. **Nested conditionals in add()** - Extract helper functions
3. **CSV writer buffers all data** - Reevaluate streaming approach
4. **Missing return types in catalog.py** - Add type annotations

### MEDIUM (Could improve)
1. **Inconsistent config path handling** - Unify pattern
2. **Unimplemented update commands** - Either implement or remove
3. **Missing stderr preservation in subprocess** - Add stderr=PIPE
4. **Module organization for writers** - Consider class-based abstraction

### LOW (Polish)
1. **Success message on stderr** - Use stdout
2. **Path validation edge cases** - Add comprehensive validation
3. **Remove unnecessary noqa comments** - Code is actually secure
4. **Redundant fetch_item() alias** - Consolidate

---

## Files Most Affected (by number of issues)

1. **api.py** (10+ issues) - Duplication, type ignores, complexity
2. **filter.py** (8+ issues) - Duplication, confirmation logic
3. **put.py** (7+ issues) - Error handling, complexity, validation
4. **core.py** (3+ issues) - Global state, thread safety
5. **csv_writer.py** (2+ issues) - Memory efficiency, abstraction
6. **catalog.py** (2+ issues) - Missing types, validation

---

## Recommendations Priority List

1. **Week 1**: Extract common registry CLI pattern
2. **Week 1**: Fix type annotations in api.py  
3. **Week 2**: Refactor add() functions to remove nesting
4. **Week 2**: Unify error handling strategy
5. **Week 3**: Move to class-based writer abstraction
6. **Week 3**: Consider dependency injection for config state
