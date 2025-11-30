# Sprint 06: CSV & JSON Plugins

**Status:** 🔲 PLANNED

**Goal:** Build production CSV and JSON plugins using jn-plugin library

**Prerequisite:** Sprint 05 complete (jn-plugin library)

---

## Deliverables

1. CSV plugin (read/write)
2. JSON plugin (read)
3. JSONL plugin (read/write)
4. Integration with JN discovery

---

## Phase 1: CSV Plugin - Read Mode

### Core Implementation
- [ ] Create `plugins/zig/csv/` directory
- [ ] Parse CSV header row
- [ ] Stream rows as NDJSON objects
- [ ] Handle standard CSV escaping

### Options
- [ ] `--delimiter=,` - field delimiter (default comma)
- [ ] `--no-header` - first row is data, not headers
- [ ] `--quote="` - quote character (default double-quote)

### Edge Cases
- [ ] Empty file → no output
- [ ] Header only → no data rows
- [ ] Quoted fields with delimiters
- [ ] Escaped quotes inside fields
- [ ] Unicode content
- [ ] Very long lines (>10KB)
- [ ] Missing fields (short rows)
- [ ] Extra fields (long rows)

### Quality Gate
- [ ] `jn-csv --mode=read < test.csv` outputs valid NDJSON
- [ ] Handles all edge cases
- [ ] 1GB file in <5s

---

## Phase 2: CSV Plugin - Write Mode

### Core Implementation
- [ ] Read NDJSON from stdin
- [ ] Write CSV header from first record keys
- [ ] Stream rows in consistent column order

### Options
- [ ] `--delimiter=,` - field delimiter
- [ ] `--no-header` - skip header row

### Edge Cases
- [ ] Empty input → empty output
- [ ] Fields containing delimiter → quoted
- [ ] Fields containing newline → quoted
- [ ] Fields containing quotes → escaped
- [ ] Inconsistent fields across records
- [ ] Null values → empty field

### Quality Gate
- [ ] `jn-csv --mode=write < test.ndjson` outputs valid CSV
- [ ] Round-trip CSV → NDJSON → CSV preserves data

---

## Phase 3: JSON Plugin

### Read Mode
- [ ] Parse JSON array → NDJSON
- [ ] Parse JSON object → single NDJSON record
- [ ] Handle nested structures

### Options
- [ ] Auto-detect array vs object
- [ ] `--array-path=.data` - path to array in object

### Edge Cases
- [ ] Empty array → no output
- [ ] Deeply nested objects
- [ ] Large JSON files (>100MB)
- [ ] Malformed JSON → error

### Quality Gate
- [ ] `jn-json --mode=read < test.json` outputs NDJSON
- [ ] Handles large files efficiently

---

## Phase 4: JSONL Plugin

### Read Mode
- [ ] Validate each line is valid JSON
- [ ] Pass through valid NDJSON
- [ ] Report malformed lines

### Write Mode
- [ ] Pass through NDJSON (identity)
- [ ] Ensure each record is single line
- [ ] Ensure no trailing newline issues

### Options
- [ ] `--skip-invalid` - skip malformed lines
- [ ] `--strict` - fail on first invalid line

### Quality Gate
- [ ] JSONL read validates input
- [ ] JSONL write produces valid NDJSON

---

## Phase 5: Discovery Integration

### Manifest Files
- [ ] Create manifest.json for each plugin
- [ ] Or use `--jn-meta` auto-generation

### JN Integration
- [ ] Update discovery to find binary plugins
- [ ] Binary plugins take precedence over Python
- [ ] Test: `jn cat test.csv` uses Zig plugin

### Installation
- [ ] Plugins build to `jn_home/plugins/formats/`
- [ ] Or separate binary distribution

### Quality Gate
- [ ] `jn cat test.csv` uses Zig CSV plugin
- [ ] `jn cat test.json` uses Zig JSON plugin
- [ ] Discovery correctly prioritizes binary plugins

---

## Phase 6: Performance Benchmarks

### CSV Benchmarks
| File Size | Target Time | vs Python |
|-----------|-------------|-----------|
| 1MB | <50ms | 5x faster |
| 100MB | <2s | 10x faster |
| 1GB | <15s | 10x faster |

### JSON Benchmarks
| File Size | Target Time | vs Python |
|-----------|-------------|-----------|
| 1MB | <30ms | 5x faster |
| 100MB | <2s | 10x faster |
| 1GB | <15s | 10x faster |

### Binary Size
- [ ] CSV plugin <500KB (ReleaseSmall)
- [ ] JSON plugin <500KB (ReleaseSmall)

### Quality Gate
- [ ] All benchmarks meet targets
- [ ] Memory usage constant (streaming)

---

## Phase 7: Testing

### Test Matrix

| Test | CSV Read | CSV Write | JSON | JSONL |
|------|----------|-----------|------|-------|
| Basic operation | ✅ | ✅ | ✅ | ✅ |
| Empty input | ✅ | ✅ | ✅ | ✅ |
| Unicode | ✅ | ✅ | ✅ | ✅ |
| Large file (1GB) | ✅ | ✅ | ✅ | ✅ |
| Malformed input | ✅ | ✅ | ✅ | ✅ |
| --jn-meta | ✅ | ✅ | ✅ | ✅ |
| Pipeline chain | ✅ | ✅ | ✅ | ✅ |

### Integration Tests
- [ ] `jn cat test.csv | jn filter '.x > 10' | jn put out.json`
- [ ] `jn cat test.json | jn put out.csv`
- [ ] All existing JN tests pass with Zig plugins

### Quality Gate
- [ ] All tests pass
- [ ] No regressions from Python plugins

---

## Success Criteria

| Plugin | Read | Write | Benchmark | Tests |
|--------|------|-------|-----------|-------|
| CSV | ✅ | ✅ | 10x faster | Pass |
| JSON | ✅ | N/A | 10x faster | Pass |
| JSONL | ✅ | ✅ | Baseline | Pass |

---

## Notes

**Library Dependencies:**
- Consider [zig_csv](https://github.com/matthewtolman/zig_csv) for CSV
- Use std.json for JSON (or simdjson via @cImport for speed)

**Deferred:**
- GZ compression plugin
- HTTP protocol plugin
- YAML/TOML plugins
