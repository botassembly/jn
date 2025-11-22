# DuckDB Plugin

**Status:** ✅ Implemented
**Plugin:** `jn_home/plugins/databases/duckdb_.py`
**Date:** 2025-11-22

---

## Overview

The DuckDB plugin enables querying analytical databases through SQL-based profiles. It's a self-contained protocol plugin that manages its own profile discovery and resolution.

**Usage:**
```bash
# Query via profile
jn cat "@analytics/sales-summary"

# With parameters
jn cat "@analytics/by-region?region=West"

# List profiles
jn profile list --type duckdb

# Inspect namespace
jn inspect "@analytics"
```

---

## Architecture

### Self-Contained Protocol Plugin

The DuckDB plugin follows the self-contained architecture pattern:

1. **Vendors all logic** - Profile discovery, SQL parsing, parameter handling
2. **No framework coupling** - Works standalone via `--mode` flags
3. **Implements inspect-profiles** - Framework calls plugin to discover profiles

**Key principle:** Framework is a dumb router. Plugin contains all DuckDB-specific logic.

### Plugin Modes

```python
# Data reading
python duckdb_.py --mode read "@namespace/query?param=value"

# Profile discovery (called by framework)
python duckdb_.py --mode inspect-profiles

# Container inspection
python duckdb_.py --mode inspect-container "duckdb://path/to/db"
```

---

## Profile Structure

```
profiles/duckdb/{namespace}/
├── _meta.json              # Database connection config
├── {query}.sql             # Named SQL queries
└── {query}.sql
```

**Example:**
```
profiles/duckdb/analytics/
├── _meta.json
├── sales-summary.sql
├── by-region.sql
└── monthly-revenue.sql
```

### Meta File: `_meta.json`

```json
{
  "driver": "duckdb",
  "path": "data/analytics.duckdb",
  "description": "Analytics database"
}
```

**Fields:**
- `driver` - Always "duckdb"
- `path` - Path to .duckdb file (relative to profile dir or absolute)
- `description` - Human-readable description (optional)

**Path resolution:**
- Relative paths: Resolve from `_meta.json` directory
- Absolute paths: Use as-is

### SQL Files: `.sql`

SQL queries with optional parameter placeholders and metadata comments.

**Example:** `by-region.sql`
```sql
-- Regional sales analysis
-- Parameters: region

SELECT
    product,
    SUM(revenue) as total_revenue,
    COUNT(*) as sales_count
FROM sales
WHERE region = $region
GROUP BY product
ORDER BY total_revenue DESC;
```

**Features:**
- **Description:** First `--` comment line
- **Parameters:** `-- Parameters: param1, param2` or auto-detected from SQL
- **Placeholders:** `$param` or `:param` (converted to `$param`)
- **Auto-limit:** Framework can apply `LIMIT N` via `--limit` flag

---

## Parameter Handling

### Parameter Syntax

Both DuckDB-style (`$param`) and generic (`:param`) are supported:

```sql
-- DuckDB style (native)
SELECT * FROM users WHERE id = $user_id

-- Generic style (converted to $param)
SELECT * FROM users WHERE id = :user_id
```

The plugin converts `:param` → `$param` using regex: `(?<!:):([a-zA-Z_]\w*)`

This preserves:
- Time literals: `'12:00:00'`
- Cast operators: `foo::DATE`
- URLs in strings: `'http://example.com'`

### Passing Parameters

**Via URL query string:**
```bash
jn cat "@analytics/by-region?region=West"
jn cat "@analytics/sales?year=2024&quarter=Q1"
```

**Via CLI flags (future):**
```bash
jn cat "@analytics/by-region" -p region=West
```

Parameters are passed to DuckDB's `execute(query, params)` as a dict.

---

## Profile Discovery

### Framework Integration

The framework discovers DuckDB profiles by calling:
```bash
uv run --script duckdb_.py --mode inspect-profiles
```

