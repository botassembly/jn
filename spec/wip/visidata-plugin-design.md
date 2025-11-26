# VisiData Plugin for JN: Bidirectional Integration

**Date:** 2025-11-25
**Status:** Design Proposal
**Author:** Claude

---

## Overview

A VisiData plugin (`vd-jn`) that enables bidirectional integration between VisiData and JN:

1. **Open jn sources from VisiData** - Use jn's universal addressing to load data
2. **Apply jq filters within VisiData** - Run jq expressions without leaving VisiData
3. **Pipe selections through jn** - Send selected rows to jn commands
4. **Save via jn** - Write data using jn's output plugins

---

## Why Bidirectional Integration?

**Current flow (jn → VisiData):**
```bash
jn cat http://myapi/users | jn vd
```

**Proposed bidirectional flow:**
```bash
# From shell: Open jn source directly in VisiData
vd jn://http/myapi/users

# From VisiData: Pipe selection through jn
# (Press custom key, data flows: VisiData → jn filter → VisiData)
```

**Benefits:**
- Stay in VisiData for exploration, use jn for complex transformations
- Access jn's universal addressing (HTTP, Gmail, MCP, etc.) from VisiData
- Use jq expressions (familiar to jn users) within VisiData
- Round-trip editing: Load from API → modify → push back

---

## Feature Design

### 1. JN Source Loader

**Capability:** Open any jn-addressable source directly in VisiData.

**Usage:**
```bash
# From command line
vd jn://http/myapi/users
vd jn://gmail/inbox
vd jn://mcp/server/resource

# Or within VisiData
o jn://http/myapi/users
```

**Implementation:**
```python
@VisiData.api
def open_jn(vd, p):
    """Open a jn:// URL as a sheet."""
    return JNSheet(p.given, source=p)

class JNSheet(TableSheet):
    rowtype = 'records'

    def iterload(self):
        import subprocess
        import json

        # Extract jn address from jn://... URL
        address = self.source.given.replace('jn://', '')

        # Run jn cat to get NDJSON
        proc = subprocess.Popen(
            ['jn', 'cat', address],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        for line in proc.stdout:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    yield {'_error': str(e), '_line': line}

        proc.wait()
```

**Registration:**
```python
# In ~/.visidatarc or plugin file
vd.addGlobals({'open_jn': open_jn})
```

### 2. JQ Filter Command

**Capability:** Apply jq expressions to current sheet, creating a new filtered sheet.

**Usage (within VisiData):**
```
Press: Ctrl+J (or custom binding)
Prompt: jq filter: .age > 30
Result: New sheet with filtered rows
```

**Implementation:**
```python
@TableSheet.api
def jq_filter(sheet, expr):
    """Filter rows using jq expression via jn filter."""
    import subprocess
    import json

    # Convert current sheet to NDJSON
    ndjson_lines = []
    for row in sheet.rows:
        ndjson_lines.append(json.dumps(sheet.rowdict(row)))

    # Pipe through jn filter
    proc = subprocess.Popen(
        ['jn', 'filter', expr],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = proc.communicate('\n'.join(ndjson_lines))

    if proc.returncode != 0:
        vd.fail(f"jq error: {stderr}")
        return

    # Create new sheet with results
    filtered_rows = []
    for line in stdout.strip().split('\n'):
        if line:
            filtered_rows.append(json.loads(line))

    return vd.push(TableSheet(f"{sheet.name}_filtered", rows=filtered_rows))

# Bind to key
TableSheet.addCommand('', 'jq-filter', 'jq_filter(input("jq filter: "))')
TableSheet.bindkey('^J', 'jq-filter')  # Ctrl+J
```

### 3. Pipe to JN Command

**Capability:** Pipe selected rows through any jn command pipeline.

**Usage (within VisiData):**
```
1. Select rows with s/gs
2. Press: |  (pipe key)
3. Prompt: jn command: jn filter '.status == "active"' | jn put output.json
4. Result: Selected rows piped through command
```

**Implementation:**
```python
@TableSheet.api
def pipe_to_jn(sheet, cmd):
    """Pipe selected rows through a jn command."""
    import subprocess
    import json

    # Get selected rows (or all if none selected)
    rows = sheet.selectedRows or sheet.rows

    # Convert to NDJSON
    ndjson = '\n'.join(json.dumps(sheet.rowdict(r)) for r in rows)

    # Run command
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = proc.communicate(ndjson)

    if proc.returncode != 0:
        vd.warning(f"Command failed: {stderr}")

    # If output is NDJSON, open as new sheet
    if stdout.strip():
        try:
            rows = [json.loads(line) for line in stdout.strip().split('\n') if line]
            return vd.push(TableSheet(f"{sheet.name}_piped", rows=rows))
        except json.JSONDecodeError:
            # Not JSON, show as text
            vd.status(stdout[:100])

    return None

TableSheet.addCommand('', 'pipe-to-jn', 'pipe_to_jn(input("jn command: "))')
TableSheet.bindkey('|', 'pipe-to-jn')
```

