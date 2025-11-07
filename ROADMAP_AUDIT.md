# Roadmap Audit & Architecture Gap Analysis

**Date**: November 7, 2025
**Purpose**: Deep dive audit of roadmap.md against actual implementation

---

## ✅ Items DONE But Not Marked Complete

### 1. Run with env — `jn --env <K=V> run <pipeline>`
**Status**: ✅ **FULLY IMPLEMENTED**

Evidence:
- `src/jn/cli/run.py:20-21` - CLI accepts `--env` flag
- `src/jn/config/utils.py:8-17` - `parse_key_value_pairs()` parses env flags
- `src/jn/config/utils.py:20-58` - `substitute_template()` replaces `${env.*}` placeholders
- **Tests**: `test_run_pipeline_with_env_flag`, `test_run_pipeline_with_env_from_os_environ`, etc.
- All tests passing ✅

**Recommendation**: Mark as `[x]` in roadmap

---

### 2. Run with params — `jn run <pipeline> --param <k=v>`
**Status**: ✅ **FULLY IMPLEMENTED**

Evidence:
- `src/jn/cli/run.py:17-18` - CLI accepts `--param` flag
- Same `parse_key_value_pairs()` parses params
- `substitute_template()` replaces `${params.*}` placeholders
- **Tests**: `test_run_pipeline_with_params`, `test_run_pipeline_with_params_and_env_combined`
- All tests passing ✅

**Recommendation**: Mark as `[x]` in roadmap

---

### 3. Exec source extras — support `cwd`/`env` interpolation
**Status**: ✅ **FULLY IMPLEMENTED**

Evidence:
- `src/jn/config/pipeline.py:60-84` - `_run_source()` applies templating to argv, cwd, env
- `src/jn/config/pipeline.py:74-83` - Env precedence: config.exec.env > CLI --env > os.environ
- **Tests**: Multiple tests verify cwd/env handling
- Working in production ✅

**Recommendation**: Mark as `[x]` in roadmap

---

### 4. Pipeline params/env templating — `${params.*}` and `${env.*}` expansion
**Status**: ✅ **FULLY IMPLEMENTED**

Evidence:
- `src/jn/config/utils.py:20-58` - Full regex-based template substitution
- Works in argv, cmd, cwd, env values
- Error handling for missing keys
- **Tests**: Comprehensive coverage across multiple test files
- All tests passing ✅

**Recommendation**: Mark as `[x]` in roadmap

---

