# DuckDB Profile System

**Status:** Design + Implementation Guide
**Priority:** P0 (blocks g2 production use)
**Dependencies:** Plugin system, Profile system (`spec/done/profile-usage.md`)

---

## Problem

Users need to run SQL queries against DuckDB databases without URL-encoded query strings.

**Current (unacceptable):**
```bash
jn cat "duckdb://genie.duckdb?query=SELECT%20patient_id%2C%20regimen%20FROM%20treatments%20WHERE%20regimen%20LIKE%20'%25FOLFOX%25'"
```

**Desired:**
```bash
jn cat "@genie/folfox-cohort"
```

---

## Solution

SQL-based profiles: Store queries as `.sql` files in profile directory, reference with `@namespace/query` syntax.

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
profiles/duckdb/genie/
├── _meta.json
├── folfox-cohort.sql
├── kras-mutant.sql
└── braf-v600e.sql
```

---

## Meta File: `_meta.json`

Defines database connection and default options.

**Example:**
```json
{
  "driver": "duckdb",
  "path": "datasets/genie-crc/genie_crc.duckdb",
  "options": {
    "read_only": true
  },
  "description": "AACR Project GENIE CRC v2.0 cohort data"
}
```

**Fields:**
- `driver` - Always "duckdb"
- `path` - Path to .duckdb file (relative to profile dir or absolute)
- `options` - DuckDB connection options (read_only, etc.)
- `description` - Human-readable description

**Path resolution:**
- Relative paths: Resolve from profile directory
- Absolute paths: Use as-is
- Environment variables: `"${DATA_DIR}/genie.duckdb"`

---

## Query Files: `.sql`

SQL files with optional parameter placeholders and metadata comments.

**Example:** `profiles/duckdb/genie/folfox-cohort.sql`
```sql
-- FOLFOX-treated patients with survival outcomes
-- Parameters: none
SELECT
  patient_id,
  regimen,
  os_months,
  os_status
FROM treatments
WHERE regimen = 'Fluorouracil, Leucovorin Calcium, Oxaliplatin';
```

**With parameters:** `profiles/duckdb/genie/gene-mutant.sql`
```sql
-- Samples with mutations in a specific gene
-- Parameters: gene (required), mutation_type (optional)
SELECT DISTINCT
  s.sample_id,
  s.patient_id,
  m.hugo_symbol,
  m.variant_classification,
  m.hgvsp_short
FROM samples s
JOIN mutations m ON s.sample_id = m.sample_id
WHERE m.hugo_symbol = $gene
  AND ($mutation_type IS NULL OR m.variant_classification = $mutation_type);
