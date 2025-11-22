# Plugin Architecture Recommendation
**Analysis & Strategy for Universal Profile/Introspection System**

---

## Executive Summary

**Problem**: DuckDB implementation added ~200 lines of plugin-specific code to 5 core framework files. This pattern is **unsustainable** - every new protocol plugin requires framework modifications.

**Root Cause**: Inconsistent architecture across existing plugins. Some plugins are self-contained (HTTP), others require framework helpers (Gmail, DuckDB).

**Recommendation**: Adopt **Strategy: Self-Contained Plugins** - Push ALL logic to plugins, framework becomes a dumb router. Estimated savings: **~300 lines from core**, zero code required for new plugins.

---

## Current State Analysis

### Plugins with Profile Support

| Plugin | Profile Files | Framework Code | Self-Contained? | Lines of Framework Code |
|--------|---------------|----------------|-----------------|-------------------------|
| **HTTP** | `.json` | ✅ VENDORED in plugin | ✅ YES | 0 (duplicated ~150 in plugin) |
| **Gmail** | `.json` | ❌ `src/jn/profiles/gmail.py` | ❌ NO | ~110 |
| **JQ** | `.jq` | ❌ `src/jn/profiles/service.py` | ❌ NO | ~60 |
| **DuckDB** | `.sql` | ❌ Multiple files | ❌ NO | ~200 |
| **MCP** | `.json` | ❌ TBD | ❌ NO | TBD |

**Total Framework Code**: ~370 lines for profile-specific logic that should be in plugins

---

## The 5 Concerns

For each plugin with profiles, the framework currently handles:

### 1. **Profile Discovery** (Finding available profiles)

**Current Implementation**:
```python
# src/jn/profiles/service.py - 334 lines total
def _parse_jq_profile(jq_file: Path, profile_root: Path) -> ProfileInfo:
    """Parse JQ .jq files, extract metadata from comments"""

def _parse_duckdb_profile(sql_file: Path, profile_root: Path) -> ProfileInfo:
    """Parse DuckDB .sql files, extract SQL metadata"""

def list_all_profiles() -> List[ProfileInfo]:
    """Scan filesystem for jq/*.jq, duckdb/*.sql, gmail/*.json, http/*.json"""
```

**Problems**:
- Framework knows about `.jq`, `.sql`, `.json` file extensions for each plugin
- Duplicates metadata extraction logic already in plugins
- Adding new plugin requires modifying `list_all_profiles()`

---

### 2. **Profile Resolution** (Converting @ref to actual config)

**Current Implementation**:
```python
# src/jn/addressing/resolver.py - 858 lines total

# Lines 107-110: DuckDB hardcoded
if address.type == "profile" and plugin_name == "duckdb_":
    config = self._build_duckdb_profile_config(address)

# Lines 819-833: Gmail hardcoded
if namespace == "gmail":
    url = resolve_gmail_reference(address.base, address.parameters)

# Lines 836-842: HTTP hardcoded
url, headers = resolve_profile_reference(address.base, address.parameters)

# Lines 694-758: 73-line DuckDB-specific config builder
def _build_duckdb_profile_config(self, address: Address) -> Dict:
    profiles = search_profiles(type_filter="duckdb")
    # Load .sql file, parse _meta.json, build param-* keys...
```

**Problems**:
- Hardcoded `if plugin_name == "duckdb_"` checks
- Framework imports from `profiles/gmail.py`, `profiles/http.py`
- Profile-to-config logic leaks into framework
- 73 lines just for DuckDB config building

---

### 3. **Container Detection** (Is this a listing or a resource?)

**Current Implementation**:
```python
# src/jn/cli/commands/inspect.py - 629 lines total

def _is_container(address_str: str) -> bool:
    # Lines 34-36: Gmail hardcoded
    if address_str.startswith("gmail://"):
        return address_str.count("/") == 2

    # Lines 38-48: DuckDB hardcoded (URL parsing!)
    if address_str.startswith("duckdb://"):
        base = address_str.split("?")[0]
        for ext in (".duckdb", ".ddb"):
            if ext in base:
                suffix = base.split(ext, 1)[1].strip("/")
                return not suffix

    # Lines 54-57: Generic @ reference
    if address_str.startswith("@"):
        return "/" not in address_str[1:].split("?")[0]
```

