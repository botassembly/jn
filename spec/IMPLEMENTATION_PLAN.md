# JN Next-Gen Implementation Plan

**Approach:** Ground-up rebuild with code harvesting
**Started:** 2025-11-09
**Target:** Production-ready agent-native ETL framework

---

## Progress Overview

**Week 1: Foundation** ⚙️ IN PROGRESS
**Week 2-4: Core Features** 📋 PLANNED
**Week 5-8: Advanced Features** 📋 PLANNED
**Week 9-12: Polish & Ecosystem** 📋 PLANNED

---

## Week 1: Foundation & Core Plugins

### Day 1-2: Project Bootstrap ✅ COMPLETE

- [x] Move old implementation to `oldgen/`
  - Archived 3,500 LOC for reference
  - Tests preserved in `oldgen/tests/`

- [x] Create new directory structure
  ```
  src/jn/          # Core library
  plugins/         # Bundled plugins
  tests/           # New test suite
  docs/harvest/    # Documentation
  ```

- [x] Harvest code patterns
  - `src/jn/detection.py` - Auto-detection logic (160 LOC)
  - `src/jn/subprocess_utils.py` - Safe subprocess patterns (120 LOC)
  - Documentation in `docs/harvest/code-harvest.md`

- [x] CLI framework decision
  - **Click for core** - Lightweight, composable
  - **argparse for plugins** - Zero dependencies
  - Rationale documented in code-harvest.md

- [x] Update package configuration
  - Version: 4.0.0-alpha1
  - Dependencies: Just `click>=8.0.0` (minimal!)
  - Plugins included in package distribution

**Status:** ✅ Complete | **LOC:** 280 | **Tests:** N/A

---

### Day 3-4: Essential Plugins ✅ COMPLETE

- [x] Plugin organization
  ```
  plugins/
    readers/     # File format → NDJSON
    writers/     # NDJSON → file format
    filters/     # NDJSON → NDJSON
    shell/       # Command → NDJSON
    http/        # HTTP/API (future)
  ```

- [x] CSV reader/writer
  - `plugins/readers/csv_reader.py` - CSV/TSV → NDJSON
  - `plugins/writers/csv_writer.py` - NDJSON → CSV/TSV
  - Tests: 5/5 passing

- [x] JSON passthrough
  - `plugins/readers/json_reader.py` - Smart JSON/NDJSON detection
  - Tests: 3/3 passing

- [x] First shell plugin
  - `plugins/shell/ls.py` - Parse ls output to NDJSON
  - Vendored parsing logic from JC concepts
  - Tests: 1/1 passing

- [x] Plugin documentation
  - `docs/harvest/plugin-organization.md` - Strategy & roadmap
  - `plugins/README.md` - Usage guide
  - JC vendoring tiers (15+ commands planned)

**Status:** ✅ Complete | **LOC:** 570 | **Tests:** 9/9 passing (100%)

---

### Day 5: Plugin Discovery System ✅ COMPLETE

- [x] Filesystem scanner (`src/jn/discovery.py`)
  - Scan plugin paths (user → project → package → system)
  - Parse `# META:` headers with regex (no Python imports!)
  - Track modification times for cache invalidation
  - Return plugin registry dict

- [x] Extension registry (`src/jn/registry.py`)
  - Load/save `~/.jn/registry.json`
  - Map extensions to plugins (`.csv` → `csv_reader`)
  - Map URL patterns to plugins (`https://` → `http_get`)
  - Default registry with built-in mappings

- [x] Plugin metadata parser
  - Extract `type`, `handles`, `streaming` from headers
  - Parse examples() docstring (regex, no exec)
  - Read `.schema.json` if exists
  - Cache results with mtime

- [x] Discovery tests
  - `tests/unit/test_discovery.py` - 16 tests
  - `tests/unit/test_registry.py` - 18 tests
  - Test regex parsing
  - Test extension resolution
  - Test modification tracking

**Status:** ✅ Complete | **LOC:** 218 | **Tests:** 34 passing (100%)

---

### Week 1 Summary Goals

- [x] Project structure and foundation
- [x] 4 working plugins with tests
- [x] Plugin discovery without imports
- [x] Extension registry system
- [ ] Foundation for CLI commands

**Week 1 Status:** ✅ Days 1-5 Complete
- LOC: 1,068 code (vs oldgen 3,500 = 69% reduction)
- Core library: detection.py, subprocess_utils.py, discovery.py, registry.py
- Plugins: 4 working (csv_reader, csv_writer, json_reader, ls)
- Tests: 34/34 passing (100%)
- Coverage: 92%