```

**Parameter syntax:**
- DuckDB style: `$param_name` or `$1, $2, ...`
- Colon style: `:param_name` (converted to `$param_name`)

**Metadata comments:**
- First line: Description (after `--`)
- `Parameters:` line: List parameters with types/requirements

---

## Usage

### Basic Query
```bash
jn cat "@genie/folfox-cohort"
```

### Parameterized Query
```bash
jn cat "@genie/gene-mutant?gene=KRAS"
jn cat "@genie/gene-mutant?gene=BRAF&mutation_type=Missense_Mutation"
```

### Limit Results
```bash
jn cat "@genie/folfox-cohort?limit=100"
```

### Pipe to Other Commands
```bash
jn cat "@genie/folfox-cohort" | jn filter '.os_months > 50' | jn put survivors.csv
```

---

## Discovery

### List All Profiles
```bash
jn profile list --type duckdb
```
Output:
```
@genie/folfox-cohort       FOLFOX-treated patients with survival outcomes
@genie/kras-mutant         Samples with KRAS mutations
@genie/braf-v600e          Samples with BRAF V600E mutation
```

### Inspect Profile
```bash
jn inspect "@genie"
```
Output:
```json
{
  "profile": "@genie",
  "type": "duckdb",
  "database": "datasets/genie-crc/genie_crc.duckdb",
  "description": "AACR Project GENIE CRC v2.0 cohort data",
  "queries": [
    {
      "reference": "@genie/folfox-cohort",
      "description": "FOLFOX-treated patients with survival outcomes",
      "params": []
    },
    {
      "reference": "@genie/gene-mutant",
      "description": "Samples with mutations in a specific gene",
      "params": ["gene", "mutation_type"]
    }
  ]
}
```

### Inspect Database
```bash
jn inspect "duckdb://genie.duckdb"
```
Output:
```json
{
  "database": "genie.duckdb",
  "size_mb": 15.2,
  "tables": [
    {
      "name": "patients",
      "rows": 1486,
      "columns": ["patient_id", "sex", "age_at_seq", "race"]
    },
    {
      "name": "treatments",
      "rows": 5103,
      "columns": ["patient_id", "regimen", "os_months", "os_status"]
    }
  ]
}
```

---

## Implementation

### 1. Plugin Code

**Location:** `jn_home/plugins/databases/duckdb_.py`

**Improved implementation** (based on g2 team's work, refactored):

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["duckdb>=1.0.0"]
# [tool.jn]
# matches = ["^duckdb://.*", ".*\\.duckdb$", ".*\\.ddb$"]
# role = "protocol"
# ///

"""DuckDB plugin for JN - query analytical databases."""

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

import duckdb


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read from DuckDB database, yielding NDJSON records.

    Config keys:
        path: Database file path
        query: SQL query to execute
        params: Dict of bind parameters
        limit: Optional row limit
        profile_sql: SQL from profile file (takes precedence over query)
    """
    cfg = config or {}

    # Profile mode: SQL comes from .sql file
    if cfg.get("profile_sql"):
        db_path = cfg["db_path"]
        query = cfg["profile_sql"]
        params = cfg.get("params") or {}
    # Direct mode: Parse address
    else:
        raw_path = (
            cfg.get("path") or
            cfg.get("address") or
            cfg.get("url")
        )
        if not raw_path:
            raise ValueError("Database path required")

        db_path, query, params, table = _parse_address(str(raw_path))

        # Merge params from config
        user_params = cfg.get("params") or {}
        params = {**params, **user_params}

        # Override query from config
        if cfg.get("query"):
            query = cfg["query"]
        # Table shortcut: duckdb://db.duckdb/table_name
        elif table:
            query = f"SELECT * FROM {table}"

        if not query:
            raise ValueError(
                "SQL query required. Use:\n"
                "  duckdb://db.duckdb?query=SELECT * FROM table\n"
                "  duckdb://db.duckdb/table_name (shortcut)\n"
                "  jn cat '@profile/query'"
            )

    # Handle limit
    limit = cfg.get("limit")
    if limit:
        query = _apply_limit(query, limit)

    # Execute query
    conn = None
    try:
        conn = duckdb.connect(db_path, read_only=True)

        # Convert :param to $param for consistency
        query = query.replace(":", "$")

        # Execute with parameters
        cursor = conn.execute(query, params or None)
        columns = [col[0] for col in cursor.description]

        # Stream results
        row = cursor.fetchone()
        while row is not None:
            yield dict(zip(columns, row))
            row = cursor.fetchone()

    except duckdb.Error as e:
        raise RuntimeError(f"DuckDB error: {e}\nSQL: {query}") from e
    finally:
        if conn:
            conn.close()


def writes(config: Optional[dict] = None) -> None:
    """Write mode not yet supported."""
    raise NotImplementedError(
        "DuckDB writes not yet supported. Use DuckDB CLI for loading data."
    )


def _parse_address(address: str) -> Tuple[str, Optional[str], Dict[str, str], Optional[str]]:
    """Parse duckdb:// address into components.

    Formats:
        duckdb://path/to/file.duckdb?query=SELECT...&param=value
        duckdb://path/to/file.duckdb/table_name
        file.duckdb (plain file path)

    Returns:
        (db_path, query_sql, params, table_name)
    """
    if not address.startswith("duckdb://"):
        # Plain file path
        return address, None, {}, None

    parsed = urllib.parse.urlparse(address)
    raw_path = parsed.netloc + parsed.path
    query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    # Extract query
    query_sql = query_params.pop("query", [None])[0]

    # Extract params (everything except query and limit)
    limit = query_params.pop("limit", [None])[0]
    params = {
        key: values[-1]
        for key, values in query_params.items()
        if values
    }

    # Handle limit separately (converted to int by caller)
    if limit:
        params["limit"] = limit

    # Split db path and table name
    db_path, table = _split_db_and_table(raw_path)

    return db_path or "", query_sql, params, table


def _split_db_and_table(raw_path: str) -> Tuple[str, Optional[str]]:
    """Split path like 'db.duckdb/table' into ('db.duckdb', 'table')."""
    if not raw_path:
        return raw_path, None

    for ext in (".duckdb", ".ddb"):
        idx = raw_path.find(ext)
        if idx != -1:
            db_path = raw_path[:idx + len(ext)]
            suffix = raw_path[idx + len(ext):].lstrip("/")
            return db_path or raw_path, suffix or None

    return raw_path, None


def _apply_limit(query: str, limit: int) -> str:
    """Append LIMIT clause if not present."""
    if re.search(r"\bLIMIT\b", query, re.IGNORECASE):
        return query

    trimmed = query.rstrip().rstrip(";")
    return f"{trimmed} LIMIT {limit}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JN DuckDB plugin")
    parser.add_argument("--mode", required=True, choices=["read", "write"])
    parser.add_argument("--path", help="Database path or duckdb:// URL")
    parser.add_argument("--query", help="SQL query")
    parser.add_argument("--limit", type=int, help="Row limit")
    parser.add_argument("--db-path", help="Database path (for profile mode)")
    parser.add_argument("--profile-sql", help="SQL from profile file")
    parser.add_argument("address", nargs="?", help="Alternative to --path")

    # Parse --param-* arguments
    args, unknown = parser.parse_known_args()

    params = {}
    i = 0
    while i < len(unknown):
        if unknown[i].startswith("--param-"):
            param_name = unknown[i][8:]  # Strip '--param-'
            if i + 1 < len(unknown):
                params[param_name] = unknown[i + 1]
                i += 2
            else:
                sys.stderr.write(f"Missing value for {unknown[i]}\n")
                sys.exit(1)
        else:
            i += 1

    if args.mode == "write":
        sys.stderr.write("Write mode not supported\n")
        sys.exit(1)

    # Build config
    config = {"params": params}

    if args.profile_sql:
        # Profile mode
        config["profile_sql"] = args.profile_sql
        config["db_path"] = args.db_path or args.path or args.address
    else:
        # Direct mode
        config["path"] = args.path or args.address
        if args.query:
            config["query"] = args.query
        if args.limit:
            config["limit"] = args.limit

    # Execute
    try:
        for row in reads(config):
            print(json.dumps(row), flush=True)
    except (ValueError, RuntimeError) as e:
        sys.stderr.write(f"{e}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
```