**Problems**:
- Framework knows Gmail's URL structure (`count("/") == 2`)
- Framework knows DuckDB file extensions (`.duckdb`, `.ddb`)
- URL parsing logic belongs in plugins

---

### 4. **Container Formatting** (Pretty-printing inspection results)

**Current Implementation**:
```python
# src/jn/cli/commands/inspect.py

def _format_container_text(result: dict) -> str:
    transport = result.get("transport", "unknown")

    # Lines 69-95: HTTP formatting (27 lines)
    if transport == "http":
        lines.append(f"API: {result.get('api', 'unknown')}")
        for source in sources:
            lines.append(f"  • {source['name']}")
            # Format params, description, etc.

    # Lines 141-176: DuckDB formatting (35 lines)
    elif transport == "duckdb":
        for table in tables:
            lines.append(f"  • {table['name']}")
            # Format type, columns, etc.

    elif transport == "duckdb-profile":
        for query in queries:
            # Format query metadata

    # Lines 178-210: Gmail formatting (32 lines)
    elif transport == "gmail":
        for label in labels:
            # Format label data
```

**Problems**:
- Framework has ~100 lines of plugin-specific formatting
- Each plugin needs a new `elif transport == "X"` block
- Plugins already output structured data - framework just reformats it

---

### 5. **Parameter Classification** (Config vs Filter params)

**Current Implementation**:
```python
# src/jn/introspection.py

def get_plugin_config_params(plugin_path: str) -> List[str]:
    # Lines 116-119: DuckDB hardcoded (string matching!)
    if "duckdb" in plugin_path.lower():
        return ["__ALL_PARAMS_ARE_CONFIG__", "limit", "offset", "format"]

    # ... generic introspection

# src/jn/filtering.py

def separate_config_and_filters(params: Dict, config_param_names: List[str]):
    # Lines 241-244: Magic marker pattern
    if "__ALL_PARAMS_ARE_CONFIG__" in config_param_names:
        return dict(params), []  # All config, no filters
```

**Problems**:
- String-based plugin detection (`if "duckdb" in plugin_path`)
- Magic marker (`__ALL_PARAMS_ARE_CONFIG__`) is a code smell
- Should ask plugin, not guess

---

## Comparison: HTTP Plugin vs DuckDB Plugin

### HTTP Plugin (✅ Good Architecture)

**Plugin is self-contained**:
```python
# jn_home/plugins/protocols/http_.py

# Lines 66-250: VENDORED profile resolution (~180 lines)
def find_profile_paths() -> list[Path]:
    """Self-contained profile discovery"""

def load_hierarchical_profile(api_name: str, source_name: str) -> dict:
    """Self-contained profile loading"""

def resolve_profile_reference(reference: str, params: dict) -> tuple:
    """Self-contained profile resolution"""

def reads(url: str, **params) -> Iterator[dict]:
    # Lines 321-355: Container detection & listing INSIDE plugin
    if url.startswith("@") and "/" not in url[1:].split("?")[0]:
        # List available sources
        sources = list_profile_sources(api_name)
        for source_name in sources:
            yield {"name": source_name, "_type": "source", ...}
        return

    # Lines 358-367: Profile resolution INSIDE plugin
    if url.startswith("@"):
        resolved_url, headers, timeout, method = resolve_profile_reference(url, params)
```

**Framework code**: 0 lines (except generic param passing)

**Duplication**: Yes, vendored code duplicates `src/jn/profiles/http.py`, but plugin is **portable** and **self-contained**

---

### DuckDB Plugin (❌ Bad Architecture)

**Plugin delegates to framework**:
```python
# jn_home/plugins/databases/duckdb_.py

def reads(config: Optional[dict] = None) -> Iterator[dict]:
    # Lines 128-132: Container listing (only in plugin)
    if url and url.startswith("@") and "/" not in url[1:]:
        yield from _list_profile_queries(namespace)  # ✅ Good
        return

    # Lines 136-138: Profile mode (expects framework to provide SQL)
    if cfg.get("profile_sql"):  # ❌ Framework built this config
        db_path = cfg["db_path"]
        query = cfg["profile_sql"]
        params = cfg.get("params") or {}
```

**Framework code**: ~200 lines across 5 files

**What framework provides**:
- `resolver.py`: 73-line config builder, namespace detection via filesystem check
- `profiles/service.py`: 52-line SQL parser
- `introspection.py`: String-based detection
- `filtering.py`: Magic marker handling
- `inspect.py`: Container detection, formatting

