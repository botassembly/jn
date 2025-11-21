# DuckDB Implementation Guide

**For:** Developer implementing DuckDB profile system
**Time estimate:** 4-7 days
**Prerequisites:** Read `duckdb-profiles.md` first

---

## Implementation Order

### Phase 1: Plugin Migration (Day 1)

**Goal:** Get basic DuckDB plugin working in main JN repo

**Tasks:**
1. Copy improved plugin code from `duckdb-profiles.md` spec
2. Place in: `jn_home/plugins/databases/duckdb_.py`
3. Make executable: `chmod +x jn_home/plugins/databases/duckdb_.py`
4. Test basic queries work

**Test:**
```bash
# Create test database
duckdb test.duckdb << EOF
CREATE TABLE users (id INT, name VARCHAR);
INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob');
EOF

# Test direct queries
jn cat "duckdb://test.duckdb/users"
jn cat "duckdb://test.duckdb?query=SELECT * FROM users WHERE id = 1"
```

**Files changed:**
- `jn_home/plugins/databases/duckdb_.py` (new)

**Acceptance:** Basic queries work, plugin discovered by JN

---

### Phase 2: Profile Service (Day 2)

**Goal:** Discover and parse .sql profile files

**Tasks:**
1. Add `_parse_duckdb_profile()` to `src/jn/profiles/service.py`
2. Add DuckDB scanning to `list_all_profiles()`
3. Test profile discovery

**Test:**
```bash
# Create test profile
mkdir -p .jn/profiles/duckdb/test
cat > .jn/profiles/duckdb/test/_meta.json << 'EOF'
{
  "driver": "duckdb",
  "path": "test.duckdb",
  "description": "Test database"
}
EOF

cat > .jn/profiles/duckdb/test/all-users.sql << 'EOF'
-- All users
SELECT * FROM users;
EOF

# Test discovery
jn profile list --type duckdb
# Should show: @test/all-users
```

**Files changed:**
- `src/jn/profiles/service.py` (add ~50 lines)

**Acceptance:** `jn profile list --type duckdb` shows .sql files

---

### Phase 3: Address Resolution (Day 3)

**Goal:** Resolve `@namespace/query` to DuckDB plugin config

**Tasks:**
1. Add `_build_duckdb_profile_config()` to `src/jn/addressing/resolver.py`
2. Call it from `resolve()` when profile type is duckdb
3. Pass config to DuckDB plugin

**Test:**
```bash
# Using profile from Phase 2
jn cat "@test/all-users"
# Should output NDJSON

jn cat "@test/all-users?limit=1"
# Should output 1 row
```

**Files changed:**
- `src/jn/addressing/resolver.py` (add ~40 lines)

**Acceptance:** `jn cat "@namespace/query"` executes SQL and returns NDJSON

---

### Phase 4: Parameterized Queries (Day 4)

**Goal:** Support query parameters via URL params

**Tasks:**
1. Update profile config to pass params
2. Test parameter binding

**Test:**
```bash
# Create parameterized query
cat > .jn/profiles/duckdb/test/by-id.sql << 'EOF'
-- User by ID
-- Parameters: user_id
SELECT * FROM users WHERE id = $user_id;
EOF

# Test with parameter
jn cat "@test/by-id?user_id=1"
# Should return Alice

jn cat "@test/by-id?user_id=2"
# Should return Bob
```

**Files changed:**
- None (should work from Phase 3)

**Acceptance:** Parameterized queries work with `?param=value`

---

### Phase 5: Inspect Database (Day 5)

**Goal:** Show tables/schemas when inspecting DuckDB files

**Tasks:**
1. Add `_inspect_duckdb_database()` to `src/jn/cli/commands/inspect.py`
2. Wire into `inspect()` command
3. Add pretty-printing

**Test:**
```bash
jn inspect "duckdb://test.duckdb"
# Should show:
# Database: test.duckdb
# Tables:
#   users    2 rows    id, name
```

**Files changed:**
- `src/jn/cli/commands/inspect.py` (add ~80 lines)

**Acceptance:** `jn inspect "duckdb://file.duckdb"` shows tables and row counts

---

### Phase 6: Inspect Profile (Day 6)

**Goal:** Show queries when inspecting profiles

**Tasks:**
1. Add `_inspect_duckdb_profile()` to `src/jn/cli/commands/inspect.py`
2. Wire into `inspect()` command
3. Add pretty-printing