**Key improvements:**
- Profile mode support via `profile_sql` config key
- Better error messages (includes SQL in error output)
- Unified parameter syntax (`:param` → `$param`)
- Cleaner argument parsing
- Table shortcuts: `duckdb://db/table` → `SELECT * FROM table`

---

### 2. Profile Service Changes

**File:** `src/jn/profiles/service.py`

**Add DuckDB profile scanning:**

```python
def list_all_profiles() -> List[ProfileInfo]:
    """Scan filesystem and load all profiles."""
    profiles = []

    for profile_root in _get_profile_paths():
        # ... existing JQ, Gmail, HTTP, MCP scanning ...

        # DuckDB profiles (NEW)
        duckdb_dir = profile_root / "duckdb"
        if duckdb_dir.exists():
            for sql_file in duckdb_dir.rglob("*.sql"):
                profile = _parse_duckdb_profile(sql_file, profile_root)
                if profile:
                    profiles.append(profile)

    return profiles


def _parse_duckdb_profile(sql_file: Path, profile_root: Path) -> Optional[ProfileInfo]:
    """Parse DuckDB .sql file into ProfileInfo.

    Extracts:
    - Description from first comment line
    - Parameters from comment or SQL body
    """
    content = sql_file.read_text()

    # Parse metadata from comments
    description = ""
    params = []

    for line in content.split("\n")[:20]:
        line = line.strip()

        # Description from first comment
        if line.startswith("--") and not description:
            desc = line.lstrip("-").strip()
            if desc and not desc.startswith("Parameters:"):
                description = desc

        # Parameters from "-- Parameters: x, y, z"
        if "-- Parameters:" in line:
            params_text = line.split("Parameters:", 1)[1].strip()
            # Parse "gene (required), mutation_type (optional)"
            params = [
                p.split("(")[0].strip()
                for p in params_text.split(",")
            ]
            break

    # If no explicit parameters, find $param or :param in SQL
    if not params:
        params = list(set(re.findall(r'[$:](\w+)', content)))

    # Build reference from path
    # profiles/duckdb/genie/folfox.sql → @genie/folfox
    rel_path = sql_file.relative_to(profile_root / "duckdb")
    parts = rel_path.with_suffix("").parts

    namespace = parts[0]
    name = "/".join(parts[1:]) if len(parts) > 1 else parts[0]

    return ProfileInfo(
        reference=f"@{namespace}/{name}",
        type="duckdb",
        namespace=namespace,
        name=name,
        path=sql_file,
        description=description,
        params=params
    )
```

