# JN Plugin Architecture Refactoring Plan

**Created:** 2025-11-22
**Status:** In Progress
**Goal:** Eliminate protocol-specific special-casing and plugin boilerplate

---

## Executive Summary

This plan refactors the JN plugin system to eliminate ~760 lines of special-casing and duplication by:

1. **Passing framework context to plugins** (eliminates 363 lines of plugin boilerplate)
2. **Using plugin metadata for capabilities** (eliminates 50 lines of hardcoded lists)
3. **Implementing generic container protocol** (eliminates 135 lines of protocol-specific formatting)
4. **Removing duplicate discovery logic** (eliminates 30 lines)
5. **Cleaning up framework special-cases** (eliminates 182 lines of protocol-specific routing)

**Total Impact:** ~760 lines removed, true plugin extensibility achieved

---

## Current State Assessment

### Problems Identified

1. **Special-casing in core files** (263 lines)
   - `src/jn/cli/commands/inspect.py`: 135 lines of protocol-specific formatting
   - `src/jn/cli/commands/cat.py`: 18 lines of hardcoded plugin detection
   - `src/jn/addressing/resolver.py`: 95 lines of protocol-specific resolution
   - `src/jn/cli/commands/profile.py`: 15 lines of hardcoded type lists

2. **Plugin boilerplate** (363 lines)
   - `duckdb_.py`: 85 lines duplicating framework logic
   - `http_.py`: 227 lines vendored from framework
   - `gmail_.py`: 51 lines of path discovery

3. **Duplicate logic** (30 lines)
   - `src/jn/profiles/service.py`: Hardcoded directory scanning + generic introspection

4. **Repository issues**
   - Binary file committed: `test.duckdb` (536 KB)
   - Temporary analysis doc: `PLUGIN_ARCHITECTURE_RECOMMENDATION.md` (828 lines)

5. **Acknowledged technical debt**
   - `cat.py:315`: Comment admits hardcoded approach is wrong

### Success Criteria

- ✅ Zero protocol-specific logic in framework core
- ✅ Plugins receive all needed context from framework
- ✅ Adding new protocol requires zero framework changes
- ✅ No code duplication between plugins and framework
- ✅ All tests pass
- ✅ No binary files in version control

---

## Implementation Phases

### Phase 1: Fix Immediate Repository Issues ⚡ PRIORITY

**Goal:** Clean up repository hygiene issues

**Tasks:**

1. **Add database files to .gitignore**
   - Add `*.duckdb`, `*.ddb`, `*.db` to `.gitignore`

2. **Remove binary file from repo**
   - `git rm test.duckdb`
   - Update tests to generate databases on-demand

3. **Handle temporary analysis document**
   - Move architectural insights to `spec/done/plugin-architecture.md`
   - Delete `PLUGIN_ARCHITECTURE_RECOMMENDATION.md`

**Risk:** None (cleanup only)
**Impact:** Repository hygiene, prevents future binary commits

---

### Phase 2: Add Plugin Metadata Support

**Goal:** Enable framework to discover plugin capabilities instead of hardcoding

**Tasks:**

1. **Extend plugin metadata schema** (`src/jn/plugins/discovery.py`)
   - Add `manages_parameters: bool` field (default: False)
   - Add `supports_container: bool` field (default: False)
   - Add `container_mode: Optional[str]` field (e.g., "path_count", "query_param")
   - Update `PluginMetadata` dataclass
   - Update metadata parsing from `[tool.jn]`

2. **Update existing plugins with metadata**
   - `duckdb_.py`: `manages_parameters = true, supports_container = true`
   - `http_.py`: `manages_parameters = true, supports_container = true`
   - `gmail_.py`: `manages_parameters = true, supports_container = true`
   - `mcp_.py`: `manages_parameters = true, supports_container = true`

3. **Update cat.py to use metadata** (lines 313-323)
   ```python
   # Before:
   is_protocol_plugin = any(name in path for name in ["duckdb_", ...])

   # After:
   plugin_meta = resolver.get_plugin_metadata(final_stage.plugin_path)
   if plugin_meta.manages_parameters:
       # Skip config/filter separation
   ```

**Risk:** Low (additive changes, backward compatible)
**Impact:** Eliminates hardcoded plugin lists in cat.py (~18 lines)

