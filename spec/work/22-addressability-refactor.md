# Addressability System Refactor

**Status:** 🚧 PLANNED
**Type:** Core Framework Refactor
**Effort:** High (5-7 days)
**Priority:** Critical (foundation for v5)

## Overview

Implement the universal addressability system defined in `spec/design/addressability.md`. This refactor introduces a unified syntax for addressing all data sources and destinations in JN, with two operators: `~` for format override and `?` for parameters.

**Core Syntax:**
```
address[~format][?parameters]
```

**Key Innovation:** Self-contained addressing where the complete address (source + format + config) is in a single string, making it composable, discoverable, and agent-friendly.

## Motivation

**Current Problems:**
1. **Scattered configuration:** Format hints and parameters spread across multiple flags
2. **Inconsistent syntax:** Different patterns for files, protocols, profiles, stdin
3. **Agent confusion:** AI agents struggle to discover and compose data sources
4. **Limited composability:** Hard to mix local files, remote APIs, and protocols

**After Addressability:**
```bash
# Before (scattered)
jn cat data.txt --format csv --delimiter ';'

# After (self-contained)
jn cat "data.txt~csv?delimiter=;"

# Complex pipeline (before: impossible, after: natural)
jn cat \
  sales/*.csv \
  "@stripe/charges?created_after=2024-01-01" \
  "https://api.example.com/orders.json" \
  "@gmail/receipts?has=attachment" \
  | jn filter '@builtin/deduplicate' \
  | jn put "-~table.grid"
```

## Key Features

### 1. Address Parsing
- Parse `address[~format][?parameters]` syntax
- Extract base address, format override, parameters
- Handle URL encoding and special characters
- Support quoted addresses for shell safety

### 2. Format Override (`~` operator)
- Override auto-detected format
- Support shorthand formats: `table.grid` → `table?tablefmt=grid`
- Apply to files: `file.txt~csv`
- Apply to stdin/stdout: `-~csv`, `-~table.grid`

### 3. Parameters (`?` operator)
- Parse URL-style query strings
- Pass to both profiles AND plugins
- Support plugin configuration (delimiter, indent, tablefmt, etc.)
- Support profile parameters (gene, limit, etc.)

### 4. Address Types
- **Files:** `path/to/file.ext[~format][?config]`
- **Protocol URLs:** `protocol://path[?params]`
- **Profile references:** `@profile/component[?params]`
- **Stdin/stdout:** `-[~format][?config]`
- **Plugin references:** `@plugin`

### 5. Multi-Source Concatenation
- Support multiple addresses in `jn cat`
- Process sequentially, output NDJSON
- Auto-detect format per source
- Mix local files, APIs, protocols

### 6. Plugin Configuration
- CSV: `?delimiter=;`, `?header=false`
- JSON: `?indent=4`, `?indent=0`
- Table: `?tablefmt=grid`, `?maxcolwidths=20`, `?showindex=true`

## Architecture

### Module Structure

```
src/jn/
├── addressing/           # New module for addressability
│   ├── __init__.py       # Re-exports
│   ├── parser.py         # Address parsing
│   ├── resolver.py       # Address resolution
│   ├── types.py          # Address types and dataclasses
│   └── config.py         # Plugin configuration
```

### Core Classes

```python
# src/jn/addressing/types.py

from dataclasses import dataclass
from typing import Optional, Dict, Literal

@dataclass
class Address:
    """Parsed address with format override and parameters."""
    raw: str                          # Original address string
    base: str                         # Base address (file, URL, @profile, -)
    format_override: Optional[str]    # Format after ~ (csv, json, table.grid)
    parameters: Dict[str, str]        # Query string parameters
    type: Literal["file", "protocol", "profile", "plugin", "stdio"]

@dataclass
class ResolvedAddress:
    """Address resolved to plugin + config."""
    address: Address                  # Original parsed address
    plugin: Plugin                    # Plugin to use
    config: Dict[str, any]            # Plugin configuration
    url: Optional[str]                # Resolved URL (for protocols/profiles)
```

### Parser Implementation