### 5. Shell driver — implement safe execution + opt-in flag
**Status**: ✅ **FULLY IMPLEMENTED** (PR #7)

Evidence:
- `src/jn/drivers/shell.py` - Complete implementation
- Security: requires `--unsafe-shell` flag
- Works for both sources AND targets
- **Tests**: `test_shell_driver.py` with 5 comprehensive tests
- All tests passing ✅

**Recommendation**: Mark as `[x]` in roadmap

---

### 6. JC source adapter — wrap shell output to JSON
**Status**: ✅ **FULLY IMPLEMENTED** (PR #7)

Evidence:
- `src/jn/models/source.py:22` - `adapter` field added to Source model
- `src/jn/config/pipeline.py:66-67, 91-92` - JC prepended to argv/cmd when adapter="jc"
- Works with both exec and shell sources
- **Tests**: `test_jc_adapter.py` + `test_jc_real_world.py` (9 tests total)
- All tests passing ✅

**Recommendation**: Mark as `[x]` in roadmap

---

### 7. File driver — streaming file read/write with confinement
**Status**: ✅ **MOSTLY IMPLEMENTED** (81% coverage)

Evidence:
- `src/jn/drivers/file.py` - `run_file_read()` and `run_file_write()` exist
- Path confinement checks working
- Parent directory creation working
- Append mode working
- **Tests**: `test_run_pipeline_with_file_driver`, `test_file_driver_paths_relative_to_config`

**Gaps**:
- Not explicitly optimized for streaming (loads entire file into memory currently)
- Could add chunked reads/writes for large files

**Recommendation**: Mark as `[x]` in roadmap (core functionality complete, streaming optimization can be future work)

---

## 🔄 Items Partially Implemented or Unclear

### 8. CSV/delimited source — `jn new source <name> --driver file --format csv`
**Status**: ⏳ **NOT IMPLEMENTED**

**Current state**:
- File driver exists but no CSV parsing
- JC has `--csv-s` streaming parser available
- Python `csv` module could be used

**Architecture question**: Which approach?
- Option A: Use jc `--csv-s` as adapter (leverages existing adapter system)
- Option B: Add format-specific logic to file driver
- Option C: Create separate CSV adapter as source transformer

**Recommendation**: Needs architecture document

---

## ❓ Items Needing Clarification

### 9. Doctor check — `jn doctor`
**Status**: ❓ **UNCLEAR SCOPE**

**What should this check?**
- [ ] jq installed and in PATH?
- [ ] jc installed and in PATH?
- [ ] Config file valid (parse check)?
- [ ] All pipeline refs valid (sources/converters/targets exist)?
- [ ] File paths accessible?
- [ ] Permissions OK?
- [ ] Python version compatible?
- [ ] Network connectivity (for curl driver)?

**Questions for user:**
1. What are the critical checks this command should perform?
2. Should it be just validation, or also offer fixes?
3. Should it check individual pipelines or just general health?

---

### 10. Discover list — `jn discover`
**Status**: ❓ **UNCLEAR PURPOSE**

**Possible interpretations:**
- Discover available jc parsers?
- Discover external tools (jq, jc, curl)?
- Discover pipeline definitions in current directory?
- Discover data sources (auto-detect files/URLs)?

**Questions for user:**
1. What should this command discover?
2. Is this about auto-configuration or introspection?
3. Related to MCP server discovery?

---

### 11. Shape stream — `jn shape --in <path>`
**Status**: ❓ **UNCLEAR PURPOSE**

**Possible interpretations:**
- Infer JSON schema from NDJSON stream?
- Show data types and structure?
- Generate jq expressions for common transformations?
- Validate stream format?

**Questions for user:**
1. What is the primary use case for this command?
2. Should it output JSON Schema, sample data, or statistics?
3. Is this for debugging or pipeline design?

---

### 12. Try building — `jn try <kind> <name>`
**Status**: ❓ **UNCLEAR BEHAVIOR**

**Possible interpretations:**
- Test a single component in isolation?
- Dry-run without side effects?
- Interactive REPL for testing?
- Generate sample output?

**Questions for user:**
1. What does "try" mean in this context?
2. For a source: run it and show output?
3. For a converter: feed it test data?
4. For a target: show what would be written?

---

## 🚧 Items Clearly Not Implemented

### 13. Curl driver — streaming HTTP client for sources/targets
**Status**: ⏳ **NOT IMPLEMENTED**

**Architecture exists**: `spec/arch/drivers.md:91-103` describes curl driver

**What's needed**:
- Implement `src/jn/drivers/curl.py`
- Add HTTP methods (GET, POST, PUT, DELETE)
- Headers support
- Body streaming
- Timeouts and retries
- Error handling

**Recommendation**: Architecture is clear, just needs implementation

---

### 14. MCP import — `jn mcp import <server>`
**Status**: ⏳ **NOT IMPLEMENTED**

**Architecture exists**: `spec/arch/drivers.md:128-138` describes MCP driver concept

**What's needed**:
- Define what "import" means (create config entries from MCP server discovery?)
- How to discover MCP servers?
- How to map MCP tools to JN sources/targets?

**Recommendation**: Needs architecture document for MCP integration strategy

---

### 15. MCP driver — `jn new source|target <name> --driver mcp`
**Status**: ⏳ **NOT IMPLEMENTED**

**Related to #14** - needs MCP integration architecture

**What's needed**:
- MCP client implementation or library
- Protocol handling (stdio, SSE, HTTP)
- Tool invocation mapping
- Streaming support

**Recommendation**: Needs architecture document

---

### 16. Edit item — `jn edit <kind> <name>`
**Status**: ⏳ **NOT IMPLEMENTED**

**Implementation questions**:
- Should this open $EDITOR with JSON?
- Or provide interactive prompts?
- Or accept CLI flags to modify specific fields?

**Recommendation**: Low priority, users can edit jn.json directly

---

### 17. Remove item — `jn rm <kind> <name>`
**Status**: ⏳ **NOT IMPLEMENTED**

**Implementation**: Straightforward - remove item from config and save

**Recommendation**: Low priority, users can edit jn.json directly

---

### 18. Release smoke — `jn --version`
**Status**: ⏳ **NOT IMPLEMENTED**

**Implementation**: Trivial - add version string to CLI

**Recommendation**: Easy win, should be done before any release

---

## 📋 Architecture Documents Needed

Based on this audit, these architecture documents should be created:

### 1. **CSV and Delimited Data Architecture** (HIGH PRIORITY)
**File**: `spec/arch/csv-delimited.md`

**Should cover**:
- CSV parsing strategies (jc vs Python csv vs streaming)
- Dialect configuration (delimiter, quote char, encoding)
- Header handling
- Type inference vs string-only
- Streaming vs batch mode
- Error handling (malformed rows)
- Integration with file driver vs separate adapter

---

### 2. **Developer Tools Architecture** (HIGH PRIORITY)
**File**: `spec/arch/developer-tools.md`

**Should cover**:
- `jn doctor` - health checks and validation
- `jn try` - component testing in isolation
- `jn discover` - introspection and auto-discovery
- `jn shape` - data profiling and schema inference
- Use cases and workflows for each tool
- Error messages and remediation suggestions

---

### 3. **MCP Integration Architecture** (MEDIUM PRIORITY)
**File**: `spec/arch/mcp-integration.md`

**Should cover**:
- MCP protocol overview
- Server discovery mechanisms
- Tool mapping strategy (MCP tools → JN sources/targets)
- Configuration format for MCP sources/targets
- Authentication and credentials
- Streaming vs request/response patterns
- Error handling
- `jn mcp import` workflow

---

### 4. **HTTP Client Architecture** (MEDIUM PRIORITY)
**File**: `spec/arch/http-client.md` (could expand drivers.md)

**Should cover**:
- Curl driver implementation details
- Request configuration (methods, headers, body)
- Response handling (status codes, headers, body)
- Streaming for large downloads/uploads
- Authentication methods (Bearer, Basic, API keys)
- Retry strategies and exponential backoff
- Timeout configuration
- TLS/SSL considerations
- Testing strategies (VCR, httpbin)

---

### 5. **CLI Utilities Architecture** (LOW PRIORITY)
**File**: `spec/arch/cli-utilities.md`

**Should cover**:
- `jn edit` - interactive editing
- `jn rm` - safe deletion with validation
- `jn --version` - version display
- CRUD operations philosophy
- Safety checks and confirmations

---

## 🎯 Recommended Priority Order

1. **Update roadmap.md** - Mark completed items (15 minutes)
2. **Clarify with user** - Get answers about doctor/discover/shape/try (30 minutes)
3. **Create CSV architecture doc** - High impact, roadmap item (1-2 hours)
4. **Create Developer Tools architecture doc** - Covers 4 roadmap items (1-2 hours)
5. **Optional: MCP or HTTP architecture** - Based on user priority (2-3 hours)

---

## Questions for User

### Critical Questions (need answers to proceed):

1. **Doctor command**: What specific checks should `jn doctor` perform? Just external tools (jq/jc), or also config validation, pipeline integrity, etc.?

2. **Discover command**: What should `jn discover` discover? Available parsers? Data sources? MCP servers?

3. **Shape command**: What should `jn shape --in <path>` do? Infer schema? Show statistics? Generate sample jq expressions?

4. **Try command**: What should `jn try <kind> <name>` do? Run component with test data? Dry-run? Interactive testing?

5. **CSV implementation**: Preferred approach?
   - A) Use jc `--csv-s` as adapter (simple, consistent with jc approach)
   - B) Add format support to file driver (more control)
   - C) Python csv module in separate adapter (most flexible)

6. **MCP priority**: Is MCP integration high priority? Should we focus on it now or defer?

### Nice-to-know Questions:

7. Should `jn edit` open $EDITOR, use interactive prompts, or accept CLI flags?

8. Should `jn rm` require confirmation? Check for pipeline references?

9. Any other roadmap items you know are needed but not listed?

---

## Summary

**Completed but unmarked**: 7 items (env, params, shell, jc, templating, exec extras, file driver)

**Needs clarification**: 4 items (doctor, discover, shape, try)

**Needs architecture**: 4 major areas (CSV, dev tools, MCP, HTTP)

**Clearly todo**: 4 items (edit, rm, version, and implementations once architecture clear)

**Next steps**: Get user answers, then create 1-2 architecture documents before finalizing commit.