**Files Modified:**
- `src/jn/plugins/discovery.py`
- `src/jn/cli/commands/cat.py`
- `jn_home/plugins/databases/duckdb_.py`
- `jn_home/plugins/protocols/http_.py`
- `jn_home/plugins/protocols/gmail_.py`
- `jn_home/plugins/protocols/mcp_.py`

---

### Phase 3: Environment Variable Context Passing

**Goal:** Pass JN_HOME and profile paths to plugins via environment

**Tasks:**

1. **Define environment variable contract**
   - `JN_HOME`: Base directory for JN configuration
   - `JN_PROFILE_DIR`: Plugin-specific profile directory (e.g., `$JN_HOME/profiles/duckdb`)
   - `JN_WORKING_DIR`: Current working directory
   - `JN_PROJECT_DIR`: Project .jn directory if exists

2. **Update plugin invocation** (`src/jn/core/pipeline.py`, `src/jn/profiles/service.py`)
   ```python
   env = os.environ.copy()
   env['JN_HOME'] = str(get_jn_home())
   env['JN_PROFILE_DIR'] = str(get_profile_dir(plugin_type))
   env['JN_WORKING_DIR'] = str(Path.cwd())

   process = subprocess.Popen(
       ['uv', 'run', '--script', str(plugin_path), ...],
       env=env,
       ...
   )
   ```

3. **Update plugins to use environment variables**
   - `duckdb_.py`: Replace `_get_profile_paths()` with `os.getenv('JN_PROFILE_DIR')`
   - `http_.py`: Replace `find_profile_paths()` with environment variable
   - `gmail_.py`: Use `JN_HOME` for credential paths

4. **Document environment contract**
   - Update `spec/done/plugin-specification.md` with environment variables section

**Risk:** Low (plugins can still fall back to old behavior if env vars not set)
**Impact:** Enables plugin simplification in next phase

**Files Modified:**
- `src/jn/core/pipeline.py`
- `src/jn/profiles/service.py`
- `src/jn/context.py` (add helper functions)
- `spec/done/plugin-specification.md`

---

### Phase 4: Implement Generic Container Protocol

**Goal:** Eliminate protocol-specific formatting in inspect.py

**Tasks:**

1. **Define standard container metadata format**
   ```json
   {
     "_type": "container_listing",
     "_plugin": "duckdb",
     "_container": "test.duckdb",
     "items": [
       {"name": "users", "type": "table", "columns": 5},
       {"name": "orders", "type": "table", "columns": 8}
     ]
   }
   ```

2. **Implement generic formatter** (`src/jn/cli/commands/inspect.py`)
   ```python
   def _format_container_generic(result: dict) -> str:
       """Generic formatter for container listings."""
       lines = []
       container = result.get('_container', 'unknown')
       plugin = result.get('_plugin', 'unknown')

       lines.append(f"Container: {container} ({plugin})")
       lines.append("")

       items = result.get('items', [])
       if items:
           lines.append("Items:")
           for item in items:
               name = item.get('name', 'unknown')
               lines.append(f"  • {name}")

               # Show other fields as key: value
               for key, value in item.items():
                   if key != 'name' and not key.startswith('_'):
                       lines.append(f"    {key}: {value}")

       return "\n".join(lines)
   ```

3. **Update plugins to emit standard format**
   - `duckdb_.py`: Update `_list_tables()` to emit standard format
   - `http_.py`: Update source listings to emit standard format
   - `gmail_.py`: Update label listings to emit standard format
   - `mcp_.py`: Update tool/resource listings to emit standard format

4. **Replace protocol-specific formatters** (`src/jn/cli/commands/inspect.py`)
   - Remove `_format_container_text()` lines 68-203 (135 lines)
   - Replace with call to `_format_container_generic()`

**Risk:** Medium (requires coordinated plugin updates)
**Impact:** Eliminates 135 lines of protocol-specific formatting

**Files Modified:**
- `src/jn/cli/commands/inspect.py`
- `jn_home/plugins/databases/duckdb_.py`
- `jn_home/plugins/protocols/http_.py`
- `jn_home/plugins/protocols/gmail_.py`
- `jn_home/plugins/protocols/mcp_.py`

---