The plugin scans profile paths and returns NDJSON:
```json
{"reference": "@analytics/sales-summary", "type": "duckdb", "namespace": "analytics", "name": "sales-summary", "path": "/path/to/sales-summary.sql", "description": "Sales summary", "params": [], "examples": []}
{"reference": "@analytics/by-region", "type": "duckdb", "namespace": "analytics", "name": "by-region", "path": "/path/to/by-region.sql", "description": "Regional sales", "params": ["region"], "examples": []}
```

### Profile Path Priority

The plugin searches for profiles in priority order:

1. **Project-local:** `.jn/profiles/duckdb/` (relative to CWD)
2. **User profiles:** `$JN_HOME/profiles/duckdb/` or `~/.jn/profiles/duckdb/`

This allows:
- Project-specific queries in version control
- User-global queries in `~/.jn/`

---

## Implementation Details

### Core Functions

**Profile loading** (vendored from framework):
```python
def _load_profile(reference: str) -> Tuple[str, str, dict]:
    """Load DuckDB profile from filesystem.

    Returns:
        (db_path, sql_content, meta)
    """
```

**Profile discovery:**
```python
def inspect_profiles() -> Iterator[dict]:
    """List all available DuckDB profiles.

    Called by framework with --mode inspect-profiles.
    Returns ProfileInfo-compatible records.
    """
```

**Query execution:**
```python
def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Execute SQL query and stream results as NDJSON.

    Handles:
    - Profile resolution (@namespace/query)
    - Parameter substitution
    - Streaming results
    - Auto-limit
    """
```

### Dependencies

PEP 723 metadata:
```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "duckdb>=0.9.0",
# ]
# [tool.jn]
# matches = ["^@.*", "^duckdb://.*"]
# role = "protocol"
# ///
```

The `uv run --script` shebang ensures `duckdb` package is installed.

---

## Container Inspection

The plugin supports inspecting DuckDB database files:

```bash
jn inspect "duckdb://data/analytics.duckdb"
```

**Output:**
```json
{
  "transport": "duckdb-container",
  "path": "data/analytics.duckdb",
  "tables": [
    {"name": "sales", "columns": ["id", "product", "revenue", "region", "date"]},
    {"name": "customers", "columns": ["id", "name", "email", "created_at"]},
    {"name": "products", "columns": ["id", "name", "category", "price"]}
  ]
}
```

This allows:
- Discovering available tables
- Understanding database schema
- Creating profile queries

---

## CLI Integration

### Profile Management

```bash
# List DuckDB profiles
jn profile list --type duckdb

# Get profile details
jn profile info "@analytics/sales-summary"

# Inspect namespace (shows all queries)
jn inspect "@analytics"
```

### Querying Data

```bash
# Execute profile query
jn cat "@analytics/sales-summary"

# With parameters
jn cat "@analytics/by-region?region=West"

# With limit
jn cat "@analytics/sales-summary" --limit 10

# Pipeline with filters
jn cat "@analytics/sales-summary" | jn filter '.revenue > 1000' | jn put output.csv
```

---

## Architecture Pattern: Self-Contained Plugins

The DuckDB plugin exemplifies the self-contained protocol plugin pattern:

### Before (Coupled)

**Problem:** Framework contained DuckDB-specific code
- `profiles/service.py` had `_parse_duckdb_profile()` function
- Framework scanned filesystem for `.sql` files
- ~200 lines of DuckDB logic in framework

**Issues:**
- Framework bloat
- Plugin not independently testable
- Hard to add new database plugins

### After (Self-Contained)

**Solution:** Plugin vendors all logic
- Plugin has `inspect_profiles()` mode
- Framework calls plugin subprocess to discover profiles
- Plugin handles SQL parsing, parameter detection, etc.

**Benefits:**
- ✅ Framework is generic (works for any protocol plugin)
- ✅ Plugin is standalone (testable independently)
- ✅ Easy to add PostgreSQL, MySQL, SQLite plugins (same pattern)

### Framework → Plugin Communication

```
Framework                     Plugin
---------                     ------
1. Discover plugins     →     [Plugin exists at path]
2. Call plugin          →     uv run --script plugin.py --mode inspect-profiles
3. Receive NDJSON       ←     {"reference": "@ns/q", "type": "duckdb", ...}
4. Cache results              [Store in ProfileInfo objects]
5. User queries profile       jn cat "@ns/q?param=val"
6. Resolve address      →     [Match @ns/q to duckdb plugin]
7. Call plugin          →     uv run --script plugin.py --mode read "@ns/q?param=val"
8. Stream NDJSON        ←     {"id": 1, "name": "Alice"}
```