---

### 3. Address Resolver Changes

**File:** `src/jn/addressing/resolver.py`

**Handle DuckDB profile resolution:**

```python
def _resolve_url_and_headers(
    self, address: Address, plugin_name: str
) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
    """Resolve URL and headers for address."""

    # ... existing protocol, file, stdio logic ...

    # DuckDB profiles (NEW)
    if address.type == "profile" and plugin_name == "duckdb_":
        from ..profiles.service import search_profiles

        # Find profile
        profiles = search_profiles(type_filter="duckdb")
        profile = next((p for p in profiles if p.reference == address.base), None)

        if not profile:
            raise AddressResolutionError(
                f"DuckDB profile not found: {address.base}\n"
                f"  Run 'jn profile list --type duckdb' to see available profiles"
            )

        # Load SQL from file
        sql_content = profile.path.read_text()

        # Load meta config
        meta_path = profile.path.parent.parent / "_meta.json"
        if not meta_path.exists():
            meta_path = profile.path.parent / "_meta.json"

        meta = json.loads(meta_path.read_text())
        db_path = meta.get("path")

        # Resolve relative paths
        if not Path(db_path).is_absolute():
            db_path = str(meta_path.parent / db_path)

        # Return special config for DuckDB plugin
        # (url field repurposed for profile data)
        return json.dumps({
            "profile_sql": sql_content,
            "db_path": db_path,
            "params": address.parameters
        }), None

    # ... rest of existing logic ...
```

**Actually, simpler approach:** Modify `_build_config` to handle profiles:

```python
def resolve(self, address: Address, mode: str = "read") -> ResolvedAddress:
    """Resolve address to plugin and configuration."""

    # ... existing plugin finding logic ...

    # Build configuration
    if address.type == "profile" and plugin_name == "duckdb_":
        config = self._build_duckdb_profile_config(address)
    else:
        config = self._build_config(address.parameters, plugin_name)

    # ... rest of existing logic ...


def _build_duckdb_profile_config(self, address: Address) -> Dict:
    """Build config for DuckDB profile."""
    from ..profiles.service import search_profiles

    # Find profile
    profiles = search_profiles(type_filter="duckdb")
    profile = next((p for p in profiles if p.reference == address.base), None)

    if not profile:
        raise AddressResolutionError(
            f"DuckDB profile not found: {address.base}\n"
            f"  Run 'jn profile list --type duckdb' to see available profiles"
        )

    # Load SQL
    sql_content = profile.path.read_text()

    # Load meta
    meta_path = profile.path.parent.parent / "_meta.json"
    if not meta_path.exists():
        meta_path = profile.path.parent / "_meta.json"

    meta = json.loads(meta_path.read_text())
    db_path = meta.get("path")

    # Resolve relative paths
    if not Path(db_path).is_absolute():
        db_path = str(meta_path.parent / db_path)

    return {
        "profile_sql": sql_content,
        "db_path": db_path,
        "params": address.parameters
    }
```

---

### 4. Inspect Command Changes

**File:** `src/jn/cli/commands/inspect.py`

**Add DuckDB support:**

