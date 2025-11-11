# JC Project Vendoring for Shell Plugins

## Overview
Vendor (copy and adapt) parsers from the JC project to create shell command plugins. JC provides battle-tested parsers that convert output from common Unix commands (ls, ps, df, etc.) into JSON.

## Goals
- Vendor JC parsers into `jn_home/plugins/shell/` directory
- Convert JC parsers to JN plugin format (PEP 723 + reads() function)
- Support common shell commands (ls, ps, df, du, etc.)
- Enable usage: `jn ls /path | jn filter '...'` instead of `ls /path | jq '...'`
- Preserve JC's robust parsing logic
- Give credit to JC project in comments/docs

## Resources
**JC Project:** https://github.com/kellyjonbrazil/jc
- Created by Kelly Brazil
- 80+ command parsers (ls, ps, df, netstat, etc.)
- Python library with CLI interface
- Liberal license (MIT) - allows vendoring

**Documentation:** https://kellyjonbrazil.github.io/jc/
**Parsers directory:** https://github.com/kellyjonbrazil/jc/tree/master/jc/parsers

## Priority Commands to Vendor
**File/Directory:**
- `ls` - List directory contents
- `du` - Disk usage
- `find` - Find files
- `stat` - File statistics

**Process/System:**
- `ps` - Process status
- `top` - System processes
- `df` - Disk free space
- `free` - Memory usage

**Network:**
- `ifconfig` / `ip` - Network interfaces
- `netstat` / `ss` - Network connections
- `ping` - Network connectivity
- `route` - Routing table

**User/Permission:**
- `who` - Logged in users
- `last` - Login history
- `id` - User/group IDs

## Technical Approach

### Vendoring Process
1. Copy parser files from JC repo to `jn_home/plugins/shell/`
2. Wrap parser logic in JN plugin structure
3. Add PEP 723 header with JC attribution
4. Implement `reads()` function that:
   - Executes shell command
   - Captures stdout
   - Passes to JC parser
   - Yields records as NDJSON
5. Add pattern matching (if applicable)
6. Update imports to use vendored code

### Plugin Structure Template

```python
#!/usr/bin/env -S uv run --script
"""Parse ls command output using JC parser.

Vendored from: https://github.com/kellyjonbrazil/jc
Original author: Kelly Brazil
License: MIT
JN modifications: Wrapped in plugin interface
"""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = []  # Shell commands invoked by name, not pattern
# ///

import subprocess
import sys
from typing import Iterator, Optional

# Vendored JC parser code
def parse_ls(data: str) -> list:
    """JC ls parser - vendored and potentially modified."""
    # ... original JC parsing logic ...
    pass

def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Execute ls command and parse output."""
    config = config or {}
    path = config.get("path", ".")
    args = config.get("args", [])

    cmd = ["ls", "-la"] + args + [path]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    parsed = parse_ls(result.stdout)
    yield from parsed

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("args", nargs="*")
    args = parser.parse_args()

    config = {"path": args.path, "args": args.args}
    for record in reads(config):
        print(json.dumps(record), flush=True)
```

## Usage Examples

```bash
# List directory as JSON
jn ls /home/user | jn jtbl

# Filter large files
jn ls /var/log | jn filter '.size > 1000000' | jn put large-logs.csv

# Process info
jn ps | jn filter '.command =~ "python"' | jn jtbl

# Disk usage
jn df | jn filter '.use_percent > 80' | jn jtbl

# Find + filter
jn find /home/user -name "*.py" | jn filter '.size > 10000' | jn put large-scripts.json

# Network connections
jn netstat | jn filter '.state == "ESTABLISHED"' | jn jtbl
```

## Vendoring Guidelines

### Preserve Attribution
```python
"""
Vendored from: https://github.com/kellyjonbrazil/jc
Original author: Kelly Brazil
License: MIT
JN modifications: [list changes]
"""
```

### Allowed Modifications
- Add PEP 723 header
- Wrap in plugin interface (reads() function)
- Remove CLI entry point (we provide our own)
- Update imports for vendored location
- Fix bugs (contribute back to JC if possible)
- Optimize for streaming (if possible)

### Prohibited Modifications
- Change license
- Remove attribution
- Claim original authorship
- Modify core parsing logic unnecessarily

### Maintenance Strategy
- Periodically sync with JC updates
- Track JC version in comments
- Document divergence from upstream
- Contribute improvements back to JC when possible

## Out of Scope
- Windows commands (JC supports some, but lower priority)
- All 80+ JC parsers - start with top 10-15
- Live command execution (we run once and parse)
- Interactive commands (top, htop) - snapshot only
- Commands requiring sudo - run as-is
- Custom command wrappers - just vendor JC parsers

## Success Criteria
- 10-15 common commands vendored and working
- Proper attribution in all files
- Commands work in pipelines
- Parsing matches JC output format
- Clear documentation on vendored vs original
- Can update from upstream JC periodically

## Related Projects
All by Kelly Brazil (kellybrazil.github.io):
- **JC** - CLI tool output → JSON (vendoring source)
- **JTBL** - JSON → table (using as dependency, ticket #08)
- **Jello** - Python + Jinja2 for JSON (not needed, we have jq)

## Legal Verification
Before vendoring:
1. Verify JC license allows vendoring (MIT ✓)
2. Include LICENSE file from JC in shell plugin directory
3. Maintain attribution in every vendored file
4. Add "vendored from JC" to JN documentation
