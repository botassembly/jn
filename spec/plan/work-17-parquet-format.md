# Parquet Format Plugin

## What
Read and write Apache Parquet columnar storage files. High-performance binary format for big data.

## Why
Parquet is the standard for big data, data lakes, and analytics. Efficient storage and fast queries. Works with DuckDB, Spark, pandas.

## Key Features
- Read Parquet files to NDJSON (streaming, row groups)
- Write NDJSON to Parquet format
- Schema preservation (data types, compression)
- Columnar storage (efficient for analytics)
- Compression support (snappy, gzip, zstd)
- Partition handling (Hive-style partitions)

## Dependencies
- `pyarrow` (Apache Arrow Python library, includes Parquet)

## Examples
```bash
# Read Parquet file
jn cat data.parquet | jn filter '.revenue > 1000' | jn put filtered.csv

# Convert CSV to Parquet
jn cat large.csv | jn put data.parquet

# Query with DuckDB (no import needed)
jn cat data.parquet --query "SELECT region, SUM(sales) FROM data GROUP BY region" | jn jtbl

# Process partitioned data
jn cat data/year=2024/month=01/*.parquet | jn filter '.status == "active"' | jn put jan-2024.json

# Convert between formats
jn cat input.parquet | jn put output.json
jn cat input.json | jn put output.parquet
```

## Parquet Benefits
- **Compression**: 10x smaller than CSV/JSON
- **Speed**: Columnar format = fast aggregations
- **Schema**: Type information preserved
- **Compatibility**: Works with Spark, DuckDB, pandas, BigQuery, etc.

## Record Structure
Parquet preserves schema:
```python
# Input schema is maintained
{"name": str, "age": int, "balance": float, "created": datetime}
```

## URL Syntax
- `data.parquet` - Single file
- `data/*.parquet` - Multiple files (glob)
- `data/year=2024/month=*/day=*/*.parquet` - Partitioned data

## Out of Scope
- Complex schemas (nested structs, lists) - basic types first
- Advanced partitioning strategies - read Hive-style only
- Parquet metadata editing - use dedicated tools