```python
# src/jn/addressing/parser.py

import re
from urllib.parse import urlparse, parse_qs
from .types import Address

def parse_address(raw: str) -> Address:
    """Parse address[~format][?parameters] syntax.

    Examples:
        "file.csv" → Address(base="file.csv", format=None, params={})
        "file.txt~csv" → Address(base="file.txt", format="csv", params={})
        "-~csv?delimiter=;" → Address(base="-", format="csv", params={"delimiter": ";"})
        "@api/source?limit=100" → Address(base="@api/source", format=None, params={"limit": "100"})
    """
    # Extract parameters (everything after ?)
    if '?' in raw:
        addr_part, query_string = raw.split('?', 1)
        parameters = parse_qs(query_string, keep_blank_values=True)
        # Flatten single-item lists: {"key": ["value"]} → {"key": "value"}
        parameters = {k: v[0] if len(v) == 1 else v for k, v in parameters.items()}
    else:
        addr_part = raw
        parameters = {}

    # Extract format override (everything after ~)
    if '~' in addr_part:
        base, format_override = addr_part.rsplit('~', 1)
        # Expand shorthand: "table.grid" → "table" + params["tablefmt"] = "grid"
        if '.' in format_override:
            format_name, variant = format_override.split('.', 1)
            format_override = format_name
            # Shorthand expansion based on format
            if format_name == "table":
                parameters.setdefault("tablefmt", variant)
    else:
        base = addr_part
        format_override = None

    # Determine address type
    if base == '-':
        addr_type = "stdio"
    elif base.startswith('@'):
        if '/' in base:
            addr_type = "profile"  # @namespace/component
        else:
            addr_type = "plugin"   # @plugin
    elif '://' in base:
        addr_type = "protocol"     # http://, s3://, gmail://
    else:
        addr_type = "file"         # Filesystem path

    return Address(
        raw=raw,
        base=base,
        format_override=format_override,
        parameters=parameters,
        type=addr_type
    )
```

### Resolver Implementation

```python
# src/jn/addressing/resolver.py

from pathlib import Path
from .types import Address, ResolvedAddress
from ..plugins.registry import PluginRegistry
from ..plugins.service import PluginService

class AddressResolver:
    """Resolve addresses to plugins and configurations."""

    def __init__(self, registry: PluginRegistry, plugin_service: PluginService):
        self.registry = registry
        self.plugin_service = plugin_service

    def resolve(self, address: Address, mode: str = "read") -> ResolvedAddress:
        """Resolve address to plugin + config.

        Args:
            address: Parsed address
            mode: "read" or "write"

        Returns:
            ResolvedAddress with plugin and configuration
        """
        # 1. Determine plugin
        if address.format_override:
            # Explicit format override
            plugin = self._find_plugin_by_format(address.format_override)
        elif address.type == "protocol":
            # Protocol plugin (http://, s3://, gmail://)
            plugin = self._find_plugin_by_protocol(address.base)
        elif address.type == "profile":
            # Profile reference (@namespace/component)
            plugin = self._resolve_profile(address.base)
        elif address.type == "plugin":
            # Direct plugin reference (@plugin)
            plugin = self._find_plugin_by_name(address.base[1:])
        elif address.type == "file":
            # Auto-detect from extension
            plugin = self.registry.find_plugin(address.base, mode=mode)
        elif address.type == "stdio":
            # Stdin/stdout - default to NDJSON if no override
            plugin = self._find_plugin_by_format("ndjson")
        else:
            raise ValueError(f"Unknown address type: {address.type}")

        # 2. Build configuration from parameters
        config = self._build_config(address.parameters, plugin)

        # 3. Resolve URL (for protocols/profiles)
        url = self._resolve_url(address)

        return ResolvedAddress(
            address=address,
            plugin=plugin,
            config=config,
            url=url
        )

    def _find_plugin_by_format(self, format_name: str) -> Plugin:
        """Find plugin by format name (csv, json, table, etc.)."""
        # Search for plugin with matching format name
        # Try: formats/{format_name}_.py or protocols/{format_name}_.py
        ...

    def _find_plugin_by_protocol(self, url: str) -> Plugin:
        """Find plugin by protocol (http://, s3://, etc.)."""
        protocol = url.split('://')[0]
        # Search for protocol plugin: protocols/{protocol}_.py
        ...

    def _resolve_profile(self, profile_ref: str) -> Plugin:
        """Resolve profile reference to plugin + config.

        Example:
            @genomoncology/alterations
            → Load profiles/http/genomoncology/_meta.json
            → Load profiles/http/genomoncology/alterations.json
            → Return HTTP plugin with merged config
        """
        ...

    def _build_config(self, parameters: dict, plugin: Plugin) -> dict:
        """Build plugin configuration from parameters.

        Maps parameter names to plugin config structure:
        - delimiter → csv plugin's delimiter param
        - indent → json plugin's indent param
        - tablefmt → table plugin's format param
        """
        ...

    def _resolve_url(self, address: Address) -> Optional[str]:
        """Resolve address to URL (for protocols/profiles)."""
        if address.type == "protocol":
            return address.base  # Already a URL
        elif address.type == "profile":
            # Load profile and build URL with parameters
            ...
        return None
```

