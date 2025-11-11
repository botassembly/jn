# DuckDB Database Plugin

## What
Query DuckDB analytical database for OLAP workloads. In-process SQL engine optimized for analytics, can query Parquet/CSV directly.

## Why
DuckDB is perfect for analytical queries, data science workflows, and processing large datasets. Complements PostgreSQL (OLTP) and SQLite (embedded).

## Key Features
- Execute analytical SQL queries (window functions, complex aggregations)
- Query files directly (Parquet, CSV, JSON) without import
- In-process (no server) but columnar storage (fast analytics)
- Named queries from profile `.sql` files
- Parameterized queries with CLI arguments
- Streaming results (constant memory)

## Dependencies
- `duckdb` (Python library, includes engine)

## Profile Structure
**Config:** `profiles/duckdb/analytics.json`
```json
{
  "driver": "duckdb",
  "path": "analytics.duckdb",
  "options": {"read_only": true}
}
```

**Named query:** `profiles/duckdb/analytics/sales-summary.sql`
```sql
SELECT region,
       DATE_TRUNC('month', sale_date) as month,
       SUM(revenue) as total_revenue,
       COUNT(*) as num_sales
FROM sales
WHERE sale_date >= :start_date
GROUP BY region, month
ORDER BY month, region
```

## Examples
```bash
# Named query with parameters
jn cat @analytics/sales-summary.sql --start-date 2024-01-01 | jn jtbl

# Query Parquet directly (no import needed)
jn cat data.parquet --query "SELECT * FROM data WHERE amount > 1000" | jn put filtered.csv

# Complex analytics
jn cat @analytics/revenue-by-quarter.sql --year 2024 | jn filter '.growth > 0.1' | jn jtbl

# Query multiple files
jn cat "logs/*.parquet" --query "SELECT timestamp, level, message FROM logs WHERE level = 'ERROR'" | jn put errors.json
```

## Key Differences
| Feature | SQLite | PostgreSQL | DuckDB |
|---------|--------|------------|--------|
| Use case | Local OLTP | Remote OLTP | Analytics/OLAP |
| Storage | Row-based | Row-based | Columnar |
| Query | Simple | Complex | Complex + analytical |
| Files | Read DB only | Remote only | Query Parquet/CSV directly |
| Speed | Fast writes | Balanced | Fast analytics |

## Out of Scope
- Writing to DuckDB (add later)
- Schema management - use DuckDB CLI
- Extensions (httpfs, parquet) - use defaults
