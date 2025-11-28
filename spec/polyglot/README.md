# Polyglot Plugin Architecture

This folder contains the design documents for JN's polyglot plugin system, enabling plugins written in any language (Rust, Go, Python, etc.) with a standardized CLI interface.

## Overview

JN is migrating from Python-only plugins to a language-agnostic architecture where:

1. **Zig core binary** replaces Python CLI for instant startup (<5ms)
2. **Zig plugins** for hot-path formats (csv, json, http) - 10x performance
3. **Rust plugin** for jq replacement (jaq-based) - 30x faster startup
4. **Python plugins** retained for complex APIs (gmail, mcp, duckdb)
5. **Core libraries** for Python, Zig, and Rust plugin development
6. **Manifests auto-generated** from binaries via `--jn-meta`

## Documents

| Document | Purpose |
|----------|---------|
| [01-architecture-review.md](01-architecture-review.md) | Analysis of current architecture, feasibility of pure CLI |
| [02-core-library.md](02-core-library.md) | Shared library design for Python (`jn_plugin`) and Rust (`jn-plugin`) |
| [03-distribution.md](03-distribution.md) | Cross-platform build, bundling, and distribution |
| [04-replacement-strategy.md](04-replacement-strategy.md) | Which plugins to Rust, manifest schema, discovery |
| [05-auto-manifests.md](05-auto-manifests.md) | Auto-generating manifests from binary `--jn-meta` |
| [06-language-comparison.md](06-language-comparison.md) | Rust vs Go vs C vs Shell - when to use each |
| [07-zig-proposal.md](07-zig-proposal.md) | Zig as optimal choice for core plugins |
| [08-core-zig-evaluation.md](08-core-zig-evaluation.md) | Evaluation of replacing JN core with Zig |
| [09-implementation-plan.md](09-implementation-plan.md) | **Final implementation plan with timeline** |

## Key Decisions

### CLI Contract

All plugins (any language) implement:

```
plugin --mode=read|write|raw [OPTIONS] [ADDRESS]

stdin:  Raw bytes (read) or NDJSON (write)
stdout: NDJSON (read) or format bytes (write)
stderr: Human-readable errors
exit:   0=success, 1=error

Special:
  --jn-meta    Output plugin metadata as JSON
  --limit N    Limit output records
```

### Plugin Replacement Plan

| Plugin | Language | Rationale |
|--------|----------|-----------|
| csv, json, jsonl, gz, http | **Zig** | Hot path, 10x speedup, tiny binaries |
| yaml, toml | **Zig** | Common formats, simple parsing |
| jq | **Rust** | Use jaq library (30x faster than jq) |
| gmail, mcp, duckdb | Python | Complex APIs, OAuth, not hot path |
| xlsx, markdown, table, xml | Python | Library dependencies, lower priority |

### Discovery Priority

1. **Binary + manifest** (or auto-generated manifest)
2. **Python + PEP 723** (fallback)

Binary plugins take precedence over Python plugins with the same name.

### Manifest Format

```json
{
  "name": "csv",
  "version": "0.1.0",
  "description": "Parse CSV/TSV files",
  "matches": [".*\\.csv$", ".*\\.tsv$"],
  "role": "format",
  "modes": ["read", "write"],
  "supports_raw": false,
  "manages_parameters": false,
  "supports_container": false
}
```

Manifests are **auto-generated** by running `plugin --jn-meta` when:
- Binary exists but manifest is missing
- Binary is newer than manifest

## Architecture Diagram

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
├─────────────┤   ├─────────────┤   ├─────────────┤
│ jn-plugin   │   │ jn-plugin   │   │ jn_plugin   │
│    (zig)    │   │   (rust)    │   │  (python)   │
└─────────────┘   └─────────────┘   └─────────────┘
      │                 │                 │
      └────────────────┬┴─────────────────┘
                       ▼
              Standard CLI Contract
              (stdin/stdout/NDJSON)
```

## Performance Targets

| Metric | Python | Rust | Improvement |
|--------|--------|------|-------------|
| CSV parse (1GB) | 20s | 2s | 10x |
| JSON parse (1GB) | 15s | 1.5s | 10x |
| Process startup | 50-200ms | <10ms | 10-20x |
| Memory (streaming) | ~100MB | ~10MB | 10x |

**Petabyte workload (1000 × 1TB files, 100 parallel):**
- Python: ~2.3 days
- Rust: ~5.5 hours

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Core libraries: Python (`jn_plugin`), Zig (`jn-plugin`), Rust (`jn-plugin-rs`)
- [ ] First Zig plugin: CSV (proof of concept)
- [ ] Update discovery for binary plugins + manifests

### Phase 2: Zig Core Binary (Week 3-4)
- [ ] CLI parser, address parser in Zig
- [ ] Pipeline executor (fork/exec, pipe management)
- [ ] Plugin discovery from manifests
- [ ] Partial replacement: keep Python for complex resolution

### Phase 3: Zig Plugins (Week 5-6)
- [ ] json, jsonl, gz plugins
- [ ] http plugin (using zig-curl)
- [ ] yaml, toml plugins

### Phase 4: Rust jq Plugin (Week 7-8)
- [ ] jq replacement using jaq library
- [ ] 30x faster startup than jq
- [ ] Full jq compatibility for JN use cases

### Phase 5: Integration (Week 9-10)
- [ ] Discovery priority: binary > Python
- [ ] Cross-platform builds (GitHub Actions)
- [ ] Performance benchmarks
- [ ] Remove Python versions of ported plugins

## Related Files

- `spec/polyglot/experiments/plugin-core/jn_plugin.py` - Python core library PoC
- `spec/polyglot/experiments/plugin-core/csv_plugin.py` - CSV plugin using core library
- `jn_home/plugins/` - Current Python plugins (some to be replaced)

## References

### Zig
- [zig_csv](https://github.com/matthewtolman/zig_csv) - SIMD-accelerated CSV parser
- [zig-curl](https://github.com/jiacai2050/zig-curl) - libcurl bindings for HTTP
- [zimdjson](https://github.com/EzequielRamis/zimdjson) - simdjson port (3+ GB/s JSON)
- [std.json](https://zig.guide/standard-library/json/) - Zig standard library JSON

### Rust
- [jaq](https://github.com/01mf02/jaq) - jq clone (30x faster startup, security audited)
- [jaq-core](https://crates.io/crates/jaq-core) - jaq as library
- [serde](https://serde.rs/) - Serialization framework

### C Libraries (via @cImport)
- [simdjson](https://github.com/simdjson/simdjson) - 3+ GB/s JSON parsing
- [PCRE2](https://github.com/PCRE2Project/pcre2) - Regex library
- [libcurl](https://curl.se/libcurl/) - HTTP client

### Python
- [PEP 723](https://peps.python.org/pep-0723/) - Inline script metadata