**Test:**
```bash
jn inspect "@test"
# Should show:
# Profile: @test (DuckDB)
# Database: test.duckdb
# Available queries:
#   @test/all-users    All users
#   @test/by-id        User by ID (user_id)
```

**Files changed:**
- `src/jn/cli/commands/inspect.py` (add ~60 lines)

**Acceptance:** `jn inspect "@namespace"` shows available queries

---

### Phase 7: Tests & Documentation (Day 7)

**Goal:** Full test coverage and documentation

**Tasks:**
1. Write unit tests (`tests/plugins/test_duckdb_plugin.py`)
2. Write integration tests (`tests/cli/test_duckdb_profiles.py`)
3. Update README with DuckDB examples
4. Update CLAUDE.md with profile instructions

**Test:**
```bash
make test
# All tests pass

make coverage
# DuckDB code covered
```

**Files changed:**
- `tests/plugins/test_duckdb_plugin.py` (new, ~100 lines)
- `tests/cli/test_duckdb_profiles.py` (new, ~150 lines)
- `README.md` (add examples)
- `CLAUDE.md` (add DuckDB section)

**Acceptance:** Tests pass, documentation complete

---

## Key Code Locations

### Plugin
```
jn_home/plugins/databases/duckdb_.py
```
- `reads(config)` - Main read function
- `_parse_address(address)` - Parse duckdb:// URLs
- `_apply_limit(query, limit)` - Add LIMIT clause

### Profile Service
```
src/jn/profiles/service.py
```
- `_parse_duckdb_profile(sql_file, profile_root)` - Parse .sql files
- `list_all_profiles()` - Add DuckDB scanning

### Address Resolver
```
src/jn/addressing/resolver.py
```
- `_build_duckdb_profile_config(address)` - Build plugin config from profile
- `resolve(address, mode)` - Call DuckDB config builder

### Inspect Command
```
src/jn/cli/commands/inspect.py
```
- `_inspect_duckdb_database(uri)` - Show database tables
- `_inspect_duckdb_profile(reference)` - Show profile queries
- `inspect(uri, ...)` - Route to appropriate inspector

---

## Common Patterns

### Profile Config Flow

```
User: jn cat "@genie/folfox"
  ↓
Address Parser: parse_address("@genie/folfox")
  ↓ Address(type="profile", base="@genie/folfox", ...)
  ↓
Address Resolver: resolve(address)
  ↓ Calls _build_duckdb_profile_config(address)
    → Loads genie/folfox.sql
    → Loads genie/_meta.json
    → Returns config dict
  ↓
DuckDB Plugin: reads(config)
  ↓ config["profile_sql"] = "SELECT ..."
  ↓ config["db_path"] = "datasets/..."
  ↓ config["params"] = {}
  ↓
  ↓ conn = duckdb.connect(db_path)
  ↓ cursor = conn.execute(sql, params)
  ↓ yield rows as dicts
  ↓
NDJSON output
```

### File Path Resolution

**Profile paths:**
- `.jn/profiles/duckdb/` (project, highest priority)
- `~/.local/jn/profiles/duckdb/` (user)
- `jn_home/profiles/duckdb/` (bundled, lowest)

**Database paths in _meta.json:**
- Relative: Resolved from profile directory
- Absolute: Used as-is
- Environment vars: `"${DATA_DIR}/db.duckdb"`

### Error Handling

**Plugin errors:**
```python
except duckdb.Error as e:
    raise RuntimeError(f"DuckDB error: {e}\nSQL: {query}") from e
```

**Profile not found:**
```python
if not profile:
    raise AddressResolutionError(
        f"DuckDB profile not found: {address.base}\n"
        f"  Run 'jn profile list --type duckdb' to see available profiles"
    )
```

**Missing parameters:**
```python
if not db_path:
    raise ValueError(
        "Database path required. Use:\n"
        "  duckdb://db.duckdb?query=SELECT...\n"
        "  jn cat '@profile/query'"
    )
```

---

## Testing Checklist

### Unit Tests
- [ ] `_parse_address()` parses all URL formats
- [ ] `_split_db_and_table()` handles .duckdb and .ddb
- [ ] `_apply_limit()` appends LIMIT correctly
- [ ] `reads()` executes simple queries
- [ ] `reads()` executes parameterized queries
- [ ] `reads()` handles profile mode

### Integration Tests
- [ ] `jn cat "duckdb://db/table"` works
- [ ] `jn cat "duckdb://db?query=..."` works
- [ ] `jn profile list --type duckdb` shows profiles
- [ ] `jn cat "@namespace/query"` works
- [ ] `jn cat "@namespace/query?param=value"` works
- [ ] `jn inspect "duckdb://db"` shows tables
- [ ] `jn inspect "@namespace"` shows queries

