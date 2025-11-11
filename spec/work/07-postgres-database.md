# PostgreSQL Database Plugin

## What
Query remote PostgreSQL databases with named SQL queries, connection pooling, and environment variable substitution.

## Why
PostgreSQL is the standard production database. Enable SQL queries against remote databases with secure credential management.

## Key Features
- Remote database connections (connection strings)
- Named queries from profile `.sql` files
- Parameterized queries (NULL-safe optional filters)
- Server-side cursors for streaming (constant memory)
- Connection pooling
- Environment variable substitution for secrets (`${DB_PASSWORD}`)

## Dependencies
- `aiosql` (query manager, same as SQLite)
- `psycopg2-binary` (PostgreSQL driver)

## Profile Structure
**Config:** `profiles/postgres/proddb.json`
```json
{
  "driver": "postgresql",
  "connection": "postgresql://user:${DB_PASSWORD}@host:5432/db",
  "options": {
    "pool_size": 5,
    "sslmode": "prefer"
  }
}
```

**Named query:** `profiles/postgres/proddb/active-users.sql`
```sql
SELECT user_id, name, email FROM users
WHERE active = true AND (:dept IS NULL OR dept = :dept)
LIMIT :limit
```

## Examples
```bash
# Named query with parameters
export DB_PASSWORD=secret
jn cat @proddb/active-users.sql --limit 10 --dept engineering | jn put results.csv

# Pipeline
jn cat @proddb/sales.sql --year 2024 | jn filter '.revenue > 10000' | jn jtbl
```

## Security
- Never log connection strings
- Use environment variables for passwords
- Prefer SSL/TLS connections
- Read-only user recommended

## Out of Scope
- Writing (INSERT/UPDATE/DELETE) - add later
- Schema migrations - use Alembic/Flyway