## Implementation Plan

### Phase 1: Core Parsing (Day 1-2)
- [ ] Create `src/jn/addressing/` module
- [ ] Implement `Address` and `ResolvedAddress` dataclasses
- [ ] Implement `parse_address()` function
- [ ] Support all address types (file, protocol, profile, plugin, stdio)
- [ ] Handle format override (`~` operator)
- [ ] Parse parameters (`?` operator)
- [ ] Expand shorthand formats (`table.grid` → `table?tablefmt=grid`)
- [ ] Unit tests for parser

**Test cases:**
```python
# Files
assert parse_address("data.csv").base == "data.csv"
assert parse_address("data.txt~csv").format_override == "csv"
assert parse_address("data.csv~csv?delimiter=;").parameters == {"delimiter": ";"}

# Protocols
assert parse_address("http://example.com/data.json").type == "protocol"
assert parse_address("s3://bucket/key.csv").type == "protocol"
assert parse_address("gmail://me/messages?from=boss").parameters == {"from": "boss"}

# Profiles
assert parse_address("@genomoncology/alterations?gene=BRAF").type == "profile"
assert parse_address("@gmail/inbox").type == "profile"

# Stdin/stdout
assert parse_address("-").type == "stdio"
assert parse_address("-~csv").format_override == "csv"
assert parse_address("-~table.grid").parameters == {"tablefmt": "grid"}

# Shorthand expansion
addr = parse_address("-~table.grid")
assert addr.format_override == "table"
assert addr.parameters["tablefmt"] == "grid"
```

### Phase 2: Address Resolution (Day 3-4)
- [ ] Implement `AddressResolver` class
- [ ] Plugin lookup by format name
- [ ] Plugin lookup by protocol
- [ ] Profile resolution (load _meta.json + component.json)
- [ ] Config building from parameters
- [ ] URL resolution for protocols/profiles
- [ ] Integration with existing `PluginRegistry`
- [ ] Unit tests for resolver

**Test cases:**
```python
# Format override
addr = parse_address("data.txt~csv")
resolved = resolver.resolve(addr)
assert resolved.plugin.name == "csv"

# Protocol detection
addr = parse_address("http://example.com/data.json")
resolved = resolver.resolve(addr)
assert resolved.plugin.name == "http"

# Profile resolution
addr = parse_address("@genomoncology/alterations?gene=BRAF")
resolved = resolver.resolve(addr)
assert resolved.plugin.name == "http"
assert resolved.url == "https://api.genomoncology.io/api/alterations?gene=BRAF"

# Config mapping
addr = parse_address("data.csv~csv?delimiter=;")
resolved = resolver.resolve(addr)
assert resolved.config["delimiter"] == ";"
```

### Phase 3: Command Integration (Day 5-6)
- [ ] Update `jn cat` to use addressability system
- [ ] Update `jn put` to use addressability system
- [ ] Update `jn filter` to handle profile/plugin references
- [ ] Update `jn run` to use new addressing
- [ ] Multi-source concatenation in `jn cat`
- [ ] Pass config to plugins via command-line args
- [ ] Integration tests for all commands

**Changes:**
```python
# src/jn/cli/commands/cat.py (before)
def cat(sources: list[str], format: str = None, **kwargs):
    for source in sources:
        plugin = registry.find_plugin(source)
        # Run plugin...

# src/jn/cli/commands/cat.py (after)
def cat(addresses: list[str]):
    from jn.addressing import parse_address, AddressResolver

    resolver = AddressResolver(registry, plugin_service)

    for addr_str in addresses:
        # Parse address
        addr = parse_address(addr_str)

        # Resolve to plugin + config
        resolved = resolver.resolve(addr, mode="read")

        # Run plugin with config
        run_plugin(resolved.plugin, resolved.config, resolved.url)
```

### Phase 4: Plugin Configuration (Day 6-7)
- [ ] Update CSV plugin to accept config params (delimiter, header)
- [ ] Update JSON plugin to accept config params (indent)
- [ ] Create/update table plugin with config params (tablefmt, maxcolwidths, showindex, alignment)
- [ ] Update all plugins to accept `--config key=value` args
- [ ] Document plugin configuration interface
- [ ] Integration tests with real plugins