### 4. Save via JN

**Capability:** Save current sheet using jn's output plugins (supports more formats).

**Usage (within VisiData):**
```
Press: Ctrl+Shift+S (or custom binding)
Prompt: jn output: output.xlsx
Result: Data saved via jn put
```

**Implementation:**
```python
@TableSheet.api
def save_via_jn(sheet, path):
    """Save sheet using jn put for extended format support."""
    import subprocess
    import json

    # Convert to NDJSON
    ndjson = '\n'.join(json.dumps(sheet.rowdict(r)) for r in sheet.rows)

    # Pipe to jn put
    proc = subprocess.Popen(
        ['jn', 'put', path],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    _, stderr = proc.communicate(ndjson)

    if proc.returncode == 0:
        vd.status(f"Saved to {path} via jn")
    else:
        vd.fail(f"Save failed: {stderr}")

TableSheet.addCommand('', 'save-via-jn', 'save_via_jn(input("jn output: "))')
```

---

## Complete Plugin File

```python
#!/usr/bin/env python3
"""VisiData plugin for JN integration.

Installation:
1. Save as ~/.visidata/plugins/vd_jn.py
2. Add to ~/.visidatarc: import plugins.vd_jn

Or install via pip if published:
    pip install vd-jn
"""

import json
import subprocess

from visidata import vd, VisiData, TableSheet, Sheet

__version__ = '0.1.0'


# =============================================================================
# JN Source Loader
# =============================================================================

@VisiData.api
def open_jn(vd, p):
    """Open a jn:// URL as a VisiData sheet.

    Usage:
        vd jn://http/myapi/users
        vd jn://gmail/inbox
    """
    return JNSheet(p.base_stem or 'jn', source=p)


class JNSheet(TableSheet):
    """Sheet that loads data from a jn source."""

    rowtype = 'records'

    def iterload(self):
        # Extract address from jn://... path
        address = str(self.source.given)
        if address.startswith('jn://'):
            address = address[5:]  # Remove jn:// prefix

        # Run jn cat
        proc = subprocess.Popen(
            ['jn', 'cat', address],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        for line in proc.stdout:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    yield {'_error': str(e), '_raw': line[:200]}

        proc.wait()
        if proc.returncode != 0:
            vd.warning(f"jn cat warning: {proc.stderr.read()}")


# =============================================================================
# JQ Filter Command
# =============================================================================

@TableSheet.api
def jq_filter(sheet, expr):
    """Filter current sheet using a jq expression via jn filter.

    Creates a new sheet with matching rows.
    """
    if not expr:
        return

    # Convert rows to NDJSON
    ndjson_lines = []
    for row in sheet.rows:
        row_dict = {col.name: col.getValue(row) for col in sheet.visibleCols}
        ndjson_lines.append(json.dumps(row_dict))

    # Pipe through jn filter
    proc = subprocess.Popen(
        ['jn', 'filter', expr],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = proc.communicate('\n'.join(ndjson_lines))

    if proc.returncode != 0:
        vd.fail(f"jq filter error: {stderr}")
        return

    # Parse results
    filtered_rows = []
    for line in stdout.strip().split('\n'):
        if line:
            try:
                filtered_rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # Create new sheet
    result_sheet = TableSheet(f"{sheet.name}[{expr[:20]}]", rows=filtered_rows)
    return vd.push(result_sheet)


# =============================================================================
# Pipe to JN Command
# =============================================================================

@TableSheet.api
def pipe_to_jn(sheet, cmd):
    """Pipe selected (or all) rows through a jn command.

    If the command outputs NDJSON, opens result as new sheet.
    """
    if not cmd:
        return

    # Get rows to pipe
    rows = sheet.selectedRows if sheet.selectedRows else sheet.rows

    # Convert to NDJSON
    ndjson_lines = []
    for row in rows:
        row_dict = {col.name: col.getValue(row) for col in sheet.visibleCols}
        ndjson_lines.append(json.dumps(row_dict))

    # Run command
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = proc.communicate('\n'.join(ndjson_lines))

    if proc.returncode != 0:
        vd.warning(f"Command failed: {stderr}")

    if stdout.strip():
        # Try to parse as NDJSON
        try:
            result_rows = []
            for line in stdout.strip().split('\n'):
                if line:
                    result_rows.append(json.loads(line))

            if result_rows:
                result_sheet = TableSheet(f"{sheet.name}_piped", rows=result_rows)
                return vd.push(result_sheet)
        except json.JSONDecodeError:
            # Not JSON, just show status
            vd.status(f"Output: {stdout[:100]}")

    return None


# =============================================================================
# Save via JN
# =============================================================================

@TableSheet.api
def save_via_jn(sheet, path):
    """Save current sheet using jn put (supports more formats)."""
    if not path:
        return

    # Convert to NDJSON
    ndjson_lines = []
    for row in sheet.rows:
        row_dict = {col.name: col.getValue(row) for col in sheet.visibleCols}
        ndjson_lines.append(json.dumps(row_dict))

    # Pipe to jn put
    proc = subprocess.Popen(
        ['jn', 'put', path],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    _, stderr = proc.communicate('\n'.join(ndjson_lines))

    if proc.returncode == 0:
        vd.status(f"Saved {len(sheet.rows)} rows to {path}")
    else:
        vd.fail(f"Save failed: {stderr}")


# =============================================================================
# Key Bindings
# =============================================================================

# jq filter: Ctrl+J
TableSheet.addCommand('^J', 'jq-filter', 'jq_filter(input("jq filter: "))',
                      'filter rows using jq expression via jn')

# Pipe to jn: | (pipe)
TableSheet.addCommand('|', 'pipe-to-jn', 'pipe_to_jn(input("jn command: "))',
                      'pipe selected rows through jn command')

# Save via jn: g Ctrl+S (global save via jn)
TableSheet.addCommand('g^S', 'save-via-jn', 'save_via_jn(input("jn output path: "))',
                      'save sheet using jn put')

# Reload from jn source (for JNSheet)
JNSheet.addCommand('r', 'reload-jn', 'reload()', 'reload data from jn source')


# =============================================================================
# Filetype Registration
# =============================================================================

# Register jn:// as a filetype
vd.addGlobals({'open_jn': open_jn})
```

