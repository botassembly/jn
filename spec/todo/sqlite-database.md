# SQLite Database Plugin

## What
Query local SQLite databases with named SQL queries and parameters. Serverless, perfect for local data processing.

## Why
SQLite is everywhere (iOS, Android, browsers, local apps). Enable SQL queries in pipelines with reusable named queries.

## Key Features
- Execute SQL queries, return NDJSON results
- Named queries from profile `.sql` files
- Parameterized queries (NULL-safe optional filters)
- Direct table access (`mydb.sqlite/tablename`)
- Streaming (cursor-based, constant memory)

## Dependencies
- `aiosql` (query manager)
- `sqlite3` (built into Python)

## Profile Structure
**Config:** `profiles/sqlite/mydb.json`
```json
{
  "driver": "sqlite",
  "path": "/path/to/database.db",
  "options": {"read_only": true}
}
```

**Named query:** `profiles/sqlite/mydb/active-users.sql`
```sql
SELECT user_id, name, email FROM users
WHERE active = 1 AND (:dept IS NULL OR dept = :dept)
LIMIT :limit
```

## Examples
```bash
# Direct table access
jn cat mydb.sqlite/users | jn filter '.active == true'

# Named query with parameters
jn cat @mydb/active-users.sql --limit 10 --dept engineering | jn put results.csv

# Pipeline
jn cat @mydb/sales.sql --year 2024 | jn filter '.revenue > 10000' | jn jtbl
```

## Out of Scope
- Writing (INSERT/UPDATE/DELETE) - add later
- Schema management - use sqlite3 CLI
