# Users Guide

> **Purpose**: How to use JN effectively for common tasks.

---

## Quick Start

### Installation

```bash
pip install -e .
```

### Your First Pipeline

```bash
# Read CSV, output as NDJSON
jn cat data.csv

# Convert CSV to JSON
jn cat data.csv | jn put output.json

# Filter and convert
jn cat data.csv | jn filter '.revenue > 1000' | jn put filtered.json
```

---

## Core Commands

### `jn cat` - Read Any Source

Reads data from files, URLs, or profiles and outputs NDJSON.

```bash
# Local files
jn cat data.csv
jn cat data.json
jn cat data.xlsx

# Compressed files (auto-detected)
jn cat data.csv.gz

# URLs
jn cat https://api.example.com/data.json

# Profile references
jn cat @myapi/users

# With parameters
jn cat @myapi/users?limit=10

# Multiple files (glob)
jn cat "data/*.csv"

# Stdin
echo '{"x":1}' | jn cat -
```

**Format override**: Force a specific format with `~format`:
```bash
jn cat data.txt~csv           # Parse .txt as CSV
jn cat @myapi/data~json       # Force JSON parsing
```

### `jn put` - Write Any Format

Reads NDJSON from stdin and writes to a file or stdout.

```bash
# Write to file (format from extension)
jn cat data.csv | jn put output.json

# Write to stdout with format
jn cat data.csv | jn put -~table

# Compressed output
jn cat data.csv | jn put output.json.gz
```

### `jn filter` - Transform Data

Filters and transforms NDJSON using ZQ expressions.

```bash
# Filter records
jn cat data.csv | jn filter '.status == "active"'

# Select fields
jn cat data.csv | jn filter 'pick(.name, .email)'

# Transform values
jn cat data.csv | jn filter '.total = .price * .quantity'

# Multiple operations
jn cat data.csv | jn filter '.status == "active" | pick(.name, .total)'
```

**Common ZQ patterns**:
```bash
# Filter by condition
jn filter '.age > 21'
jn filter '.name | contains("Smith")'

# Select specific fields
jn filter 'pick(.id, .name, .email)'

# Rename fields
jn filter '.customer_name = .name | drop(.name)'

# Aggregate (requires slurp)
jn filter -s 'sum(.amount)'
jn filter -s 'count()'

# Group and aggregate
jn filter -s 'group_by(.category) | map({category: .[0].category, total: sum(.amount)})'
```

### `jn head` / `jn tail` - Truncate Streams

```bash
# First 10 records (default)
jn cat data.csv | jn head

# First N records
jn cat data.csv | jn head -n 5

# Last 10 records
jn cat data.csv | jn tail

# Last N records
jn cat data.csv | jn tail -n 20
```

**Important**: `head` triggers early termination—upstream stops processing after N records.

### `jn join` - Combine Data

Joins data from stdin with another source.

```bash
# Join orders with customers
jn cat orders.csv | jn join customers.csv --on customer_id

# Different key names
jn cat orders.csv | jn join customers.csv --left-key cust_id --right-key id

# Embed matches as array
jn cat customers.csv | jn join orders.csv --on customer_id --target orders

# With aggregation
jn cat customers.csv | jn join orders.csv --on customer_id --agg "order_count: count(), total: sum(.amount)"
```

### `jn merge` - Concatenate Sources

Combines multiple sources into one stream.

```bash
# Merge multiple files
jn merge data1.csv data2.csv data3.csv

# With source labels
jn merge "jan.csv:label=January" "feb.csv:label=February"

# Mixed sources
jn merge data.csv @myapi/users https://api.com/data.json
```

### `jn inspect` - Discover Structure

Examines data sources or profiles.

```bash
# Analyze data structure
jn cat data.csv | jn inspect

# Discover profile endpoints
jn inspect @myapi

# Get schema from sample
jn cat data.csv | jn head -n 100 | jn inspect
```

### `jn analyze` - Compute Statistics

Generates statistics about NDJSON streams.

```bash
jn cat data.csv | jn analyze
```

Output includes:
- Record count
- Field names and types
- Numeric statistics (min, max, mean)
- Null/missing counts

### `jn table` - Pretty Print

Formats NDJSON as a readable table.

```bash
jn cat data.csv | jn table
jn cat data.csv | jn head -n 10 | jn table
```

### `jn profile` - Manage Profiles