---

## Installation

### Option 1: Manual Install

```bash
# Create plugin directory
mkdir -p ~/.visidata/plugins

# Save plugin file
cat > ~/.visidata/plugins/vd_jn.py << 'EOF'
# (paste plugin code here)
EOF

# Add to visidatarc
echo "import plugins.vd_jn" >> ~/.visidatarc
```

### Option 2: Package Install (Future)

```bash
pip install vd-jn
```

Then in `~/.visidatarc`:
```python
import vd_jn
```

---

## Usage Examples

### Open JN Sources

```bash
# HTTP API
vd jn://http/myapi/users

# Gmail
vd jn://gmail/inbox

# With profile-based auth
vd jn://http/github/repos
```

### Filter with jq

```
1. Open data in VisiData
2. Press Ctrl+J
3. Enter: .age > 30 and .status == "active"
4. New sheet opens with filtered results
```

### Pipe Selection Through JN

```
1. Select rows with s, gs, or |
2. Press | (pipe)
3. Enter: jn filter '.type == "premium"' | jn put premium_users.csv
4. If output is NDJSON, opens as new sheet
```

### Save to Extended Formats

```
1. Explore/modify data in VisiData
2. Press g Ctrl+S
3. Enter: output.xlsx
4. Data saved via jn (supports xlsx, yaml, toml, etc.)
```

---

## Licensing Considerations

**VisiData:** GPL v3
**JN:** MIT
**This Plugin:** GPL v3 (required because it runs inside VisiData's process)

The plugin can be distributed separately from JN. Users who want bidirectional integration install it by choice.

---

## Future Enhancements

1. **Profile Browser** - Browse available jn profiles as a VisiData sheet
2. **jn inspect Integration** - Run jn inspect on current data
3. **Live Reload** - Auto-reload jn sources on changes
4. **jn analyze** - Show jn analyze output in VisiData
5. **MCP Tool Browser** - Browse MCP tools as interactive sheets

---

## References

- [VisiData Plugin API](https://www.visidata.org/docs/api/)
- [VisiData Custom Loaders](https://www.visidata.org/docs/api/loaders)
- [ajkerrigan/visidata-plugins](https://github.com/ajkerrigan/visidata-plugins) - Example plugins
- [JN Universal Addressing](spec/done/addressability.md)
