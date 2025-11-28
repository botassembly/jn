# Polyglot Plugin Architecture

JN is migrating to a polyglot architecture with Zig core, Zig/Rust plugins, and Python for complex APIs.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     jn (Zig binary)                         │
│  CLI parsing │ Address parsing │ Discovery │ Pipeline exec  │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Zig Plugins │   │ Rust Plugin │   │Python Plugs │
│ csv, json   │   │    jq       │   │ gmail, mcp  │
│ http, gz    │   │   (jaq)     │   │ duckdb,xlsx │
└─────────────┘   └─────────────┘   └─────────────┘
        │                 │                 │
        └────────────────┬┴─────────────────┘
                         ▼
                Standard CLI Contract
```

## Why This Architecture

| Component | Language | Rationale |
|-----------|----------|-----------|
| **Core (jn binary)** | Zig | <5ms startup, <1MB binary, trivial cross-compile |
| **Format plugins** | Zig | Hot path parsing, 10x faster than Python |
| **jq filter** | Rust | Use jaq library (30x faster startup than jq) |
| **Protocol plugins** | Python | Complex APIs (OAuth, MCP), not hot path |

## CLI Contract

All plugins implement:
```
plugin --mode=read|write|raw [OPTIONS]
  stdin:  bytes (read) or NDJSON (write)
  stdout: NDJSON (read) or bytes (write)
  --jn-meta: output plugin metadata as JSON
```

## Plugin Assignment

| Zig | Rust | Python |
|-----|------|--------|
| csv, json, jsonl | jq (jaq) | gmail, mcp |
| gz, http | | duckdb, xlsx |
| yaml, toml | | markdown, table, xml |

## Discovery

1. Binary + manifest (or auto-generated via `--jn-meta`)
2. Python + PEP 723 (fallback)

Binary plugins take precedence.

## Manifest Format

```json
{
  "name": "csv",
  "matches": [".*\\.csv$"],
  "role": "format",
  "modes": ["read", "write"]
}
```

Auto-generated when binary is newer than manifest.

## Performance Targets

| Metric | Python | Zig/Rust |
|--------|--------|----------|
| Startup | 150-200ms | <5ms |
| CSV 1GB | 20s | 2s |
| Binary size | N/A | <500KB |

## Key Libraries

| Language | Library | Purpose |
|----------|---------|---------|
| Zig | [zimdjson](https://github.com/EzequielRamis/zimdjson) | 3+ GB/s JSON parsing |
| Zig | [zig-curl](https://github.com/jiacai2050/zig-curl) | HTTP client via libcurl |
| Rust | [jaq](https://github.com/01mf02/jaq) | jq replacement (30x faster) |
| C | simdjson, PCRE2, libcurl | Via Zig @cImport |

## Files

- [plan.md](plan.md) - Detailed implementation plan with timeline
- [experiments/](experiments/) - Proof-of-concept code
