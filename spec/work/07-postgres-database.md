# PostgreSQL Database Plugin

## Overview
Implement a separate database plugin for PostgreSQL using aiosql. PostgreSQL is the primary production database target, with features like connection pooling, remote access, and advanced SQL capabilities.

## Goals
- Connect to PostgreSQL databases (local or remote)
- Execute SQL queries and return results as NDJSON
- Support named queries from profile files (`.sql` files)
- Handle parameterized queries with CLI arguments
- Support connection pooling for performance
- Stream results row-by-row (server-side cursor)

## Resources
**Public PostgreSQL Databases (for testing):**
- Use Docker: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=test postgres:16`
- Chinook Database PostgreSQL version: https://github.com/lerocha/chinook-database
- Create local test database:
  ```bash
  createdb testdb
  psql testdb << EOF
  CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT, email TEXT, active BOOLEAN, dept TEXT, created_at TIMESTAMP DEFAULT NOW());
  INSERT INTO users (name, email, active, dept) VALUES ('Alice', 'alice@example.com', true, 'engineering');
  INSERT INTO users (name, email, active, dept) VALUES ('Bob', 'bob@example.com', true, 'sales');
  INSERT INTO users (name, email, active, dept) VALUES ('Charlie', 'charlie@example.com', false, 'engineering');
  EOF
  ```

## Dependencies
**Python packages:**
- `aiosql` - SQL query manager (same as SQLite)
- `psycopg2-binary` - PostgreSQL driver (binary version, no compile)

Add to PEP 723 dependencies:
```toml
dependencies = ["aiosql>=9.0", "psycopg2-binary>=2.9.0"]
```

**Note:** Use `psycopg2-binary` (pre-compiled) not `psycopg2` (requires compilation).

**Alternative:** `asyncpg` for async support (later optimization)

## Technical Approach
- Implement `reads()` function to query database
- Pattern matching: None (profile-based only, no file extension)
- Connection string from profile config
- Use server-side cursor (`name='cursor_name'`) for streaming
- Return each row as dict with column names as keys
- Support SQL parameters: `:param` syntax (aiosql converts to PostgreSQL format)
- Load queries from `.sql` files in profiles
- Close connections properly (context managers)

## Profile Structure

**Database config:** `profiles/postgres/proddb.json`
```json
{
  "driver": "postgresql",
  "connection": "postgresql://user:${DB_PASSWORD}@localhost:5432/mydb",
  "options": {
    "pool_size": 5,
    "timeout": 30,
    "sslmode": "prefer",
    "application_name": "jn"
  }
}
```

**Named query:** `profiles/postgres/proddb/active-users.sql`
```sql
-- Get active users with optional filters
SELECT user_id, name, email, dept, created_at
FROM users
WHERE active = true
  AND (:dept IS NULL OR dept = :dept)
  AND (:min_id IS NULL OR user_id >= :min_id)
ORDER BY created_at DESC
LIMIT :limit OFFSET :offset
```

## Usage Examples

```bash
# Named query from profile
jn cat @proddb/active-users.sql --limit 10 | jn put active.csv

# With parameters
jn cat @proddb/active-users.sql --limit 100 --dept engineering --min-id 1000 | jn filter '.email =~ "gmail"'

# Direct SQL (future)
jn cat @proddb --query "SELECT * FROM users WHERE active = true LIMIT 10" | jn put users.json

# Pipeline with aggregation
jn cat @proddb/sales-data.sql --year 2024 | jn filter '.revenue > 10000' | jn put high-value.csv

# Environment variable substitution
export DB_PASSWORD=secret123
jn cat @proddb/active-users.sql --limit 10  # Uses password from env
```

## Connection Management
- Parse connection string, substitute `${ENV_VAR}` variables
- Create connection pool (don't reconnect per query)
- Use server-side cursor for large result sets
- Set `cursor_name` to enable streaming
- Close cursor and connection in finally block
- Handle connection errors gracefully

## Parameter Handling
Same as SQLite - NULL-safe parameters:
```sql
WHERE (:dept IS NULL OR dept = :dept)
```

aiosql converts `:param` syntax to PostgreSQL `%s` placeholders automatically.

## Out of Scope
- Writing to database (INSERT/UPDATE/DELETE) - add later
- Multiple simultaneous connections - one at a time
- Transactions and ACID properties - read-only for now
- Schema migrations - use Alembic/Flyway
- Replication and high availability - PostgreSQL concern
- Connection pooling optimization - basic pool only
- Prepared statements - let psycopg2 handle
- COPY command (bulk loading) - use psql directly
- Logical replication - out of scope
- Extensions (PostGIS, etc.) - works if installed
- PgBouncer integration - connection string handles it

## Security Considerations
- Never log connection strings (contain passwords)
- Use environment variables for credentials: `${DB_PASSWORD}`
- Validate SQL parameter types (prevent injection)
- Read-only user recommended
- SSL/TLS preferred (sslmode=prefer)

## Success Criteria
- Can connect to PostgreSQL databases
- Can execute queries with parameters
- Streams results (server-side cursor)
- Named queries load from profile `.sql` files
- Environment variable substitution works
- NULL-safe parameters work correctly
- Works in pipelines with filters
- Clear error messages for connection/SQL errors
- Connection pooling improves performance

## Differences from SQLite Plugin
| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Driver | `sqlite3` (built-in) | `psycopg2-binary` |
| Pattern matching | File extensions | Profile-based only |
| Connection | File path | Connection string |
| Cursor | Simple fetch | Server-side cursor |
| Pooling | N/A (file-based) | Connection pool |
| Authentication | None | User/password |
| Remote access | No | Yes |

## Implementation Note
SQLite and PostgreSQL plugins are **separate files** because:
- Different dependencies (psycopg2 vs sqlite3)
- Different connection handling
- Different cursor behavior
- Different pattern matching
- Users may only need one or the other

Both use aiosql for query management (shared interface).
