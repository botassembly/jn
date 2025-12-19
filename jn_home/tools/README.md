# JN Tools

Utility applications built on JN's NDJSON streaming infrastructure.

## Architecture

```
jn_home/
├── plugins/     # Data format handlers (csv, json, xlsx)
└── tools/       # User-facing utility applications
    ├── todo     # Task management
    └── ...      # Future tools
```

**Distinction:**
- **Plugins** = I/O adapters for file formats and protocols
- **Core tools** = Pipeline primitives (jn-cat, jn-put, jn-filter)
- **Utility tools** = Applications that leverage JN for storage/queries

## Usage

```bash
# Direct invocation
jn tool todo list
jn tool todo add "Buy milk"

# Or create an alias
alias todo="jn tool todo"
todo list
```

## Tool Interface

Tools are standalone executables (bash, Python PEP 723, or compiled) that:
1. Store data as NDJSON in `~/.local/jn/<toolname>/` or `.jn/<toolname>/`
2. Use `jn-edit` for mutations and `zq` for queries
3. Follow Unix conventions (stdin/stdout, exit codes)

---

## Current Tools

### todo
Task management with BEADS-inspired features.

```bash
jn tool todo add "Fix bug" -p high -t "@work"
jn tool todo list --tag "@work"
jn tool todo blocks 1 2      # Task 1 blocks task 2
jn tool todo ready           # Show unblocked tasks
jn tool todo tree            # Dependency visualization
jn tool todo stats           # Dashboard
```

### db
Contention-safe JSONL document database shell.

Features:
- **Canonical storage**: One record per line in NDJSON format
- **System metadata**: Reserved `_meta` object with id, timestamps, version, soft-delete
- **Contention safety**: File locking prevents concurrent write conflicts
- **Crash safety**: Atomic rewrite via temp file + rename with backups
- **Soft delete**: Records marked deleted, not removed; explicit purge for hard delete

```bash
jn tool db init                          # Initialize database
jn tool db insert '{"name":"Alice"}'     # Insert record (auto ID + timestamps)
jn tool db list                          # List active records
jn tool db get 1                         # Get record by ID
jn tool db query 'select(.age > 25)'     # Query with zq expression
jn tool db set 1 age '31'                # Set field value
jn tool db update 1 '.tags += ["vip"]'   # Update with jn-edit expression
jn tool db delete 1                      # Soft delete
jn tool db undelete 1                    # Restore soft-deleted
jn tool db purge                         # Hard delete all soft-deleted
jn tool db check                         # Validate integrity
jn tool db stats                         # Database statistics
```

Options:
- `--file <path>` - Database file (default: `./.db.jsonl`)
- `--schema <name>` - Filter/assign `_meta.schema` for multi-collection support
- `--include-deleted` - Include soft-deleted records
- `--only-deleted` - Show only soft-deleted records

Record format:
```json
{"_meta":{"id":1,"created_at":"2025-01-01T00:00:00Z","updated_at":"2025-01-01T00:00:00Z","deleted":false,"deleted_at":null,"version":1},"name":"Alice","age":30}
```

---

## Future Tool Ideas

### Personal Productivity

| Tool | Description | Data Model |
|------|-------------|------------|
| **note** | Quick notes with tags and search | `{id, text, tags[], created, modified}` |
| **bookmark** | URL bookmarks with tags, descriptions | `{id, url, title, tags[], notes, created}` |
| **snippet** | Code snippet manager with syntax | `{id, name, lang, code, tags[], description}` |
| **habit** | Habit tracker with streaks | `{id, name, schedule, completions[], streak}` |
| **journal** | Daily journaling with prompts | `{date, entries[], mood, tags[]}` |
| **goal** | Goal tracking with milestones | `{id, goal, milestones[], progress, deadline}` |

### Time & Finance

| Tool | Description | Data Model |
|------|-------------|------------|
| **timetrack** | Time tracking with projects | `{id, project, task, start, end, tags[]}` |
| **expense** | Expense tracking with categories | `{id, amount, category, vendor, date, tags[]}` |
| **invoice** | Invoice generation from time entries | `{id, client, items[], total, status, due}` |
| **budget** | Budget categories with limits | `{category, limit, spent, period}` |

### Development

| Tool | Description | Data Model |
|------|-------------|------------|
| **changelog** | Generate changelogs from commits | `{version, date, changes[], breaking[]}` |
| **migration** | Data migration scripts | `{id, name, up, down, applied_at}` |
| **seed** | Test data generators | `{name, schema, count, rules[]}` |
| **mock** | API mock server from NDJSON | `{route, method, response, delay}` |
| **env** | Environment variable manager | `{name, value, env, encrypted}` |
| **secret** | Encrypted credential storage | `{name, value, encrypted, expires}` |

### Data & Analytics

| Tool | Description | Data Model |
|------|-------------|------------|
| **metric** | Metrics collection and graphing | `{name, value, timestamp, tags[]}` |
| **survey** | Survey/form builder and collector | `{id, questions[], responses[]}` |
| **poll** | Quick polls with voting | `{id, question, options[], votes[]}` |
| **leaderboard** | Score tracking and ranking | `{id, name, score, metadata}` |

### Content & Media

| Tool | Description | Data Model |
|------|-------------|------------|
| **feed** | RSS/Atom feed aggregator | `{id, feed_url, items[], last_fetch}` |
| **watch** | File/URL watcher with actions | `{id, target, action, last_check, hash}` |
| **queue** | Simple job/task queue | `{id, job, status, attempts, result}` |
| **clip** | Clipboard history manager | `{id, content, type, source, timestamp}` |

### Reference & Collections

| Tool | Description | Data Model |
|------|-------------|------------|
| **contact** | Address book | `{id, name, email, phone, tags[], notes}` |
| **inventory** | Asset/item tracking | `{id, name, location, quantity, tags[]}` |
| **glossary** | Term definitions | `{term, definition, context, see_also[]}` |
| **recipe** | Recipe collection | `{id, name, ingredients[], steps[], tags[]}` |

---

## Implementation Priority

**High value, low effort (good first tools):**
1. **note** - Simpler than todo, just text + tags
2. **bookmark** - URLs with tags, great for CLI workflows
3. **timetrack** - Start/stop/report, useful daily
4. **snippet** - Code snippets with `pbcopy` integration

**High value, medium effort:**
5. **changelog** - Git integration, markdown output
6. **habit** - Date math, streak calculations
7. **expense** - Aggregations, monthly reports

**Interesting experiments:**
8. **feed** - HTTP fetching, XML parsing
9. **mock** - Mini HTTP server
10. **watch** - Filesystem/HTTP polling

---

## Tool Template

```bash
#!/usr/bin/env bash
# tool-name - One line description
# Requires: jn-edit, zq

set -euo pipefail

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/jn/tool-name"
DATA_FILE="$DATA_DIR/data.jsonl"

# ... implementation using jn-edit and zq
```

Or as Python (PEP 723):

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""tool-name - One line description"""

import subprocess
import json

def jn_edit(data: str, *edits) -> str:
    return subprocess.check_output(['jn-edit'] + list(edits), input=data, text=True)

def zq(data: str, query: str) -> str:
    return subprocess.check_output(['zq', '-c', query], input=data, text=True)
```