**Plugin Interface:**
```python
# Plugins receive config via CLI args
# Framework translates: config={"delimiter": ";"} → --config delimiter=;

python csv_.py --mode read --config delimiter=;
python json_.py --mode write --config indent=4
python table_.py --mode write --config tablefmt=grid --config maxcolwidths=20
```

### Phase 5: Documentation & Polish (Day 7)
- [ ] Update `CLAUDE.md` with addressing examples
- [ ] Update README with new syntax
- [ ] Add examples to `spec/workflows/`
- [ ] Update all existing work tickets to use new syntax
- [ ] Migration guide for users (old → new syntax)
- [ ] Backward compatibility notes

## Examples

### Basic Files
```bash
# Auto-detect format
jn cat data.csv | jn put output.json

# Format override
jn cat data.txt~csv | jn put output.json
jn cat data.unknown~json | jn put output.csv

# Config parameters
jn cat data.csv~csv?delimiter=; | jn put output.json
jn cat data.tsv~csv?delimiter=\t | jn put output.json
```

### Stdin/Stdout
```bash
# Format hints
cat data.csv | jn cat "-~csv" | jn put output.json
cat data.tsv | jn cat "-~csv?delimiter=\t" | jn put output.json

# Output formats
jn cat data.json | jn put "-~table.grid"
jn cat data.json | jn put "-~json?indent=4"
```

### Protocols
```bash
# HTTP
jn cat "http://example.com/data.csv" | jn put local.json

# S3
jn cat "s3://bucket/data.json" | jn put local.csv

# Gmail
jn cat "gmail://me/messages?from=boss&is=unread" | jn put emails.csv
```

### Profiles
```bash
# API query
jn cat "@genomoncology/alterations?gene=BRAF&limit=100" | jn put results.json

# Gmail profile
jn cat "@gmail/inbox?from=boss&newer_than=7d" | jn put emails.csv

# Database query
jn cat "@warehouse/orders?status=pending" | jn put orders.csv
```

### Multi-Source
```bash
# Mix local and remote
jn cat \
  sales/*.csv \
  "@stripe/charges?created_after=2024-01-01" \
  "https://api.example.com/orders.json" \
  | jn put combined.json

# Complex pipeline
jn cat \
  local.csv \
  "@api/remote?limit=100" \
  | jn filter '.active' \
  | jn filter '@builtin/deduplicate' \
  | jn put "-~table.grid"
```

### Table Output
```bash
# Grid table
jn cat data.json | jn put "-~table.grid"

# Markdown table with column width
jn cat data.json | jn put "-~table?tablefmt=markdown&maxcolwidths=30"

# With row numbers
jn cat data.json | jn put "-~table?tablefmt=grid&showindex=true"

# Right-aligned numbers
jn cat data.json | jn put "-~table?tablefmt=grid&numalign=right"
```

## Testing Strategy

### Unit Tests
- **Parser tests:** All address types, edge cases, malformed input
- **Resolver tests:** Plugin lookup, config building, URL resolution
- **Integration tests:** Each command with new addressing

### Integration Tests
```bash
# File addressing
jn cat tests/data/sample.csv | head -n 5
jn cat tests/data/sample.txt~csv?delimiter=; | head -n 5

# Stdin/stdout
cat tests/data/sample.csv | jn cat "-~csv" | head -n 5
jn cat tests/data/sample.json | jn put "-~table.grid"

# Multi-source
jn cat tests/data/sample1.csv tests/data/sample2.json | wc -l

# Format override
jn cat tests/data/sample.txt~csv | jn put output.json
cat output.json | jq length

# Config parameters
jn cat tests/data/sample.json | jn put "-~json?indent=4" | head -n 10
```

### Error Handling
- Invalid syntax: `data.csv~~json` (double tilde)
- Missing plugin: `data.txt~unknown` (no plugin for format)
- Invalid parameters: `data.csv?delimiter` (missing value)
- Profile not found: `@nonexistent/source`
- Ambiguous profile: `@inbox` (multiple matches)

## Migration Guide

### For Users

**Old syntax:**
```bash
jn cat data.txt --format csv --delimiter ';'
jn put output.json --indent 4
```

**New syntax:**
```bash
jn cat "data.txt~csv?delimiter=;"
jn put "output.json?indent=4"
```

**Backward compatibility:**
- Old `--format` flag deprecated but still works (prints warning)
- Old `--delimiter`, `--indent` flags deprecated (prints warning)
- Will be removed in v6

### For Plugin Developers

**Old interface:**
```python
def reads():
    """Read from stdin, yield NDJSON."""
    # Config hardcoded or from env vars
```