---

## Root Cause: Inconsistent Design Decisions

### Why is HTTP self-contained but Gmail/DuckDB aren't?

Looking at the code:

1. **HTTP plugin was written FIRST** - vendored its own profile code to be self-contained
2. **Gmail plugin was written SECOND** - framework team said "let's not duplicate code" and created `src/jn/profiles/gmail.py`
3. **JQ profiles were added** - framework team extended `profiles/service.py` with JQ parsing
4. **DuckDB was added** - I followed the Gmail pattern and made it worse

**Result**: Architecture drift. No clear principle.

---

## Recommendation: Universal Self-Contained Plugin Architecture

### Core Principle

> **The framework is a dumb router. Plugins are smart endpoints.**

Framework responsibilities:
- Parse address syntax (`@ref`, `protocol://`, `file.ext`)
- Match address to plugin via regex patterns
- Invoke plugin subprocess with raw address
- Stream NDJSON between plugins

Plugin responsibilities:
- Parse their own URLs/references
- Load their own profiles
- Detect containers vs leaves
- Format their own output
- Return structured metadata

---

### Concrete Design

#### 1. Profile Discovery: Plugin Introspection Mode

Add optional `--mode inspect-profiles` to plugins:

```bash
# Framework calls:
python http_.py --mode inspect-profiles

# Plugin outputs NDJSON of ProfileInfo:
{"reference": "@genomoncology/alterations", "description": "...", "params": ["gene"]}
{"reference": "@genomoncology/fusions", "description": "...", "params": []}
```

**Framework code**:
```python
# src/jn/profiles/service.py - SIMPLIFIED to ~50 lines

def list_all_profiles() -> List[ProfileInfo]:
    """Discover profiles from ALL plugins that support them."""
    profiles = []

    for plugin in discover_plugins():
        # Try to invoke plugin in profile discovery mode
        try:
            result = subprocess.run(
                [plugin.path, "--mode", "inspect-profiles"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Parse NDJSON output
                for line in result.stdout.strip().split("\n"):
                    profiles.append(ProfileInfo(**json.loads(line)))
        except:
            # Plugin doesn't support profiles, skip
            pass

    return profiles
```

**Plugin code** (example for DuckDB):
```python
# jn_home/plugins/databases/duckdb_.py

def inspect_profiles() -> Iterator[dict]:
    """List all DuckDB profiles (called via --mode inspect-profiles)."""
    jn_home = Path(os.getenv("JN_HOME", Path.home() / ".jn"))
    duckdb_dir = jn_home / "profiles" / "duckdb"

    if not duckdb_dir.exists():
        return

    for sql_file in duckdb_dir.rglob("*.sql"):
        # Parse metadata from SQL file
        content = sql_file.read_text()
        description = extract_description_from_comments(content)
        params = extract_params_from_sql(content)

        # Build reference
        namespace = sql_file.parent.name
        query_name = sql_file.stem

        yield {
            "reference": f"@{namespace}/{query_name}",
            "type": "duckdb",
            "namespace": namespace,
            "name": query_name,
            "description": description,
            "params": params,
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["read", "write", "inspect-profiles"])
    # ... handle modes

    if args.mode == "inspect-profiles":
        for profile in inspect_profiles():
            print(json.dumps(profile))
```

**Benefits**:
- Framework code shrinks from 334 lines → ~50 lines
- Zero framework changes for new plugins
- Each plugin owns its profile discovery logic
- Slightly slower (subprocess per plugin), but happens infrequently

---

#### 2. Profile Resolution: Plugin Handles Raw Addresses

Framework passes RAW address to plugin, plugin parses it:

**Framework code**:
```python
# src/jn/addressing/resolver.py - REMOVE all profile-specific code

def resolve(self, address: Address) -> ResolvedAddress:
    plugin = self._find_plugin(address)

    # For protocol plugins, pass raw address as 'url' parameter
    if plugin.role == "protocol":
        config = {"url": address.original}  # Just pass "@ref" or "duckdb://..." as-is
        # Add query parameters as separate config keys
        config.update(address.parameters or {})
    else:
        # Format plugins get file path
        config = {"path": address.path}

    return ResolvedAddress(plugin=plugin, config=config)
```