```python
@click.command()
@click.argument("uri")
@click.option("--limit", default=100, help="Sample size for data inspection")
@click.option("--output-format", default="text", type=click.Choice(["json", "text"]))
@pass_context
def inspect(ctx, uri, limit, output_format):
    """Inspect resources: databases, profiles, data sources."""

    try:
        addr = parse_address(uri)

        # DuckDB database inspection (NEW)
        if addr.type == "protocol" and uri.startswith("duckdb://"):
            result = _inspect_duckdb_database(uri)
            if output_format == "json":
                click.echo(json.dumps(result, indent=2))
            else:
                _print_duckdb_database(result)
            return

        # DuckDB profile inspection (NEW)
        if addr.type == "profile" and addr.base.startswith("@"):
            # Check if it's a DuckDB profile
            from ...profiles.service import search_profiles
            profiles = search_profiles(type_filter="duckdb")
            profile = next((p for p in profiles if p.reference == addr.base), None)

            if profile:
                result = _inspect_duckdb_profile(addr.base)
                if output_format == "json":
                    click.echo(json.dumps(result, indent=2))
                else:
                    _print_duckdb_profile(result)
                return

        # ... existing inspection logic ...

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _inspect_duckdb_database(uri: str) -> dict:
    """Inspect DuckDB database: tables, schemas, row counts."""
    import duckdb

    # Parse path from duckdb://path.db
    path = uri.replace("duckdb://", "").split("?")[0]

    conn = duckdb.connect(path, read_only=True)

    # Get file size
    size_mb = round(Path(path).stat().st_size / (1024 * 1024), 1)

    # Get all tables
    tables = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
    """).fetchall()

    result = {
        "database": path,
        "size_mb": size_mb,
        "tables": []
    }

    for (table_name,) in tables:
        # Get row count
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        # Get column info
        cols = conn.execute(f"DESCRIBE {table_name}").fetchall()
        columns = [
            {"name": c[0], "type": c[1]}
            for c in cols[:10]  # First 10 columns
        ]

        result["tables"].append({
            "name": table_name,
            "rows": count,
            "columns": columns
        })

    conn.close()
    return result


def _inspect_duckdb_profile(reference: str) -> dict:
    """Inspect DuckDB profile: list queries, parameters."""
    from ...profiles.service import search_profiles

    # Get namespace from reference (@genie/query → genie)
    namespace = reference.lstrip("@").split("/")[0]

    # Get all queries for this namespace
    all_queries = search_profiles(type_filter="duckdb")
    queries = [q for q in all_queries if q.namespace == namespace]

    if not queries:
        raise ValueError(f"No DuckDB profile found: {reference}")

    # Load meta
    meta_path = queries[0].path.parent.parent / "_meta.json"
    if not meta_path.exists():
        meta_path = queries[0].path.parent / "_meta.json"

    meta = json.loads(meta_path.read_text())

    return {
        "profile": f"@{namespace}",
        "type": "duckdb",
        "database": meta.get("path"),
        "description": meta.get("description", ""),
        "queries": [
            {
                "reference": q.reference,
                "description": q.description,
                "params": q.params
            }
            for q in queries
        ]
    }


def _print_duckdb_database(result: dict):
    """Pretty-print database inspection."""
    click.echo(f"\nDatabase: {result['database']} ({result['size_mb']} MB)\n")
    click.echo("Tables:")

    for table in result["tables"]:
        cols_str = ", ".join(c["name"] for c in table["columns"][:5])
        if len(table["columns"]) > 5:
            cols_str += ", ..."

        click.echo(f"  {table['name']:<20} {table['rows']:>8,} rows    {cols_str}")

    click.echo(f"\nRun: jn cat \"duckdb://{result['database']}/table_name\"")


def _print_duckdb_profile(result: dict):
    """Pretty-print profile inspection."""
    click.echo(f"\nProfile: {result['profile']} (DuckDB)")
    click.echo(f"Database: {result['database']}")

    if result.get('description'):
        click.echo(f"\n{result['description']}")

    click.echo("\nAvailable queries:")
    for q in result['queries']:
        params_str = f" ({', '.join(q['params'])})" if q['params'] else ""
        click.echo(f"  {q['reference']:<30} {q['description']}{params_str}")

    click.echo(f"\nRun: jn cat \"{result['queries'][0]['reference']}\"")
```

---

## Testing Plan

### Unit Tests

**File:** `tests/plugins/test_duckdb_plugin.py`

```python
import pytest
from pathlib import Path

def test_parse_duckdb_url():
    """Test URL parsing."""
    from jn_home.plugins.databases.duckdb_ import _parse_address

    path, query, params, table = _parse_address(
        "duckdb://test.duckdb?query=SELECT * FROM users&limit=10"
    )
    assert path == "test.duckdb"
    assert query == "SELECT * FROM users"
    assert params == {"limit": "10"}
    assert table is None


def test_table_shortcut():
    """Test table shortcut syntax."""
    from jn_home.plugins.databases.duckdb_ import _parse_address

    path, query, params, table = _parse_address("duckdb://test.duckdb/users")
    assert path == "test.duckdb"
    assert query is None
    assert table == "users"


def test_profile_mode(tmp_path):
    """Test profile-based query."""
    from jn_home.plugins.databases.duckdb_ import reads
    import duckdb

    # Create test database
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE TABLE users (id INT, name VARCHAR)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob')")
    conn.close()

    # Read via profile mode
    config = {
        "profile_sql": "SELECT * FROM users WHERE id = $user_id",
        "db_path": str(db_path),
        "params": {"user_id": "1"}
    }

    results = list(reads(config))
    assert len(results) == 1
    assert results[0]["name"] == "Alice"
```