### Phase 5: Remove Special-Casing from Framework

**Goal:** Eliminate hardcoded protocol logic in resolver and profile service

**Tasks:**

1. **Remove hardcoded profile type lists** (`src/jn/cli/commands/profile.py`)
   ```python
   # Before:
   type=click.Choice(["jq", "gmail", "http", "mcp", "duckdb"])

   # After:
   type=click.Choice(_get_profile_types())  # Dynamic from plugins

   def _get_profile_types():
       """Get available profile types from plugin registry."""
       plugins = get_cached_plugins_with_fallback()
       types = set()
       for plugin in plugins.values():
           if plugin.role == "protocol":
               types.add(plugin.path.stem.rstrip('_'))
       return sorted(types)
   ```

2. **Remove hardcoded type labels** (`src/jn/cli/commands/profile.py`)
   - Generate labels dynamically: `f"{profile_type.title()} Profiles"`

3. **Simplify profile namespace resolution** (`src/jn/addressing/resolver.py`)
   - Lines 339-370: Remove hardcoded iteration through protocol plugins
   - Use plugin metadata to map namespaces to plugins
   - Remove special-case for HTTP default fallback (line 370)

4. **Remove protocol-specific URL resolution** (`src/jn/addressing/resolver.py`)
   - Lines 750-779: Remove gmail-specific and http-specific resolution
   - Pass full address to all protocol plugins, let them resolve internally

5. **Remove duplicate profile discovery** (`src/jn/profiles/service.py`)
   - Lines 192-221: Delete hardcoded directory scanning
   - Keep only generic plugin introspection (lines 224-273)

6. **Remove container detection special-cases** (`src/jn/cli/commands/inspect.py`)
   - Lines 34-47: Remove hardcoded gmail:// and duckdb:// detection
   - Ask plugin via metadata or special mode

**Risk:** High (changes core routing logic)
**Impact:** Eliminates 182 lines of special-casing, achieves true protocol-agnosticism

**Files Modified:**
- `src/jn/cli/commands/profile.py`
- `src/jn/addressing/resolver.py`
- `src/jn/profiles/service.py`
- `src/jn/cli/commands/inspect.py`

---

### Phase 6: Refactor Plugins to Use New Interface

**Goal:** Remove boilerplate from plugins now that framework provides context

**Tasks:**

1. **Simplify duckdb_.py** (remove 85 lines)
   - Delete `_get_profile_paths()` (lines 23-47)
   - Replace with `os.getenv('JN_PROFILE_DIR')`
   - Simplify `_load_profile()` to use environment variables
   - Remove duplicate `_list_profile_queries()` (use `inspect_profiles()`)

2. **Simplify http_.py** (remove 227 lines)
   - Delete entire vendored section (lines 54-281)
   - Import from framework instead (allowed for protocols managing profiles)
   - Or use environment variables if framework passes resolved profile data

3. **Simplify gmail_.py** (remove 51 lines)
   - Use `JN_HOME` environment variable for credential paths
   - Remove hardcoded path construction

4. **Update all plugins to use standard container format**
   - Ensure consistent `_type`, `_plugin`, `_container`, `items` structure

**Risk:** Medium (requires thorough testing)
**Impact:** Removes 363 lines of boilerplate, plugins become simpler

**Files Modified:**
- `jn_home/plugins/databases/duckdb_.py`
- `jn_home/plugins/protocols/http_.py`
- `jn_home/plugins/protocols/gmail_.py`

---

### Phase 7: Update Tests and Documentation

**Goal:** Ensure all tests pass and documentation reflects new architecture

**Tasks:**

1. **Update tests to generate test databases on-demand**
   - `tests/cli/test_duckdb.py`: Create test.duckdb in fixture
   - Ensure tests clean up after themselves

2. **Update plugin tests**
   - Test that plugins correctly use environment variables
   - Test generic container protocol
   - Test metadata-driven capabilities

3. **Update documentation**
   - `spec/done/plugin-specification.md`: Document environment variables
   - `spec/done/plugin-specification.md`: Document container protocol
   - `spec/done/plugin-specification.md`: Document metadata fields
   - `CLAUDE.md`: Update with new plugin interface contract
   - Create `spec/done/plugin-refactoring.md`: Document this refactoring