**Plugin code** (DuckDB):
```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    cfg = config or {}
    raw_address = cfg.get("url") or cfg.get("path")

    # Parse address - plugin knows its own syntax!
    if raw_address.startswith("@"):
        # Profile reference: @namespace/query or @namespace
        namespace, query_name = parse_profile_reference(raw_address)

        if not query_name:
            # Container: list available queries
            yield from list_profile_queries(namespace)
            return

        # Leaf: load profile and resolve
        sql_content, db_path = load_profile(namespace, query_name)
        params = cfg  # All params are SQL bind params

    elif raw_address.startswith("duckdb://"):
        # Direct access: duckdb://file.duckdb or duckdb://file.duckdb/table
        db_path, table, query = parse_duckdb_url(raw_address)

        if not table and not query:
            # Container: list tables
            yield from list_tables(db_path)
            return

        # Leaf: query the database
        if table:
            sql_content = f"SELECT * FROM {table}"
        else:
            sql_content = query

    # Execute query and stream results
    conn = duckdb.connect(db_path, read_only=True)
    cursor = conn.execute(sql_content, params)
    for row in cursor.fetchall():
        yield dict(zip([col[0] for col in cursor.description], row))
```

**Benefits**:
- Framework code shrinks: REMOVE ~200 lines of DuckDB-specific logic
- Plugin owns URL parsing (knows `.duckdb` extension, `@` syntax)
- Plugin owns profile loading (knows `.sql` files, `_meta.json`)
- Clean separation of concerns

---

#### 3. Container Detection: Plugin Metadata or Convention

**Option A: PEP 723 Capability Declaration**

```python
# /// script
# [tool.jn]
# matches = ["^duckdb://.*"]
# capabilities = {
#   "profiles": true,
#   "containers": true,
#   "param_model": "all_config"
# }
# ///
```

Framework checks if plugin has `capabilities.containers = true`, assumes it handles container detection.

**Option B: Convention (Simpler)**

Plugin returns records with `_type` and `_container` fields → framework knows it's a listing.

```python
# Container listing (plugin output):
{"name": "users", "columns": 5, "_type": "table", "_container": "db.duckdb"}

# Data record (plugin output):
{"id": 1, "name": "Alice"}  # No _type/_container fields
```

Framework inspects first record - if it has `_type`, it's a container listing.

**Recommendation**: Use **Option B** (convention) - no PEP 723 changes needed, already works.

---

#### 4. Container Formatting: Plugin Provides Formatter (Optional)

**Option A: Plugin Subprocess**

```bash
# Framework calls:
python duckdb_.py --mode format-inspection < listing.ndjson

# Plugin reads NDJSON from stdin, outputs formatted text
```

**Option B: Generic Formatting (Simpler)**

Framework uses generic NDJSON formatter - just pretty-prints the structured data:

```python
def _format_container_generic(result: dict) -> str:
    """Generic formatter that works for ANY plugin."""
    lines = []

    # Header
    container = result.get("_container", "unknown")
    lines.append(f"Container: {container}")
    lines.append("")

    # Listings
    items = result.get("items", [])
    lines.append(f"Items ({len(items)}):")

    for item in items:
        name = item.get("name", item.get("id", "unknown"))
        lines.append(f"  • {name}")

        # Print all non-internal fields
        for key, value in item.items():
            if not key.startswith("_") and key != "name":
                lines.append(f"    {key}: {value}")
        lines.append("")

    return "\n".join(lines)
```

**Recommendation**: Use **Option B** (generic) - plugins already output structured data, framework just renders it.

**Benefits**:
- Framework code: REMOVE ~100 lines of plugin-specific formatting
- Works for ALL plugins (current and future)
- Plugins control structure via field names

---

#### 5. Parameter Classification: Plugin Declares Model

**Option A: PEP 723 Declaration**

```python
# /// script
# [tool.jn]
# param_model = "all_config"  # vs "mixed" vs "all_filters"
# ///
```

Framework checks metadata, no introspection needed.

**Option B: Convention**

- Protocol plugins: all params are config (passed to plugin)
- Filter plugins: first arg is filter expression, rest are config
- Format plugins: all params are config

**Recommendation**: Use **Option B** (convention) - simpler, already mostly works.

**Benefits**:
- Framework code: REMOVE `__ALL_PARAMS_ARE_CONFIG__` hack
- Plugin role (`protocol`, `filter`, `format`) determines behavior
- No string-based detection

---

## Migration Plan