### Integration Tests

**File:** `tests/cli/test_duckdb_profiles.py`

```python
import pytest
import json
from pathlib import Path

@pytest.fixture
def profile_setup(tmp_path):
    """Create test profile structure."""
    import duckdb

    # Create database
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE TABLE users (id INT, name VARCHAR, age INT)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice', 30), (2, 'Bob', 25)")
    conn.close()

    # Create profile
    profile_dir = tmp_path / ".jn" / "profiles" / "duckdb" / "testdb"
    profile_dir.mkdir(parents=True)

    # Meta file
    meta = {
        "driver": "duckdb",
        "path": str(db_path),
        "description": "Test database"
    }
    (profile_dir.parent / "_meta.json").write_text(json.dumps(meta))

    # SQL query
    (profile_dir / "all-users.sql").write_text(
        "-- All users\nSELECT * FROM users"
    )
    (profile_dir / "by-age.sql").write_text(
        "-- Users by age\nSELECT * FROM users WHERE age >= $min_age"
    )

    return tmp_path


def test_profile_list(profile_setup):
    """Test profile discovery."""
    from subprocess import run

    result = run(
        ["jn", "profile", "list", "--type", "duckdb"],
        cwd=profile_setup,
        capture_output=True,
        text=True
    )

    assert "@testdb/all-users" in result.stdout
    assert "@testdb/by-age" in result.stdout


def test_profile_cat(profile_setup):
    """Test profile-based query."""
    from subprocess import run

    result = run(
        ["jn", "cat", "@testdb/all-users"],
        cwd=profile_setup,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 2

    row1 = json.loads(lines[0])
    assert row1["name"] in ["Alice", "Bob"]


def test_profile_with_params(profile_setup):
    """Test parameterized query."""
    from subprocess import run

    result = run(
        ["jn", "cat", "@testdb/by-age?min_age=26"],
        cwd=profile_setup,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 1

    row = json.loads(lines[0])
    assert row["name"] == "Alice"
    assert row["age"] == 30
```

---

## Migration Guide (for g2 team)

### Current Setup (URL-encoded)
```bash
jn cat "duckdb://genie.duckdb?query=SELECT%20patient_id%20FROM%20treatments%20WHERE%20regimen%20LIKE%20'%25FOLFOX%25'"
```

### New Setup (Profiles)

**1. Create profile directory:**
```bash
mkdir -p .jn/profiles/duckdb/genie
```

**2. Create meta file:** `.jn/profiles/duckdb/genie/_meta.json`
```json
{
  "driver": "duckdb",
  "path": "datasets/genie-crc/genie_crc.duckdb",
  "options": {"read_only": true},
  "description": "AACR Project GENIE CRC v2.0"
}
```

**3. Create query files:** `.jn/profiles/duckdb/genie/folfox-cohort.sql`
```sql
-- FOLFOX-treated patients with survival outcomes
SELECT
  patient_id,
  regimen,
  os_months,
  os_status
FROM treatments
WHERE regimen = 'Fluorouracil, Leucovorin Calcium, Oxaliplatin';
```

**4. Use the profile:**
```bash
jn cat "@genie/folfox-cohort"
jn cat "@genie/folfox-cohort" | jn filter '.os_months > 50'
jn cat "@genie/folfox-cohort?limit=100"
```

---

## Success Metrics

- ✅ `jn cat "@namespace/query"` works
- ✅ `jn profile list --type duckdb` shows all queries
- ✅ `jn inspect "@namespace"` shows query details
- ✅ `jn inspect "duckdb://file.duckdb"` shows tables
- ✅ Parameterized queries work with `?param=value`
- ✅ Error messages include SQL and helpful suggestions
- ✅ All tests pass

---

## Out of Scope

- DuckDB write support (use DuckDB CLI for data loading)
- Query builder UI
- Schema migrations
- Multi-database profiles (one DB per profile for now)
- DuckDB extensions (use defaults)

---

## Future Enhancements

1. **Write support:** `jn cat data.csv | jn put "duckdb://db.duckdb/table"`
2. **Query builder:** Interactive query construction
3. **Schema inspector:** Visual schema explorer
4. **Profile templates:** Generate profiles from existing databases
5. **Multi-DB profiles:** Single profile spanning multiple databases
