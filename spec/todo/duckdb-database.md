# DuckDB Database Plugin

**Status:** Superseded by comprehensive spec
**See:** `duckdb-profiles.md` (full spec) and `duckdb-implementation-guide.md` (developer guide)

---

## Overview

Query DuckDB analytical databases with SQL-based profiles.

**Instead of:**
```bash
jn cat "duckdb://db.duckdb?query=SELECT%20..."
```

**Use:**
```bash
jn cat "@namespace/query"
```

---

## Quick Reference

### Profile Structure
```
.jn/profiles/duckdb/namespace/
├── _meta.json          # Database connection
└── query.sql           # Named SQL queries
```

### Examples
```bash
# Simple query
jn cat "@analytics/sales-summary"

# With parameters
jn cat "@analytics/by-region?region=West"

# List profiles
jn profile list --type duckdb

# Inspect database
jn inspect "duckdb://data.duckdb"

# Inspect profile
jn inspect "@analytics"
```

---

## Full Documentation

**Comprehensive spec:** `duckdb-profiles.md`
- Profile structure and usage
- Plugin implementation (complete code)
- Profile service integration
- Inspect support
- Full test suite

**Implementation guide:** `duckdb-implementation-guide.md`
- Phase-by-phase implementation plan (7 days)
- Testing checklist
- Debugging tips
- Migration guide for g2 team

---

## Status

- Plugin code: ✅ Ready (in duckdb-profiles.md spec)
- Profile support: 📝 Design complete, needs implementation
- Inspect: 📝 Design complete, needs implementation
- Tests: 📝 Spec written, needs implementation
- Documentation: 📝 In progress

**Estimated implementation:** 4-7 days
