# Sprint 01: Foundation & CSV Plugin

**Duration:** Week 1-2
**Goal:** Establish core libraries and prove Zig plugin viability with CSV

---

## Phase 1: Project Setup

### Quality Gate
- [ ] All three language projects compile/build
- [ ] Directory structure matches plan
- [ ] CI pipeline runs for Zig and Rust

### Tasks

#### Directory Structure
- [ ] Create `libs/python/jn_plugin/` directory
- [ ] Create `libs/zig/jn-plugin/` directory
- [ ] Create `libs/rust/jn-plugin/` directory
- [ ] Create `plugins/zig/csv/` directory
- [ ] Create `core/` directory for Zig binary (future)

#### Zig Setup
- [ ] Install Zig toolchain (0.11+)
- [ ] Initialize `libs/zig/jn-plugin/build.zig`
- [ ] Create minimal `src/lib.zig` that compiles
- [ ] Add `.gitignore` for `zig-cache/`, `zig-out/`

#### Rust Setup
- [ ] Initialize `libs/rust/jn-plugin/` with `cargo init --lib`
- [ ] Add jaq-core, serde, serde_json to `Cargo.toml`
- [ ] Create minimal lib.rs that compiles
- [ ] Verify `cargo build` succeeds

#### Python Setup
- [ ] Create `libs/python/jn_plugin/__init__.py`
- [ ] Create `libs/python/pyproject.toml`
- [ ] Implement basic `Plugin` class skeleton

---

## Phase 2: Zig Core Library

### Quality Gate
- [ ] `zig build test` passes
- [ ] Can write simple plugin using library
- [ ] `--jn-meta` outputs valid JSON

### Tasks

#### Core Types
- [ ] Define `Plugin` struct (name, matches, role, modes)
- [ ] Define `Config` struct (args, options map)
- [ ] Define `NdjsonWriter` for stdout streaming
- [ ] Define `NdjsonReader` for stdin parsing

#### CLI Parsing
- [ ] Parse `--mode=read|write|raw` argument
- [ ] Parse `--jn-meta` flag for metadata output
- [ ] Parse remaining args into config
- [ ] Error on unknown required args

#### Plugin Runner
- [ ] Implement `run()` that dispatches to reads/writes
- [ ] Handle `--jn-meta` to output plugin metadata as JSON
- [ ] Proper exit codes (0 success, 1 error)
- [ ] Error messages to stderr

#### NDJSON Utilities
- [ ] Implement buffered stdout writer
- [ ] Implement JSON object serialization
- [ ] Implement stdin line reader
- [ ] Implement JSON parsing for config values

#### Tests
- [ ] Test CLI arg parsing
- [ ] Test `--jn-meta` JSON output
- [ ] Test NDJSON writing
- [ ] Test error handling

---

## Phase 3: CSV Plugin

### Quality Gate
- [ ] `jn-csv --mode=read < test.csv` outputs valid NDJSON
- [ ] `jn-csv --jn-meta` outputs valid manifest JSON
- [ ] Handles 1MB file in <100ms
- [ ] Binary size <500KB

### Tasks

#### Dependencies
- [ ] Evaluate zig_csv vs manual parsing
- [ ] Add CSV library to build.zig dependencies
- [ ] Verify library compiles with jn-plugin

#### Read Mode
- [ ] Parse CSV header row
- [ ] Stream each row as JSON object
- [ ] Handle delimiter option (`,` default)
- [ ] Handle `--no-header` option
- [ ] Handle quoted fields
- [ ] Handle escaped quotes

#### Write Mode
- [ ] Read NDJSON from stdin
- [ ] Write CSV header from first record keys
- [ ] Stream each record as CSV row
- [ ] Handle delimiter option
- [ ] Quote fields containing delimiter/newline

#### Edge Cases
- [ ] Empty file → no output
- [ ] Header only → no data rows
- [ ] Unicode content
- [ ] Very long lines (>10KB)
- [ ] Malformed CSV (unclosed quotes)

#### Integration
- [ ] Add manifest.json alongside binary
- [ ] Test discovery finds binary plugin
- [ ] Test: `jn cat test.csv` uses Zig plugin
- [ ] Test: pipeline with Python plugin downstream

---

## Phase 4: Python Core Library

### Quality Gate
- [ ] Existing plugins can migrate to new library
- [ ] `python -m jn_plugin.test` passes
- [ ] API matches Zig library semantics

### Tasks

#### Plugin Class
- [ ] Implement `Plugin(name, matches, role, modes)`
- [ ] Implement `@plugin.reader` decorator
- [ ] Implement `@plugin.writer` decorator
- [ ] Implement `plugin.run()` CLI dispatcher

#### NDJSON Utilities
- [ ] Implement `ndjson.read_stdin()` generator
- [ ] Implement `ndjson.write(record)` to stdout
- [ ] Handle encoding (UTF-8)

#### Metadata
- [ ] Implement `--jn-meta` output
- [ ] Generate manifest JSON matching Zig format
- [ ] Validate manifest schema

#### Migration Test
- [ ] Migrate one existing plugin (yaml?) to new library
- [ ] Verify behavior matches original
- [ ] Document migration steps

---

## Phase 5: Rust Core Library (Stub)

### Quality Gate
- [ ] Crate compiles with no errors
- [ ] Basic types defined for jq plugin use

### Tasks

#### Core Types
- [ ] Define `Plugin` trait
- [ ] Define `Config` struct
- [ ] Define `NdjsonWriter` struct
- [ ] Stub `run()` function

#### Proc Macro (Optional)
- [ ] Evaluate if `#[derive(Plugin)]` is needed now
- [ ] If yes, create `jn-plugin-derive` crate
- [ ] If no, use manual impl for jq plugin

---

## Completion Checklist

### Documentation
- [ ] Update spec/polyglot/README.md with actual paths
- [ ] Add libs/README.md with build instructions
- [ ] Document CLI contract in each library

### Testing
- [ ] CSV plugin passes all edge case tests
- [ ] Performance benchmark: CSV 1MB < 100ms
- [ ] Integration test with existing `jn` framework

### Cleanup
- [ ] Remove experiments/ if superseded by real code
- [ ] Update .gitignore for new build artifacts
- [ ] Commit with descriptive message

---

## Notes

**Blockers:**
- (none yet)

**Decisions:**
- (record decisions made during sprint)

**Deferred:**
- (items pushed to next sprint)
