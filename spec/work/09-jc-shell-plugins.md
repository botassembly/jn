# JC Shell Plugins (Vendored)

## What
Vendor parsers from JC project to parse Unix command output (ls, ps, df, netstat, etc.) into NDJSON.

## Why
Unix commands output text. JC project has battle-tested parsers. Enable filtering and processing of shell command output in pipelines.

## Key Features
- 10-15 common commands: ls, ps, df, du, find, stat, netstat, ifconfig, who, last
- Execute command, capture output, parse to NDJSON
- Preserve JC's robust parsing logic
- Proper attribution and MIT license compliance

## Dependencies
- Vendor JC parser code (MIT licensed, allows modification)
- No external dependencies (copy parser logic)

## Examples
```bash
# List directory, filter large files
jn ls /var/log | jn filter '.size > 1000000' | jn jtbl

# Process listing
jn ps | jn filter '.command =~ "python"' | jn jtbl

# Disk usage
jn df | jn filter '.use_percent > 80' | jn jtbl

# Network connections
jn netstat | jn filter '.state == "ESTABLISHED"' | jn put connections.csv
```

## Vendoring Guidelines
- Copy JC parsers to `jn_home/plugins/shell/`
- Wrap in PEP 723 + reads() function
- Preserve attribution: "Vendored from github.com/kellyjonbrazil/jc, MIT License, Author: Kelly Brazil"
- Track JC version in comments
- Contribute bug fixes back to JC

## Related
- **JTBL** (ticket #08) - Use as dependency, don't vendor
- **JC** - Vendor specific parsers only