### Phase 1: HTTP Plugin (Already Done ✅)
- HTTP plugin is already self-contained
- Framework has duplicate code in `src/jn/profiles/http.py`
- **Action**: DELETE `src/jn/profiles/http.py`, keep plugin's vendored version

### Phase 2: DuckDB Plugin (Refactor)
1. **Move profile resolution to plugin**
   - Copy `_build_duckdb_profile_config()` logic INTO plugin
   - Plugin parses `@namespace/query` references itself
   - Plugin loads `.sql` files and `_meta.json` itself

2. **Add profile discovery mode**
   - Implement `--mode inspect-profiles` in plugin
   - Returns NDJSON of available profiles

3. **Update framework**
   - REMOVE `_build_duckdb_profile_config()` from resolver
   - REMOVE DuckDB-specific checks from resolver
   - REMOVE `_parse_duckdb_profile()` from service.py
   - REMOVE DuckDB formatting from inspect.py
   - REMOVE `__ALL_PARAMS_ARE_CONFIG__` from introspection.py

**Lines removed**: ~200 from framework

### Phase 3: Gmail Plugin (Refactor)
1. **Vendor profile code into plugin**
   - Copy `src/jn/profiles/gmail.py` into plugin (like HTTP)
   - Plugin handles `@gmail/inbox` references internally

2. **Add profile discovery mode**
   - Implement `--mode inspect-profiles`

3. **Update framework**
   - DELETE `src/jn/profiles/gmail.py`
   - REMOVE Gmail-specific resolver code
   - REMOVE Gmail formatting from inspect.py

**Lines removed**: ~110 from framework

### Phase 4: JQ Plugin (Refactor)
1. **Move profile parsing to plugin**
   - Plugin scans `profiles/jq/*.jq` files
   - Plugin extracts metadata from comments

2. **Add profile discovery mode**
   - Implement `--mode inspect-profiles`

3. **Update framework**
   - REMOVE `_parse_jq_profile()` from service.py

**Lines removed**: ~60 from framework

### Phase 5: Simplify Framework
1. **profiles/service.py**: Remove all plugin-specific parsers, keep only:
   - Generic `list_all_profiles()` that calls plugins
   - `ProfileInfo` data model

2. **addressing/resolver.py**: Remove all profile resolution, keep only:
   - Generic config building (pass raw address to plugin)

3. **cli/commands/inspect.py**: Remove all plugin-specific formatting, keep only:
   - Generic container formatter
   - Simple `_type`-based detection

4. **introspection.py**: Remove string-based detection
5. **filtering.py**: Remove magic markers

**Total lines removed**: ~370 from framework

---

## Final Architecture

### Framework (Core)
```
src/jn/
├── addressing/
│   ├── parser.py          # Parse address syntax (unchanged)
│   ├── resolver.py        # ✂️ 200 lines removed - just route to plugins
│   └── types.py           # (unchanged)
├── cli/commands/
│   └── inspect.py         # ✂️ 100 lines removed - generic formatting
├── profiles/
│   ├── service.py         # ✂️ 250 lines removed - just call plugins
│   └── http.py            # ❌ DELETED (vendored in plugin)
│   └── gmail.py           # ❌ DELETED (vendored in plugin)
├── introspection.py       # ✂️ 5 lines removed - no string detection
└── filtering.py           # ✂️ 5 lines removed - no magic markers
```

**Total**: ~560 lines removed

### Plugins (Self-Contained)
```
jn_home/plugins/protocols/
├── http_.py               # ✅ Already self-contained (~500 lines)
│   ├── Profile discovery (vendored)
│   ├── Profile resolution (vendored)
│   ├── Container detection (in reads())
│   └── --mode inspect-profiles
│
├── gmail_.py              # ♻️ Refactor to match HTTP pattern
│   ├── Vendor gmail profile code
│   └── Add --mode inspect-profiles
│
├── duckdb_.py             # ♻️ Refactor to be self-contained
│   ├── Move profile loading into plugin
│   ├── Parse @namespace/query internally
│   └── Add --mode inspect-profiles
│
└── mcp_.py                # ♻️ Follow same pattern
```

**Plugin Growth**: ~150 lines per plugin (but fully self-contained)

---

## Trade-offs

### ✅ Pros
1. **Zero framework changes for new plugins** - biggest win
2. **Plugins are portable** - can be copied between projects
3. **Clear separation of concerns** - framework routes, plugins handle logic
4. **Easier to understand** - all logic for a plugin is in one file
5. **Better testing** - test plugins independently
6. **Faster iteration** - plugin developers don't touch framework

