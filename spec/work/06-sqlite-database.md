# SQLite Database Plugin

## Overview
Implement a database plugin for SQLite using aiosql for query management. SQLite is serverless and perfect for local data processing, testing, and single-user applications.

## Goals
- Read from SQLite database files
- Execute SQL queries and return results as NDJSON
- Support named queries from profile files (`.sql` files)
- Handle parameterized queries with CLI arguments
- Support direct table access (`@dbfile/tablename`)
- Stream results row-by-row (cursor-based)

## Resources
**Sample SQLite Databases:**
- Chinook Database (music store): https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite
- Northwind Database (classic sample): https://github.com/jpwhite3/northwind-SQLite3/raw/master/dist/northwind.db
- Create test database:
  ```bash
  sqlite3 test.db << EOF
  CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, active INTEGER);
  INSERT INTO users VALUES (1, 'Alice', 'alice@example.com', 1);
  INSERT INTO users VALUES (2, 'Bob', 'bob@example.com', 1);
  INSERT INTO users VALUES (3, 'Charlie', 'charlie@example.com', 0);
  EOF
  ```

## Dependencies
**Python packages:**
- `aiosql` - SQL query manager (supports multiple databases)
- `sqlite3` - Built into Python (no extra install)

Add to PEP 723 dependencies:
```toml
dependencies = ["aiosql>=9.0"]
```

**Note:** aiosql is synchronous for SQLite (async only needed for async drivers).

## Technical Approach
- Implement `reads()` function to query database
- Pattern matching: `.*\\.db$`, `.*\\.sqlite$`, `.*\\.sqlite3$`
- Open database in read-only mode
- Use cursor with `arraysize` for streaming
- Return each row as dict with column names as keys
- Support SQL parameters: `:param` syntax
- Load queries from `.sql` files in profiles

## Profile Structure

**Database config:** `profiles/sqlite/mydb.json`
```json
{
  "driver": "sqlite",
  "path": "/path/to/database.db",
  "options": {
    "read_only": true,
    "timeout": 30
  }
}
```

**Named query:** `profiles/sqlite/mydb/active-users.sql`
```sql
-- Get active users with optional filters
SELECT user_id, name, email, created_at
FROM users
WHERE active = 1
  AND (:dept IS NULL OR dept = :dept)
  AND (:min_id IS NULL OR user_id >= :min_id)
ORDER BY created_at DESC
LIMIT :limit OFFSET :offset
```

## Usage Examples

```bash
# Direct table access
jn cat mydb.sqlite/users | jn put users.json

# Named query from profile
jn cat @mydb/active-users.sql --limit 10 | jn put active.csv

# With parameters
jn cat @mydb/active-users.sql --limit 10 --dept engineering | jn filter '.email =~ "gmail"'

# SQL query inline (future)
jn cat mydb.sqlite --query "SELECT * FROM users WHERE active = 1" | jn put active.json

# Pipeline with filters
jn cat @mydb/active-users.sql | jn filter '.created_at > "2024-01-01"' | jn put recent.csv
```

## Parameter Handling
Support NULL-safe parameters for optional filters:
```sql
-- If :dept not provided, condition becomes (NULL IS NULL OR ...) = TRUE
-- If :dept = 'engineering', condition becomes ('engineering' IS NULL OR ...) = FALSE OR dept = 'engineering'
WHERE (:dept IS NULL OR dept = :dept)
```

CLI arguments map to SQL parameters:
- `--limit 10` → `:limit = 10`
- `--offset 20` → `:offset = 20`
- `--dept engineering` → `:dept = 'engineering'`

## Out of Scope
- Writing to database (INSERT/UPDATE/DELETE) - add later
- Schema introspection - use SQL tools
- Multiple database connections - one at a time
- Transactions - read-only for now
- Foreign key constraints - SQLite concern
- Full-text search (FTS) - use SQL directly
- Vacuum, analyze, optimize - use sqlite3 CLI
- WAL mode configuration - use defaults
- Encryption (SQLCipher) - add later if needed
- In-memory databases (`:memory:`) - file-based only
- Concurrent writes - read-only mode prevents issues

## Success Criteria
- Can read from SQLite database files
- Can execute queries with parameters
- Streams results (constant memory for large result sets)
- Named queries load from profile `.sql` files
- NULL-safe parameters work correctly
- Works in pipelines with filters
- Clear error messages for SQL errors
- Table names resolve correctly

## Next Steps
After SQLite works:
1. Create similar plugin for PostgreSQL (separate plugin)
2. Both use aiosql for query management
3. PostgreSQL requires `psycopg2` or `asyncpg` dependency
4. Profile configs specify driver type
