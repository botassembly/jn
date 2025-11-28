# Polyglot Plugin Architecture

This folder contains the design documents for JN's polyglot plugin system, enabling plugins written in any language (Rust, Go, Python, etc.) with a standardized CLI interface.

## Overview

JN is migrating from Python-only plugins to a language-agnostic architecture where:

1. **Plugins are standalone executables** with a standard CLI contract
2. **Rust replaces Python** for hot-path format plugins (10x performance)
3. **Manifests are auto-generated** from binaries via `--jn-meta`
4. **Core libraries** reduce boilerplate in both Python and Rust

## Documents

| Document | Purpose |
|----------|---------|
| [01-architecture-review.md](01-architecture-review.md) | Analysis of current architecture, feasibility of pure CLI |
| [02-core-library.md](02-core-library.md) | Shared library design for Python (`jn_plugin`) and Rust (`jn-plugin`) |
| [03-distribution.md](03-distribution.md) | Cross-platform build, bundling, and distribution |
| [04-replacement-strategy.md](04-replacement-strategy.md) | Which plugins to Rust, manifest schema, discovery |
| [05-auto-manifests.md](05-auto-manifests.md) | Auto-generating manifests from binary `--jn-meta` |
| [06-language-comparison.md](06-language-comparison.md) | Rust vs Go vs C vs Shell - when to use each |

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
| csv, json, yaml, toml, xlsx, xml, gz | **Rust** | Hot path, 10x speedup |
| http, gmail, mcp, duckdb | Python | Complex APIs, not hot path |
| jq, markdown, table | Python | Thin wrappers, low impact |

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
│                        jn CLI                                │
│                     (Python/Click)                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Discovery                                │
│  1. Find binaries → auto-generate manifest via --jn-meta    │
│  2. Find *.py → parse PEP 723                               │
│  3. Binary takes precedence over Python                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Rust Plugin │   │ Python Plug │   │  Go Plugin  │
│   (csv_)    │   │  (http_.py) │   │  (future)   │
├─────────────┤   ├─────────────┤   ├─────────────┤
│ jn-plugin   │   │ jn_plugin   │   │ jn-plugin   │
│   crate     │   │   module    │   │   module    │
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

### Phase 1: Foundation
- [ ] Create `jn-plugins-rs` repository with workspace
- [ ] Implement `jn-plugin` core crate
- [ ] Update discovery for binary plugins

### Phase 2: Core Plugins
- [ ] Port `csv_` to Rust
- [ ] Port `json_` to Rust
- [ ] Port `gz_` to Rust
- [ ] Benchmark against Python versions

### Phase 3: Distribution
- [ ] GitHub Actions for cross-platform builds
- [ ] Auto-download on `pip install jn`
- [ ] Remove Python versions of ported plugins

### Phase 4: Extended Plugins
- [ ] Port `yaml_`, `toml_`, `xlsx_`, `xml_`
- [ ] Performance optimization (SIMD, mmap)
- [ ] Documentation and examples

## Related Files

- `experiments/plugin-core/jn_plugin.py` - Python core library PoC
- `experiments/plugin-core/csv_plugin.py` - CSV plugin using core library
- `jn_home/plugins/` - Current Python plugins (to be replaced)

## References

- [PEP 723](https://peps.python.org/pep-0723/) - Inline script metadata
- [serde](https://serde.rs/) - Rust serialization framework
- [clap](https://docs.rs/clap/) - Rust CLI argument parsing
- [cross](https://github.com/cross-rs/cross) - Cross-compilation for Rust