### Edge Cases
- [ ] Empty database (0 tables)
- [ ] Query with no results
- [ ] Invalid SQL (error message includes SQL)
- [ ] Missing parameter (helpful error)
- [ ] Profile not found (suggests `jn profile list`)
- [ ] Database not found (clear error)

---

## Debugging Tips

### Enable verbose output
```bash
export JN_DEBUG=1
jn cat "@test/query"
```

### Test plugin directly
```bash
uv run jn_home/plugins/databases/duckdb_.py \
  --mode read \
  --path test.duckdb \
  --query "SELECT * FROM users"
```

### Check profile discovery
```python
from jn.profiles.service import list_all_profiles

profiles = list_all_profiles()
duckdb_profiles = [p for p in profiles if p.type == "duckdb"]
print(duckdb_profiles)
```

### Inspect plugin config
```python
from jn.addressing import parse_address, AddressResolver
from pathlib import Path

addr = parse_address("@test/query")
resolver = AddressResolver(Path(".jn/plugins"))
resolved = resolver.resolve(addr, mode="read")
print(resolved.config)
```

---

## Common Issues

### Profile not found
**Symptom:** `DuckDB profile not found: @namespace/query`

**Fix:**
1. Check `.jn/profiles/duckdb/namespace/` exists
2. Check `query.sql` file exists
3. Run `jn profile list --type duckdb` to verify

### Database path not resolved
**Symptom:** `No such file: datasets/db.duckdb`

**Fix:**
1. Check `_meta.json` has correct path
2. Ensure relative paths resolve from profile directory
3. Use absolute path if needed

### Parameter not bound
**Symptom:** `Bind parameter not found: $param_name`

**Fix:**
1. Check query uses `$param_name` (not `:param_name`)
2. Check parameter passed in URL: `?param_name=value`
3. Verify plugin receives params in config

### SQL syntax error
**Symptom:** `Parser Error: syntax error`

**Fix:**
1. Check error message includes SQL
2. Test SQL in DuckDB CLI first
3. Check parameter syntax ($param not :param)

---

## Performance Notes

### Streaming is Critical
- Plugin uses `fetchone()` not `fetchall()`
- Memory stays constant regardless of result size
- First row appears immediately

### Connection Management
- Always `conn.close()` in finally block
- Read-only mode for safety
- Single connection per query

### Profile Discovery
- Fast: ~4ms for 50 profiles
- No caching needed until >1000 profiles
- Scans all .sql files on each `jn profile list`

---

## Handoff to g2 Team

### What They Get
1. ✅ Working DuckDB plugin in main JN repo
2. ✅ Profile system for SQL queries
3. ✅ Inspect command for databases and profiles
4. ✅ Full documentation and examples

### Migration Path
**Old (URL-encoded):**
```bash
jn cat "duckdb://db?query=SELECT%20..."
```

**New (profiles):**
```bash
# One-time setup
mkdir -p .jn/profiles/duckdb/genie
cat > .jn/profiles/duckdb/genie/_meta.json << EOF
{"driver": "duckdb", "path": "datasets/genie.duckdb"}
EOF

cat > .jn/profiles/duckdb/genie/folfox.sql << EOF
SELECT * FROM treatments WHERE regimen LIKE '%FOLFOX%';
EOF

# Use forever
jn cat "@genie/folfox"
```

### Support
- Documentation: `spec/todo/duckdb-profiles.md`
- Examples: `README.md` (after Phase 7)
- Tests: `tests/cli/test_duckdb_profiles.py`
- Questions: Open GitHub issue

---

## Success Criteria

**Phase 1-3 (MVP):**
- ✅ Plugin works with basic queries
- ✅ Profiles discovered and executed
- ✅ `jn cat "@namespace/query"` returns NDJSON

**Phase 4-6 (Full):**
- ✅ Parameters work
- ✅ Inspect shows databases
- ✅ Inspect shows profiles

**Phase 7 (Production):**
- ✅ All tests pass
- ✅ Documentation complete
- ✅ G2 team can migrate

---

## Next Steps

1. Read `duckdb-profiles.md` completely
2. Start with Phase 1 (plugin migration)
3. Test each phase before moving to next
4. Ask questions early (don't guess)
5. Keep changes small and focused

**Estimated time:** 4-7 days depending on familiarity with codebase

**Questions?** Review spec first, then ask.
