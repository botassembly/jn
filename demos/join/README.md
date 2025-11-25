# Join Demo

Demonstrates `jn join` for enriching data streams with related data.

## Quick Start

```bash
cd demos/join
./run_examples.sh
```

## Features Demonstrated

1. **Basic Left Join** - Enrich customers with their orders
2. **One-to-Many Condensation** - Multiple matches become arrays (not row explosions)
3. **Inner Join** - Filter to only records with matches
4. **Field Selection** - Pick specific fields from right source

## Key Concept

Unlike SQL joins that duplicate rows, `jn join` **condenses** matches into arrays:

```json
{"customer": "Alice", "orders": [{"id": "O1"}, {"id": "O2"}]}
{"customer": "Bob", "orders": []}
```

This preserves the cardinality of the primary stream while embedding related data.