**Key insight:** Framework never parses SQL or knows about DuckDB. It just routes addresses to plugins.

---

## Testing

### Unit Tests

Located in `tests/cli/test_duckdb.py`:

```python
def test_duckdb_direct_query(invoke, tmp_path):
    """Test direct database queries."""
    # Create test DB, query it

def test_duckdb_profile_query(invoke, tmp_path, test_db):
    """Test profile-based queries."""
    # Create profile, query via @namespace/query

def test_duckdb_profile_with_params(invoke, tmp_path, test_db):
    """Test parameterized profile queries."""
    # Query with ?param=value syntax

def test_duckdb_container_inspect(invoke, tmp_path):
    """Test database container inspection."""
    # jn inspect duckdb://db shows tables

def test_duckdb_profile_with_params_in_url(invoke, tmp_path, test_db):
    """Test URL-based parameter passing."""
    # Full integration test
```

**Coverage:** 5 tests, all passing

### Manual Testing

```bash
# Create test database
duckdb test.duckdb << EOF
CREATE TABLE users (id INT, name VARCHAR, email VARCHAR);
INSERT INTO users VALUES (1, 'Alice', 'alice@example.com');
INSERT INTO users VALUES (2, 'Bob', 'bob@example.com');
EOF

# Create profile
mkdir -p .jn/profiles/duckdb/test
cat > .jn/profiles/duckdb/test/_meta.json << EOF
{"driver": "duckdb", "path": "test.duckdb"}
EOF

cat > .jn/profiles/duckdb/test/all-users.sql << EOF
-- All users
SELECT * FROM users;
EOF

cat > .jn/profiles/duckdb/test/by-id.sql << EOF
-- User by ID
-- Parameters: user_id
SELECT * FROM users WHERE id = $user_id;
EOF

# Test
jn profile list --type duckdb
jn cat "@test/all-users"
jn cat "@test/by-id?user_id=1"
```

---

## Migration Notes

### From Previous Design

The original DuckDB specs (`spec/todo/duckdb-*.md`) proposed a coupled architecture with framework-side SQL parsing. This was refactored to the self-contained pattern during implementation.

**Key changes:**
- Profile discovery moved from `profiles/service.py` to plugin
- SQL parsing moved from framework to plugin
- Framework calls plugin subprocess instead of importing Python functions

### Upgrading Profiles

Old-style profiles (if any exist) work without changes. The profile structure is the same:
```
profiles/duckdb/{namespace}/
├── _meta.json
└── {query}.sql
```

---

## Future Enhancements

### Potential Features (Not Implemented)

1. **Write support** - `jn put "@analytics/table"` to insert data
2. **Schema management** - `jn duckdb migrate` to apply schema changes
3. **Query templates** - Parameterized common queries
4. **Multiple databases** - Multiple `_meta.json` configs per namespace

### Other Database Plugins

The self-contained pattern makes it easy to add:
- **PostgreSQL plugin** - Same pattern, different SQL dialect
- **MySQL plugin** - Same pattern, different connection
- **SQLite plugin** - Similar to DuckDB

Each plugin would implement:
- `--mode read` for querying
- `--mode inspect-profiles` for profile discovery
- `--mode inspect-container` for schema inspection

---

## Summary

The DuckDB plugin demonstrates the self-contained protocol plugin architecture:

✅ **Self-contained** - All DuckDB logic in plugin, zero in framework
✅ **Profile-based** - SQL queries as `.sql` files with `@namespace/query` syntax
✅ **Parameterized** - URL query parameters passed to SQL
✅ **Discoverable** - `--mode inspect-profiles` for framework integration
✅ **Inspectable** - `--mode inspect-container` for database schema
✅ **Tested** - 5 tests covering core functionality

**Result:** Clean separation of concerns. Framework routes, plugin executes.