**New interface:**
```python
def reads(config=None):
    """Read from stdin, yield NDJSON.

    Args:
        config: Dict of configuration parameters
                (delimiter, indent, tablefmt, etc.)
    """
    config = config or {}
    delimiter = config.get("delimiter", ",")
    # Use config...
```

**CLI args:**
```bash
# Framework passes config via --config args
python plugin.py --mode read --config delimiter=; --config header=false
```

## Dependencies

**No new external dependencies** - uses stdlib only:
- `urllib.parse` for query string parsing
- `dataclasses` for Address types
- `re` for regex parsing (if needed)

## Deliverables

- [ ] `src/jn/addressing/__init__.py` - Module exports
- [ ] `src/jn/addressing/types.py` - Address dataclasses
- [ ] `src/jn/addressing/parser.py` - Address parsing
- [ ] `src/jn/addressing/resolver.py` - Address resolution
- [ ] `src/jn/addressing/config.py` - Plugin configuration
- [ ] `tests/test_address_parser.py` - Parser unit tests
- [ ] `tests/test_address_resolver.py` - Resolver unit tests
- [ ] `tests/integration/test_addressability.py` - Integration tests
- [ ] Updated `src/jn/cli/commands/cat.py` - Use new addressing
- [ ] Updated `src/jn/cli/commands/put.py` - Use new addressing
- [ ] Updated `src/jn/cli/commands/filter.py` - Use new addressing
- [ ] Updated `src/jn/cli/commands/run.py` - Use new addressing
- [ ] Updated `CLAUDE.md` - New syntax examples
- [ ] Updated `README.md` - New syntax examples
- [ ] `spec/workflows/addressability-examples.md` - Usage guide
- [ ] Migration guide in `CHANGELOG.md`

## Success Criteria

- [ ] All address types parse correctly (file, protocol, profile, plugin, stdio)
- [ ] Format override works (`~` operator)
- [ ] Parameters parse and pass to plugins (`?` operator)
- [ ] Shorthand formats expand correctly (`table.grid` → `table?tablefmt=grid`)
- [ ] Multi-source concatenation works in `jn cat`
- [ ] Plugin configuration works (delimiter, indent, tablefmt, etc.)
- [ ] Profile resolution works (HTTP profiles, Gmail, etc.)
- [ ] All commands updated (`cat`, `put`, `filter`, `run`)
- [ ] All tests pass (unit + integration)
- [ ] Documentation complete
- [ ] Backward compatibility maintained (with deprecation warnings)

## Risks & Mitigations

### Risk 1: Breaking Changes
**Mitigation:** Maintain backward compatibility with old flags, print deprecation warnings

### Risk 2: Shell Quoting Complexity
**Mitigation:** Document quoting rules, provide examples, support both `"address"` and `address` (when safe)

### Risk 3: Parser Edge Cases
**Mitigation:** Comprehensive test suite, clear error messages

### Risk 4: Plugin Config Interface Changes
**Mitigation:** Make config parameter optional, default to empty dict, phase migration

## Future Enhancements

### Phase 2 (Post-v5)
- [ ] Glob expansion: `*.csv~csv?delimiter=;`
- [ ] Environment variable substitution: `@api/$ENV_VAR`
- [ ] Recursive directories: `folder://path/to/dir/**/*.csv`
- [ ] Remote profile loading: `@remote::https://example.com/profiles/api.json`
- [ ] Profile inheritance: `@base/extended` (extends base profile)

### Phase 3 (Advanced)
- [ ] Streaming decompression: `data.csv.gz~csv` (auto-decompress)
- [ ] Multi-format sources: `data.xlsx~xlsx?sheet=Sheet2`
- [ ] Custom delimiters: `data.txt~csv?delimiter=|||`
- [ ] Nested parameters: `@api/source?filter[status]=active`

## Notes

- Addressability is the **foundation for v5** - must be solid
- Impacts every command and plugin - requires careful testing
- Self-contained addresses are key for AI agent composability
- Query string syntax is familiar to developers (URL parameters)
- Two operators (`~` and `?`) keep syntax simple and learnable
- Profile system enables reusable configurations without CLI clutter
- Multi-source concatenation is Unix `cat` for data sources

## References

- `spec/design/addressability.md` - Complete design specification
- `spec/arch/design.md` - v5 architecture overview
- Unix philosophy: Composable, pipeable, transparent
- URL syntax: RFC 3986 (URI Generic Syntax)
- Query strings: Standard `key=value&key2=value2` format