```bash
# List available profiles
jn profile list

# Show profile details
jn profile info @myapi/users

# Filter by type
jn profile list --type=http
```

### `jn plugin` - Plugin Management

```bash
# List available plugins
jn plugin list

# Show plugin details
jn plugin info csv

# Test a plugin
jn plugin test csv
```

---

## Address Syntax

JN uses a universal address syntax:

```
[protocol://]path[~format][?params]
```

### Examples

| Address | Protocol | Path | Format | Params |
|---------|----------|------|--------|--------|
| `data.csv` | file | data.csv | csv (inferred) | - |
| `data.txt~csv` | file | data.txt | csv (override) | - |
| `https://api.com/data` | http | api.com/data | json (inferred) | - |
| `@myapi/users?limit=10` | profile | myapi/users | (from profile) | limit=10 |
| `data.csv.gz` | file | data.csv.gz | csv | (auto-decompress) |
| `duckdb://sales.db/orders` | duckdb | sales.db/orders | - | - |

### Format Override

Use `~format` to force a specific parser:

```bash
jn cat data.txt~csv              # Parse text as CSV
jn cat data.json~jsonl           # Parse as NDJSON, not JSON array
jn cat @myapi/export~csv         # Force CSV for API response
```

### Query Parameters

Pass parameters with `?key=value`:

```bash
jn cat "data.csv?delimiter=;"    # Semicolon-delimited
jn cat "@myapi/users?limit=100"  # API parameter
jn cat "data.csv?header=false"   # No header row
```

---

## Common Workflows

### Format Conversion

```bash
# CSV to JSON
jn cat data.csv | jn put output.json

# JSON to CSV
jn cat data.json | jn put output.csv

# Excel to CSV
jn cat report.xlsx | jn put data.csv

# Any format to table
jn cat data.yaml | jn table
```

### Data Filtering

```bash
# Filter rows
jn cat sales.csv | jn filter '.amount > 1000' | jn put big_sales.csv

# Select columns
jn cat users.csv | jn filter 'pick(.id, .email)' | jn put emails.csv

# Complex conditions
jn cat orders.csv | jn filter '.status == "pending" and .created < "2024-01-01"'
```

### API Data Extraction

```bash
# Fetch and save
jn cat @github/repos?user=torvalds | jn put repos.json

# Fetch, filter, save
jn cat @myapi/users | jn filter '.active' | jn put active_users.csv

# Multiple endpoints
jn merge @myapi/users @myapi/admins | jn put all_accounts.json
```

### Data Exploration

```bash
# Quick look at structure
jn cat data.csv | jn head | jn table

# Get statistics
jn cat data.csv | jn analyze

# Sample large file
jn cat huge.csv | jn head -n 1000 | jn analyze
```

### Multi-Source Operations

```bash
# Enrich orders with customer data
jn cat orders.csv | jn join customers.csv --on customer_id | jn put enriched.json

# Combine monthly files
jn merge "2024-*.csv" | jn put year.csv

# Compare sources
jn cat old.csv | jn filter 'pick(.id)' > old_ids.txt
jn cat new.csv | jn filter 'pick(.id)' > new_ids.txt
diff old_ids.txt new_ids.txt
```

---

## Tips and Tricks

### Early Termination

`head` stops upstream processing—use it for sampling:

```bash
# Only downloads ~10 records worth, not entire API
jn cat @huge-api/data | jn head -n 10
```

### Debugging Pipelines

Check intermediate output:

```bash
# See what's being passed
jn cat data.csv | tee debug.ndjson | jn filter '.x > 10' | jn put out.json

# Check record count at each stage
jn cat data.csv | jn filter '.x > 10' | wc -l
```

### Memory-Efficient Processing

All operations stream by default:

```bash
# Works on 10GB file with ~1MB RAM
jn cat huge.csv | jn filter '.status == "active"' | jn put filtered.csv
```

### Parallel Sources

Merge runs sources sequentially, but each source streams:

```bash
# Three files, processed one after another, all streaming
jn merge file1.csv file2.csv file3.csv | jn put combined.csv
```

---

## See Also

- [06-matching-resolution.md](06-matching-resolution.md) - How addresses resolve to plugins
- [07-profiles.md](07-profiles.md) - Profile configuration details
- [08-streaming-backpressure.md](08-streaming-backpressure.md) - Why streaming works
