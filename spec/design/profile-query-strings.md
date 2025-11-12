# Profile Query Strings

## Problem

How should users pass parameters to profile references like `@gmail/inbox` or `@api/source`?

## Solution: Query String Syntax

**Use URL query string syntax directly in the reference:**

```bash
jn cat "@gmail/inbox?from=boss&is=unread"
jn cat "@api/source?gene=BRAF&limit=100"
```

## Rationale

### Why Query Strings?

**1. Self-contained**
The entire "address" is in one string - no separate flags needed:
```bash
# Query string approach (chosen)
jn cat "@gmail/inbox?from=boss&is=unread"

# vs -p flag approach (rejected)
jn cat @gmail/inbox -p from=boss -p is=unread
```

**2. Familiar syntax**
Users already understand URLs with query strings:
```bash
jn cat "https://api.com/data?key=val&foo=bar"  # Same pattern
jn cat "@gmail/inbox?from=boss&is=unread"      # Consistent
```

**3. Enables multi-file cat**
Without `-p` being required, `cat` can accept multiple sources:
```bash
jn cat users.csv orders.json products.yaml | jn put combined.json
jn cat local.csv "@api/remote?limit=100" | jn filter '.active'
```

**4. Composable**
Can mix and match different sources naturally:
```bash
jn cat "@gmail/inbox?from=boss" "@api/tickets?status=open" local.csv
```

### Tradeoffs

**Quoting required:**
Shell metacharacters `?` and `&` require quoting:
```bash
jn cat "@gmail/inbox?from=boss&is=unread"  # Must quote
```

But we already quote URLs and globs:
```bash
jn cat "https://api.com/data?key=val"  # Already required
jn cat "data/*.csv"                    # Already required
```

Shell completion can add quotes automatically.

## Implementation

### 1. Parse Query String in `jn cat`

**File:** `src/jn/cli/commands/cat.py`

```python
# Parse query string from reference if present
params = {}
source_ref = input_file

if "?" in input_file and input_file.startswith("@"):
    # Split reference and query string
    source_ref, query_string = input_file.split("?", 1)
    # Parse query string
    parsed_params = parse_qs(query_string)
    for key, values in parsed_params.items():
        params[key] = values[0] if len(values) == 1 else values

# Parse -p parameters and merge (override query string)
for p in param:
    key, value = p.split("=", 1)
    if key in params:
        # Handle multiple values
        if not isinstance(params[key], list):
            params[key] = [params[key]]
        params[key].append(value)
    else:
        params[key] = value
```

**Key points:**
- Query string parsed first
- `-p` parameters override query string values
- Both can be used together
- Single values flattened, multiple values as lists

### 2. Profile Resolver Merges with Defaults

**Example:** `src/jn/profiles/gmail.py`

```python
def resolve_gmail_reference(reference: str, params: Optional[Dict] = None) -> str:
    """Resolve @gmail/inbox to gmail:// URL.

    Args:
        reference: "@gmail/inbox" (no query string)
        params: {"from": "boss", "is": "unread"} (from query string + -p)

    Returns:
        "gmail://me/messages?in=inbox&from=boss&is=unread"
    """
    # Load profile
    profile = load_gmail_profile("inbox")

    # Get defaults from profile
    defaults = profile.get("defaults", {})  # {"in": "inbox"}

    # Merge defaults with provided params (params override)
    all_params = {**defaults, **(params or {})}

    # Build URL with query string
    query_string = urlencode(all_params, doseq=True)
    return f"gmail://me/messages?{query_string}"
```

**Merge order:**
1. Profile defaults (lowest priority)
2. Query string parameters
3. `-p` parameters (highest priority)

### 3. Plugin Parses URL

**Example:** Gmail plugin

```python
from urllib.parse import urlparse, parse_qs

# Parse gmail:// URL
parsed = urlparse(args.url)  # "gmail://me/messages?from=boss&is=unread"

user_id = parsed.netloc  # "me"

# Parse query string
params = {}
if parsed.query:
    parsed_params = parse_qs(parsed.query)  # {"from": ["boss"], "is": ["unread"]}
    for key, values in parsed_params.items():
        params[key] = values[0] if len(values) == 1 else values

# Use params
query = build_gmail_query(params)  # "from:boss is:unread"
```

## Examples

### Gmail

```bash
# Basic inbox
jn cat "@gmail/inbox"
# → gmail://me/messages?in=inbox

# Inbox from specific sender
jn cat "@gmail/inbox?from=boss"
# → gmail://me/messages?in=inbox&from=boss

# Complex query
jn cat "@gmail/attachments?filename=pdf&newer_than=7d&larger=5M"
# → gmail://me/messages?has=attachment&filename=pdf&newer_than=7d&larger=5M

# Mix query string and -p
jn cat "@gmail/inbox?from=boss" -p is=unread
# → gmail://me/messages?in=inbox&from=boss&is=unread
```

### HTTP APIs

```bash
# GenomOncology API
jn cat "@genomoncology/alterations?gene=BRAF"
# → https://pwb-demo.genomoncology.io/api/alterations?gene=BRAF

# With limit
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
# → https://pwb-demo.genomoncology.io/api/alterations?gene=BRAF&limit=10

# Multiple values
jn cat "@api/data?gene=BRAF&gene=EGFR"
# → https://api.com/data?gene=BRAF&gene=EGFR
```

## Relationship to `-p`

**Both syntaxes are supported:**

```bash
# Query string (recommended - cleaner)
jn cat "@gmail/inbox?from=boss&is=unread"

# -p flags (still works)
jn cat @gmail/inbox -p from=boss -p is=unread

# Mixed (query string + -p)
jn cat "@gmail/inbox?from=boss" -p is=unread -p newer_than=7d
```

**When to use each:**

| Syntax | Use When |
|--------|----------|
| Query string | One-off queries, simple parameters, readability |
| `-p` flags | Scripting (easier to construct programmatically), overriding defaults |
| Mixed | Override some query string params dynamically |

## Future: Multi-file Cat

Once query strings are well-established, `cat` can accept multiple arguments:

```bash
# Concatenate multiple sources
jn cat file1.csv file2.json "@api/data?limit=100"

# Multiple APIs
jn cat "@api1/users?status=active" "@api2/orders?state=pending"

# Mix local and remote
jn cat local/*.csv "@gmail/attachments?filename=csv"
```

**Implementation:**
```python
@click.argument("input_files", nargs=-1, required=True)  # Multiple args
def cat(ctx, input_files, param):
    for input_file in input_files:
        # Read each source and concatenate output
        read_source(input_file, ...)
```

## Migration

**No breaking changes:**
- Query string syntax is new, doesn't break existing usage
- `-p` flags continue to work
- Profiles work unchanged

**Documentation updates:**
- Update all examples to show query string syntax as primary
- Note `-p` as alternative
- Show mixed usage for advanced cases

## Summary

**Chosen approach:**
```bash
jn cat "@gmail/inbox?from=boss&is=unread"
```

**Key benefits:**
- ✅ Self-contained (no separate flags)
- ✅ Familiar (URL syntax everyone knows)
- ✅ Enables multi-file cat
- ✅ Still supports `-p` for scripting

**Implementation:**
1. Parse query string in `jn cat`
2. Profile resolver merges with defaults
3. Plugin receives fully-qualified URL

**Future:**
- Multi-file concatenation
- More protocol plugins using same pattern
- Tab completion with quote insertion