---

## Week 2: Pipeline Execution & CLI

### Day 1-2: Automatic Pipeline Builder ✅ COMPLETE

- [x] Auto-pipeline construction (`src/jn/pipeline.py`)
  - `build_pipeline(args)` - Detect source, filters, target
  - Use detection.py for source/target detection
  - Use registry for extension → plugin mapping
  - Support inline jq expressions
  - Extension-based detection (works even if files don't exist)
  - Command argument parsing for shell plugins

- [x] Pipeline executor (`src/jn/executor.py`)
  - Execute plugins as subprocesses
  - Chain with Unix pipes
  - Stream NDJSON between steps
  - Handle errors gracefully
  - File input redirection for source plugins
  - Proper stdout/stderr capture

- [x] UV integration
  - Execute plugins via `uv run plugin.py`
  - Respect PEP 723 dependencies
  - Automatic fallback to python if UV not available

- [x] Pipeline tests
  - `tests/integration/test_pipeline.py` - 17 tests
  - Test pipeline building (files, URLs, commands)
  - Test jq filter detection
  - Test output format detection
  - Test CSV → NDJSON execution
  - Test error handling

**Status:** ✅ Complete | **LOC:** 300 | **Tests:** 17/17 passing (100%)

---

### Day 3-4: Click-Based CLI

- [ ] Core CLI (`src/jn/cli.py`)
  - Click application setup
  - Common options (--json, --quiet, --debug)
  - Error handling and exit codes

- [ ] `jn discover` command
  ```bash
  jn discover                    # List all plugins
  jn discover --type source      # Filter by type
  jn discover --changed-since    # Recent changes
  jn discover --json             # Machine-readable
  ```

- [ ] `jn show` command
  ```bash
  jn show csv_reader             # Show plugin details
  jn show csv_reader --examples  # Show examples
  jn show csv_reader --schema    # Show output schema
  ```

- [ ] `jn run` command (basic)
  ```bash
  jn run data.csv output.json    # Auto-detect pipeline
  jn run data.csv filter output.json  # With filter
  ```

- [ ] CLI tests
  - `tests/integration/test_cli.py`
  - Test discovery output
  - Test show command
  - Test basic run command

**Target:** 300 LOC | **Tests:** 15-20 tests

---

### Day 5: More Core Plugins

- [ ] JQ filter wrapper (`plugins/filters/jq_filter.py`)
  - Execute jq subprocess
  - Pass query as argument
  - Stream NDJSON through

- [ ] JSON writer (`plugins/writers/json_writer.py`)
  - NDJSON → JSON array
  - Pretty-print option
  - Handle large arrays

- [ ] HTTP GET plugin (`plugins/http/http_get.py`)
  - Use subprocess_utils.run_http_request()
  - Support headers, auth
  - Parse JSON responses

- [ ] Plugin tests
  - Test jq filtering
  - Test JSON writing
  - Test HTTP fetching

**Target:** 400 LOC | **Tests:** 8-10 tests

---

### Week 2 Summary Goals

- [ ] Full pipeline execution working
- [ ] Basic CLI commands (discover, show, run)
- [ ] 7+ working plugins
- [ ] End-to-end integration tests

**Target Status:**
- LOC: 2,000
- Plugins: 7
- Tests: 40+ passing

---

## Week 3: Shell Commands & Advanced Features

### Day 1-2: Shell Command Plugins

Vendor key commands from JC concepts:

- [ ] `plugins/shell/ps.py` - Process listing
  - Parse `ps aux` output
  - Fields: pid, user, cpu, mem, command

- [ ] `plugins/shell/find.py` - File search
  - Parse `find` output
  - Fields: path, type, size, permissions

- [ ] `plugins/shell/du.py` - Disk usage
  - Parse `du -sh` output
  - Fields: size, path

- [ ] `plugins/shell/df.py` - Filesystem info
  - Parse `df -h` output
  - Fields: filesystem, size, used, available, mount

**Target:** 600 LOC | **Tests:** 8-10 tests

---

### Day 3-4: Network Shell Commands

- [ ] `plugins/shell/dig.py` - DNS queries
  - Parse dig output
  - Fields: query, answer, authority, additional

- [ ] `plugins/shell/netstat.py` - Network connections
  - Parse netstat output
  - Fields: protocol, local_address, foreign_address, state

- [ ] `plugins/shell/ping.py` - Network connectivity
  - Parse ping output
  - Fields: host, time, ttl, packets

**Target:** 400 LOC | **Tests:** 6-8 tests

---

### Day 5: Advanced CLI Features

- [ ] `jn create` command
  ```bash
  jn create filter my-filter --query 'select(.amount > 100)'
  jn create source my-api --template http-json
  ```

- [ ] `jn test` command
  ```bash
  jn test csv_reader              # Run plugin tests
  jn test csv_reader --verbose    # Detailed output
  ```

- [ ] `jn validate` command
  ```bash
  jn validate my-plugin.py        # Lint + dry-run
  ```

**Target:** 250 LOC | **Tests:** 10-12 tests

---

### Week 3 Summary Goals

- [ ] 10+ shell command plugins
- [ ] Advanced CLI (create, test, validate)
- [ ] Rich plugin ecosystem

**Target Status:**
- LOC: 3,250
- Plugins: 14
- Tests: 60+ passing

---

## Week 4: Testing & Documentation

### Day 1-2: Test Infrastructure

- [ ] Port test patterns from oldgen
  - `tests/conftest.py` - CliRunner, fixtures
  - `tests/helpers.py` - Test data generators
  - Integration test structure

- [ ] Comprehensive test coverage
  - All plugins: 100% coverage
  - Core: 90%+ coverage
  - CLI: 80%+ coverage

- [ ] Plugin test runner
  ```bash
  make test-plugins    # Test all plugins
  make test-core       # Test core library
  make test-cli        # Test CLI
  ```

**Target:** 500 LOC (tests) | **Coverage:** 90%+

---

### Day 3-5: Documentation

- [ ] README.md - Quick start guide
- [ ] docs/architecture.md - Copy nextgen-redesign.md
- [ ] docs/plugins.md - Plugin authoring guide
- [ ] docs/agents.md - Guide for agents
- [ ] docs/examples/ - Working examples
  - basic-etl.md
  - agent-workflow.md
  - shell-commands.md

- [ ] Plugin templates
  - `templates/source_basic.py`
  - `templates/filter_basic.py`
  - `templates/target_basic.py`

**Target:** 2,000 LOC (docs)

---

### Week 4 Summary Goals

- [ ] 90%+ test coverage
- [ ] Complete documentation
- [ ] Plugin templates ready

**Target Status:**
- LOC: 3,750 (code) + 2,500 (docs/tests)
- Plugins: 14
- Tests: 100+ passing
- Coverage: 90%+

---

## Weeks 5-8: Advanced Features & Polish

### Week 5: Advanced Readers/Writers

- [ ] Excel reader/writer (openpyxl)
- [ ] YAML reader/writer
- [ ] XML reader/writer
- [ ] Parquet reader/writer
- [ ] Advanced filters (aggregations, group-by)

**Target:** 800 LOC | **Plugins:** 20

---

### Week 6: Database & Cloud

- [ ] Database plugins (postgres, mysql, sqlite)
- [ ] S3 plugins (read/write)
- [ ] HTTP POST/PUT plugins
- [ ] Streaming aggregations

**Target:** 600 LOC | **Plugins:** 25

---

### Week 7-8: Agent Optimization

- [ ] JSON output mode for all commands
- [ ] Example extraction (read without exec)
- [ ] Schema file support
- [ ] Performance optimization
  - Cache plugin discovery (<10ms)
  - Optimize UV subprocess spawning
  - Benchmark pipelines

**Target:** 400 LOC | **Performance:** <10ms discovery, >10k records/sec

---

## Weeks 9-12: Ecosystem & Release

### Week 9: Plugin Distribution

- [ ] Plugin packaging (pip installable)
- [ ] Entry points for plugins
- [ ] Plugin registry/directory
- [ ] Community templates

---

### Week 10: Advanced CLI

- [ ] `jn cat` (exploration command)
- [ ] `jn put` (output command)
- [ ] `jn shape` (schema inference)
- [ ] Shell completions (bash, zsh, fish)

---

### Week 11: Migration & Compatibility

- [ ] Migration tool from oldgen
- [ ] Backward compatibility mode (if needed)
- [ ] Migration guide documentation

---

### Week 12: Release Preparation

- [ ] Security audit
- [ ] Performance benchmarks
- [ ] Release documentation
- [ ] Packaging for PyPI
- [ ] GitHub release

---

## Success Metrics

### Code Quality
- [ ] <5,000 LOC total (vs oldgen 3,500)
- [ ] 90%+ test coverage
- [ ] Zero security vulnerabilities
- [ ] All plugins self-testing

### Performance
- [ ] <10ms plugin discovery (cached)
- [ ] <100ms pipeline overhead per step
- [ ] >10k records/sec throughput

### Functionality
- [ ] 25+ working plugins
- [ ] Full CLI feature parity
- [ ] Agent-friendly design validated

### Documentation
- [ ] Complete API documentation
- [ ] Plugin authoring guide
- [ ] Agent integration guide
- [ ] 10+ working examples

---

## Current Status (2025-11-09)

### ✅ Completed
- **Week 1, Days 1-5: Foundation Complete**
  - Foundation and core plugins
  - Plugin discovery system (regex-based, no imports)
  - Extension registry with caching
  - 4 working plugins (csv_reader, csv_writer, json_reader, ls)
  - Code harvesting and organization
  - Package configuration
  - Plugin organization strategy

### 🔄 In Progress
- Week 2, Day 3: Click-Based CLI

### 📋 Next Up
- Core CLI with Click
- `jn discover` command (list plugins)
- `jn show` command (show plugin details)
- `jn run` command (execute pipelines)

### Metrics
- **LOC:** 1,368 (code) + 400 (docs)
- **Core modules:** 6 (detection, subprocess_utils, discovery, registry, pipeline, executor)
- **Plugins:** 4 working
- **Tests:** 51/51 passing (100%)
- **Coverage:** 68%
- **Dependencies:** 1 (click only!)

---

## Daily Progress Log

### 2025-11-09 - Week 1 & 2 Days 1-2

**Week 1 (Complete):**
- ✅ Moved oldgen/ code
- ✅ Created new structure
- ✅ Harvested detection and subprocess utils
- ✅ Created 4 working plugins
- ✅ Organized plugins by category
- ✅ Updated pyproject.toml
- ✅ Created implementation plan
- ✅ Implemented plugin discovery system (src/jn/discovery.py - 110 LOC)
- ✅ Implemented extension registry (src/jn/registry.py - 108 LOC)
- ✅ Created comprehensive tests (34 tests, 92% coverage)
- ✅ Week 1 complete!

**Week 2 Days 1-2 (Complete):**
- ✅ Implemented automatic pipeline builder (src/jn/pipeline.py - 150 LOC)
  - Auto-detect sources (files, URLs, commands)
  - jq expression detection
  - Output format detection
  - Command argument parsing
- ✅ Implemented pipeline executor (src/jn/executor.py - 150 LOC)
  - Subprocess execution with Unix pipes
  - UV integration for PEP 723 dependencies
  - File I/O redirection
  - Error handling
- ✅ Created pipeline integration tests (17 tests, 100% passing)
- ✅ End-to-end CSV→NDJSON execution verified
- 🔄 Next: Click-based CLI commands

---

## Notes & Decisions

### Architecture Decisions
1. **Click over Typer** - Lighter, more composable
2. **argparse for plugins** - Zero dependencies
3. **Function-based, not classes** - Duck typing, simple
4. **Regex-based discovery** - No imports needed
5. **Bundled plugins** - Immediate value out of box

### JC Vendoring Strategy
- Not copying code verbatim
- Reimplementing as CLI plugins
- Attribution in headers
- MIT license compatible
- Tiers: 15+ commands over 3 weeks

### Key Differences from oldgen
- No Pydantic models
- No import-based config
- No 4-concept registry
- Plugins are standalone CLIs
- UV manages dependencies per-plugin

---

## Risk Mitigation

### Risk: UV dependency issues
**Mitigation:** Fallback to venv, document requirements

### Risk: Performance regression
**Mitigation:** Benchmark each phase, optimize hot paths

### Risk: Plugin API instability
**Mitigation:** Version plugin interface, support multiple versions

### Risk: Discovery complexity
**Mitigation:** Keep regex patterns simple, cache aggressively

---

## References

- `spec/arch/nextgen-redesign.md` - Core architecture
- `spec/arch/nextgen-groundup.md` - Original ground-up plan
- `docs/harvest/code-harvest.md` - Code harvesting analysis
- `docs/harvest/plugin-organization.md` - Plugin strategy
- Kelly Brazil's JC project - Parsing inspiration

---

**Last Updated:** 2025-11-09
**Current Phase:** Week 2, Day 3
**Next Milestone:** Click-based CLI with discover, show, and run commands