4. **Run full test suite**
   - `make test`
   - `make check`
   - Fix any failures

**Risk:** Low (validation only)
**Impact:** Ensures quality and provides reference for future plugin authors

**Files Modified:**
- `tests/cli/test_duckdb.py`
- `tests/plugins/` (new tests for environment variables)
- `spec/done/plugin-specification.md`
- `spec/done/plugin-refactoring.md` (new)
- `CLAUDE.md`

---

### Phase 8: Final Cleanup and Commit

**Goal:** Clean up temporary files and commit all changes

**Tasks:**

1. **Archive analysis document**
   - Move key insights from `PLUGIN_ARCHITECTURE_RECOMMENDATION.md` to `spec/done/plugin-architecture.md`
   - Delete `PLUGIN_ARCHITECTURE_RECOMMENDATION.md`
   - Move this `REFACTORING_PLAN.md` to `spec/done/plugin-refactoring-plan.md`

2. **Verify all changes**
   - Run `make test` and `make check`
   - Manually test key workflows:
     - `jn cat duckdb://test.duckdb/table`
     - `jn cat @test/all-users`
     - `jn profile list --type duckdb`
     - `jn inspect duckdb://test.duckdb`

3. **Commit changes**
   - Create atomic commits for each phase
   - Write clear commit messages
   - Reference this refactoring plan

4. **Push to branch**
   - Push to `claude/review-plugin-architecture-01DunmeuVpb79Gy3uzCU8oEN`

**Risk:** None (verification only)
**Impact:** Clean commit history documenting refactoring

---

## Rollback Strategy

If issues are discovered during implementation:

1. **Phase 1**: No rollback needed (cleanup only)
2. **Phase 2**: Metadata is optional, no breaking changes
3. **Phase 3**: Environment variables are optional, plugins fall back
4. **Phase 4**: Keep old formatters as fallback during transition
5. **Phase 5**: High risk - test thoroughly before committing
6. **Phase 6**: High risk - test thoroughly before committing

**Mitigation:** Implement phases incrementally, commit after each phase, run full test suite between phases.

---

## Metrics

### Lines Removed

| Category | Current | After | Removed | % Reduction |
|----------|---------|-------|---------|-------------|
| Framework special-casing | 263 | 0 | 263 | 100% |
| Plugin boilerplate | 363 | 0 | 363 | 100% |
| Protocol-specific formatting | 135 | ~10 | ~125 | 93% |
| Duplicate discovery | 30 | 0 | 30 | 100% |
| **TOTAL** | **791** | **~10** | **~781** | **98.7%** |

### Complexity Reduction

- **Adding postgres:// plugin**: 0 framework changes (vs. current ~50 lines)
- **Plugin implementation**: -70% code (no discovery boilerplate)
- **Framework maintainability**: +300% (generic vs. protocol-specific)

---

## Timeline Estimate

- **Phase 1**: 30 minutes (repository cleanup)
- **Phase 2**: 1-2 hours (metadata support)
- **Phase 3**: 1-2 hours (environment variables)
- **Phase 4**: 2-3 hours (generic container protocol)
- **Phase 5**: 2-3 hours (remove special-casing)
- **Phase 6**: 2-3 hours (refactor plugins)
- **Phase 7**: 1-2 hours (tests and docs)
- **Phase 8**: 30 minutes (cleanup and commit)

**Total**: 10-16 hours of focused work

---

## Success Validation

After completion, verify:

- ✅ `make test` passes with 100% success rate
- ✅ `make check` passes with zero violations
- ✅ `jn cat duckdb://test.duckdb/users` works
- ✅ `jn cat @test/all-users` works
- ✅ `jn profile list --type duckdb` works
- ✅ `jn inspect duckdb://test.duckdb` shows tables
- ✅ No hardcoded protocol names in framework core files
- ✅ Plugin metadata drives all capabilities
- ✅ Plugins use environment variables for context
- ✅ Generic container formatter works for all protocols

---

## References

- Original analysis: `PLUGIN_ARCHITECTURE_RECOMMENDATION.md`
- Plugin specification: `spec/done/plugin-specification.md`
- Backpressure architecture: `spec/done/arch-backpressure.md`
- Profile architecture: `spec/done/profile-architecture.md`