### ⚠️ Cons
1. **Code duplication** - each plugin vendors profile logic (~150 lines)
2. **Slightly slower discovery** - subprocess per plugin for `jn profile list`
3. **Larger plugins** - HTTP plugin is ~500 lines (vs ~200 if framework helped)

### 🎯 Judgment Call

**The duplication is worth it.**

Why?
- Duplication is ~150 lines per plugin (manageable)
- But saves ~300 lines of framework code that would grow with EVERY new plugin
- More importantly: **architectural clarity** - new plugin developers know exactly where to put code
- HTTP plugin proves this works (already doing it)

---

## Speed Analysis

### Current Speed (Framework-Heavy)
```
jn profile list
├── Load plugin metadata (fast)
├── Scan profiles/duckdb/*.sql (fast)
├── Parse each .sql file (fast)
└── Return list
Time: ~5ms for 20 profiles
```

### Proposed Speed (Plugin-Heavy)
```
jn profile list
├── Discover plugins (fast)
├── For each protocol plugin:
│   ├── Spawn subprocess: python plugin.py --mode inspect-profiles
│   ├── Plugin scans its own profiles
│   └── Parse NDJSON output
└── Aggregate results
Time: ~50ms for 5 plugins × ~10ms each
```

**10x slower** (5ms → 50ms), but still **instant** from user perspective.

**Optimization**: Cache plugin outputs for 5 seconds if needed.

---

## Recommendation Summary

### Adopt: Self-Contained Plugin Architecture

**Core Changes**:
1. ✂️ Remove ~370 lines of plugin-specific framework code
2. ♻️ Refactor 4 plugins to be self-contained (add ~150 lines each)
3. 📝 Document plugin development pattern clearly
4. ✅ Future plugins require ZERO framework changes

**Implementation Order**:
1. **Week 1**: DuckDB refactor (highest priority - most framework code)
2. **Week 2**: Gmail refactor
3. **Week 3**: JQ refactor
4. **Week 4**: Documentation & cleanup

**Success Criteria**:
- Zero `if plugin_name == "X"` checks in framework
- Zero imports from `src/jn/profiles/{plugin}.py` in resolver
- New plugin developer can implement profiles without touching framework
- `make test` passes with same coverage

---

## Example: Adding New Plugin (Before vs After)

### Before (Current Architecture)

Developer wants to add PostgreSQL plugin with profiles:

1. **Create plugin**: `jn_home/plugins/databases/postgres_.py`
2. **Add framework code**:
   - `src/jn/profiles/postgres.py` - profile loader (~100 lines)
   - `src/jn/addressing/resolver.py` - add PostgreSQL checks (~50 lines)
   - `src/jn/profiles/service.py` - add `_parse_postgres_profile()` (~60 lines)
   - `src/jn/cli/commands/inspect.py` - add PostgreSQL formatting (~40 lines)
   - `src/jn/introspection.py` - add string detection (~5 lines)
3. **Update tests**: Framework tests + plugin tests

**Total**: ~255 lines across 5 framework files

---

### After (Self-Contained Architecture)

Developer wants to add PostgreSQL plugin with profiles:

1. **Create plugin**: `jn_home/plugins/databases/postgres_.py`
   - Vendor profile loading (copy from DuckDB template)
   - Implement `--mode inspect-profiles`
   - Handle `@namespace/query` in `reads()`
   - ~400 lines total (but all in ONE file)

2. **Framework changes**: ZERO

3. **Tests**: Only plugin tests

**Total**: 0 lines of framework code, 400 lines of plugin code (self-contained)

---

## Conclusion

The **Self-Contained Plugin Architecture** is the clear winner:

- **Scalability**: Zero framework code per new plugin
- **Clarity**: All logic in one place
- **Speed**: Still instant (<50ms)
- **Simplicity**: Plugin developers never touch framework
- **Proven**: HTTP plugin already works this way

**Cost**: ~150 lines of duplicated profile code per plugin
**Benefit**: ~300 lines removed from framework, infinite future savings

**Next Steps**:
1. Get buy-in on this approach
2. Start with DuckDB refactor (biggest cleanup)
3. Apply same pattern to Gmail, JQ
4. Document the pattern for future plugin developers

---

**Author**: Claude (2025-11-22)
**Status**: Recommendation - Awaiting Decision
