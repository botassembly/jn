# Profile CLI

**Status:** ✅ Implemented (Phase 1 & 2)
**Commands:** `jn profile list`, `jn profile info`, `jn profile tree`
**Date:** 2025-11-22

---

## Problem

Agents and users need to:
1. **Discover** what profiles exist
2. **Navigate** profile hierarchies (APIs, sources, filters)
3. **Inspect** profile details (parameters, endpoints, configuration)
4. **Create** new profiles efficiently
5. **Validate** profiles work correctly

Currently, this requires reading JSON files directly or guessing file locations.

---

## Current State

**No profile CLI exists.** Users must:
- Manually browse `jn_home/profiles/` directory
- Read JSON/JQ files to understand structure
- Guess parameter names from API documentation
- Create files from scratch with no templates

**Profile Structure:**
```
profiles/
├── http/                    # HTTP API profiles
│   ├── genomoncology/       # API namespace
│   │   ├── _meta.json       # Connection config (base_url, headers)
│   │   ├── alterations.json # Source endpoint
│   │   └── genes.json       # Source endpoint
│   └── github.json          # Simple source (no _meta)
└── jq/                      # JQ filter profiles
    ├── builtin/             # Built-in filters
    │   └── pivot.jq
    └── genomoncology/       # API-specific filters
        └── extract-hgvs.jq
```

---

## Design Philosophy

### For Agents (Primary Users)

**What agents need:**
1. **Fast discovery** - "What profiles exist for genomoncology?"
2. **Parameter inspection** - "What params does `@genomoncology/alterations` accept?"
3. **Direct file access** - Agents can write JSON/JQ files directly (no interactive prompts needed)
4. **Validation** - "Does this profile work?"

**What agents DON'T need:**
- Interactive wizards (too slow, fragile)
- Complex editors (agents write files better than CLIs can)

### For Humans (Secondary Users)

**What humans need:**
1. **Visual hierarchy** - Tree view of profiles
2. **Examples** - "Show me how to use this profile"
3. **Templates** - Scaffolding for new profiles

---

## Proposed CLI Structure

### Command Hierarchy

```bash
jn profile                     # List all profiles (default)
jn profile list                # List all profiles (explicit)
jn profile tree                # Tree view of profile hierarchy
jn profile info <reference>    # Show profile details
jn profile test <reference>    # Test profile works
jn profile new <type>          # Create new profile (scaffold)
```

**Follows existing `jn plugin` pattern:**
- `jn plugin list` → `jn profile list`
- `jn plugin info csv_` → `jn profile info @genomoncology/alterations`

---

## Command Details

### 1. `jn profile list` (Default)

**Purpose:** Quick discovery of all available profiles

**Output (text):**
```bash
$ jn profile list

HTTP API Profiles:
  @genomoncology/alterations      - Genomic alterations endpoint
  @genomoncology/annotations      - Variant annotations endpoint
  @genomoncology/clinical_trials  - Clinical trials endpoint
  @genomoncology/diseases         - Disease information endpoint
  @genomoncology/genes            - Gene information endpoint
  @genomoncology/therapies        - Therapy information endpoint
  @github                         - GitHub API (simple)
  @jsonplaceholder                - JSONPlaceholder API (testing)

JQ Filter Profiles:
  @builtin/flatten_nested    - Flatten nested arrays/objects
  @builtin/group_count       - Group and count by field
  @builtin/group_sum         - Group and sum by field
  @builtin/pivot             - Pivot table transformation
  @builtin/stats             - Calculate statistics
  @genomoncology/by_transcript    - Pivot transcript arrays
  @genomoncology/extract-alterations - Normalize alteration records
  @genomoncology/extract-hgvs     - Extract HGVS nomenclature

Use 'jn profile info <reference>' for detailed information
```

**Output (JSON for agents):**
```bash
$ jn profile list --format json
{
  "http": {
    "@genomoncology/alterations": {
      "path": "/home/user/jn/jn_home/profiles/http/genomoncology/alterations.json",
      "type": "source",
      "params": ["gene", "mutation_type", "biomarker", "page", "limit"]
    },
    ...
  },
  "jq": {
    "@builtin/pivot": {
      "path": "/home/user/jn/jn_home/profiles/jq/builtin/pivot.jq",
      "params": ["row", "col", "value"]
    },
    ...
  }
}
```

**Filtering:**
```bash
$ jn profile list --type http           # Only HTTP profiles
$ jn profile list --type jq             # Only JQ profiles
$ jn profile list --namespace genomoncology  # Only genomoncology profiles
```

---

### 2. `jn profile tree`

**Purpose:** Visual hierarchy for exploration

**Output:**
```bash
$ jn profile tree

profiles/
├── http/
│   ├── genomoncology/          [@genomoncology]
│   │   ├── _meta.json          (connection config)
│   │   ├── alterations         [@genomoncology/alterations]
│   │   ├── annotations         [@genomoncology/annotations]
│   │   ├── clinical_trials     [@genomoncology/clinical_trials]
│   │   ├── diseases            [@genomoncology/diseases]
│   │   ├── genes               [@genomoncology/genes]
│   │   └── therapies           [@genomoncology/therapies]
│   ├── github                  [@github]
│   └── jsonplaceholder         [@jsonplaceholder]
└── jq/
    ├── builtin/                [@builtin]
    │   ├── flatten_nested      [@builtin/flatten_nested]
    │   ├── group_count         [@builtin/group_count]
    │   ├── group_sum           [@builtin/group_sum]
    │   ├── pivot               [@builtin/pivot]
    │   └── stats               [@builtin/stats]
    └── genomoncology/          [@genomoncology]
        ├── by_transcript       [@genomoncology/by_transcript]
        ├── extract-alterations [@genomoncology/extract-alterations]
        └── extract-hgvs        [@genomoncology/extract-hgvs]
```

**With source filter:**
```bash
$ jn profile tree http/genomoncology    # Show only genomoncology HTTP profiles
```

---

### 3. `jn profile info <reference>`

**Purpose:** Detailed inspection of a specific profile

**Example: HTTP Source**
```bash
$ jn profile info @genomoncology/alterations

Profile: @genomoncology/alterations
Type: HTTP source
Location: jn_home/profiles/http/genomoncology/alterations.json

Configuration:
  API: genomoncology
  Base URL: https://${GENOMONCOLOGY_URL}/api
  Path: /alterations
  Method: GET

Headers:
  Authorization: Token ${GENOMONCOLOGY_API_KEY}
  Accept: application/json

Parameters (optional):
  gene          - Gene symbol to filter by
  mutation_type - Type of mutation to filter by
  biomarker     - Biomarker name to filter by
  page          - Page number for pagination
  limit         - Number of results per page

Environment Variables:
  GENOMONCOLOGY_URL      ✓ set (pwb-demo.genomoncology.io)
  GENOMONCOLOGY_API_KEY  ✓ set (hidden)

Example Usage:
  # Fetch all alterations
  jn cat @genomoncology/alterations

  # Filter by gene
  jn cat @genomoncology/alterations -p gene=BRAF

  # Filter with multiple params
  jn cat @genomoncology/alterations -p gene=BRAF -p limit=10

  # Pipeline example
  jn cat @genomoncology/alterations -p gene=BRAF | \
    jn filter '@genomoncology/extract-alterations' | \
    jn put --plugin table -
```

**Example: JQ Filter**
```bash
$ jn profile info @builtin/pivot

Profile: @builtin/pivot
Type: JQ filter
Location: jn_home/profiles/jq/builtin/pivot.jq

Description:
  Pivot table transformation - converts rows to columns based on grouping fields.

Parameters (required):
  row   - Field to use for row grouping
  col   - Field to use for column names
  value - Field to use for cell values

Filter Preview (first 20 lines):
  # Pivot table transformation
  # Converts rows to columns based on grouping fields
  #
  # Required parameters:
  #   $row - field to use for row grouping
  #   $col - field to use for column names
  #   $value - field to use for cell values
  ...

Example Usage:
  # Pivot sales data by product and month
  jn cat sales.csv | \
    jn filter '@builtin/pivot' -p row=product -p col=month -p value=revenue

  # Pivot with multiple groups
  jn cat data.json | \
    jn filter '@builtin/pivot' -p row=category -p col=region -p value=count
```

---

### 4. `jn profile test <reference>`

**Purpose:** Validate profile works correctly

**Example:**
```bash
$ jn profile test @genomoncology/alterations

Testing profile: @genomoncology/alterations

✓ Profile file exists
✓ JSON syntax valid
✓ Required fields present (path, method, type)
✓ Environment variables set
  ✓ GENOMONCOLOGY_URL: pwb-demo.genomoncology.io
  ✓ GENOMONCOLOGY_API_KEY: (hidden)

Attempting test request...
✓ HTTP request successful (200 OK)
✓ Response is valid JSON
✓ Response has expected structure (pagination, results)

Sample response (first record):
{
  "gene": "FGF3",
  "name": "FGF3 R144L",
  "mutation_type": "Substitution - Missense",
  "position": 144
}

Test passed! Profile is working correctly.
```

**Failure example:**
```bash
$ jn profile test @genomoncology/alterations

Testing profile: @genomoncology/alterations

✓ Profile file exists
✓ JSON syntax valid
✗ Environment variable not set: GENOMONCOLOGY_API_KEY
  Set with: export GENOMONCOLOGY_API_KEY=your_key_here

Test failed. Fix errors above and retry.
```

---

### 5. `jn profile new <type> <name>`

**Purpose:** Scaffold new profile (optional - agents can write files directly)

**HTTP Source Template:**
```bash
$ jn profile new http myapi/users

Created profile structure:
  jn_home/profiles/http/myapi/_meta.json
  jn_home/profiles/http/myapi/users.json

Edit these files to configure your profile:

_meta.json:
{
  "base_url": "https://${MYAPI_URL}/api",
  "headers": {
    "Authorization": "Bearer ${MYAPI_TOKEN}",
    "Accept": "application/json"
  },
  "timeout": 30
}

users.json:
{
  "path": "/users",
  "method": "GET",
  "type": "source",
  "params": ["id", "email", "page", "limit"]
}

Test with:
  export MYAPI_URL=api.example.com
  export MYAPI_TOKEN=your_token
  jn profile test @myapi/users
  jn cat @myapi/users -p limit=10
```

**JQ Filter Template:**
```bash
$ jn profile new jq myapi/extract-users

Created profile:
  jn_home/profiles/jq/myapi/extract-users.jq

Edit this file with your jq filter logic.

Template:
# Extract and normalize user records
# Parameters: (define any)
#   $field - example parameter

. as $base |
{
  # Your transformation here
}

Test with:
  echo '{"test": "data"}' | jn filter '@myapi/extract-users'
```

---

## Implementation Status

### ✅ Phase 1: Core Discovery (DONE)

**Implemented commands:**
- ✅ `jn profile list` - Text and JSON output with filtering
- ✅ `jn profile info <reference>` - Detailed profile inspection
- ✅ `jn profile search <query>` - Search profiles by name/description

**Features:**
- Text output with organized sections by type
- JSON output for agent consumption
- Type filtering (`--type duckdb`, `--type http`, etc.)
- Format selection (`--format json`, `--format text`)

**Location:** `src/jn/cli/commands/profile.py`

### ✅ Phase 2: Advanced Features (DONE)

**Implemented:**
- ✅ `jn profile tree` - Hierarchical tree view of profiles
- ✅ Filtering by type and namespace
- ✅ Profile metadata extraction from plugins

**Not implemented:**
- ⏭️ `jn profile test <reference>` - Validation (future enhancement)

### ⏭️ Phase 3: Creation (NOT NEEDED)

**Rationale:** Agents and users can create profiles by writing JSON/SQL files directly. Templates add complexity without significant value.

**Current approach:** Documentation and examples show how to create profiles manually.

---

## Architecture

### Service Layer

**File:** `src/jn/profiles/service.py`

```python
def list_profiles(profile_type: Optional[str] = None) -> Dict[str, ProfileInfo]:
    """List all available profiles.

    Args:
        profile_type: Filter by type ('http', 'jq', etc.) or None for all

    Returns:
        Dict mapping profile reference to ProfileInfo
    """

def get_profile_info(reference: str) -> ProfileInfo:
    """Get detailed info about a specific profile.

    Args:
        reference: Profile reference like "@genomoncology/alterations"

    Returns:
        ProfileInfo with all details

    Raises:
        ProfileNotFoundError: If profile doesn't exist
    """

def test_profile(reference: str) -> TestResult:
    """Test if a profile works correctly.

    Makes actual API call (for HTTP) or validates syntax (for JQ).

    Returns:
        TestResult with success/failure and details
    """

def create_profile(profile_type: str, name: str) -> str:
    """Create new profile from template.

    Returns:
        Path to created file(s)
    """
```

**Data Classes:**
```python
@dataclass
class ProfileInfo:
    reference: str           # "@genomoncology/alterations"
    type: str               # "http" or "jq"
    path: Path              # File path
    namespace: str          # "genomoncology"
    name: str               # "alterations"

    # HTTP-specific
    base_url: Optional[str] = None
    endpoint_path: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[Dict] = None
    params: Optional[List[str]] = None
    env_vars: Optional[List[str]] = None

    # JQ-specific
    filter_preview: Optional[str] = None

@dataclass
class TestResult:
    success: bool
    message: str
    errors: List[str]
    sample_output: Optional[Dict] = None
```

---

## Agent Perspective: Why This Design?

### What Agents Can Do Well

✅ **Write files directly**
```python
# Agent creates profile easily
profile = {
    "path": "/users",
    "method": "GET",
    "type": "source",
    "params": ["id", "email"]
}
write_file("jn_home/profiles/http/myapi/users.json", json.dumps(profile, indent=2))
```

✅ **Read structured data**
```bash
# Agent parses JSON easily
jn profile info @genomoncology/alterations --format json
```

### What Agents Need Help With

❌ **Discovering what exists**
- Hard to guess: "Does a genomoncology profile exist?"
- Solution: `jn profile list --format json`

❌ **Understanding parameters**
- Hard to read JSON and extract param info
- Solution: `jn profile info @genomoncology/alterations --format json`

❌ **Validating correctness**
- Hard to test API calls and check responses
- Solution: `jn profile test @genomoncology/alterations`

---

## Alternative: Edit Files Directly?

**User's question:** "Or do you think it would just be better to edit the files directly?"

**Answer:** **Both approaches are needed.**

### Discovery/Inspection: CLI is Better
- Agents shouldn't have to traverse directories manually
- `jn profile list` is faster than `find jn_home/profiles -type f`
- `jn profile info` parses and presents better than raw JSON

### Creation/Editing: Direct Files are Better (for Agents)
- Agents write perfect JSON on first try
- No need for interactive prompts
- Templates via CLI are useful for *humans*, not agents

**Recommendation:**
- **Agents:** Use CLI for discovery, write files directly for creation
- **Humans:** Use CLI for everything (including `jn profile new` templates)

---

## Comparison with Plugin CLI

| Feature | Plugin CLI | Profile CLI (Proposed) |
|---------|-----------|------------------------|
| List all | `jn plugin list` | `jn profile list` |
| Detailed info | `jn plugin info csv_` | `jn profile info @genomoncology/alterations` |
| Tree view | ❌ Not needed | ✅ `jn profile tree` (hierarchical) |
| Test/validate | ❌ Use plugin directly | ✅ `jn profile test <ref>` (makes API call) |
| Create new | ❌ Edit files | ⚠️ `jn profile new` (optional, for humans) |
| JSON output | ✅ `--format json` | ✅ `--format json` |

**Key difference:** Profiles are hierarchical (APIs → endpoints) and parameterized, so they need richer inspection.

---

## Open Questions

### 1. Should `jn profile new` exist?

**For agents:** No, they write files directly.
**For humans:** Yes, templates are helpful.

**Decision:** Implement in Phase 3 (optional), focus on discovery first.

### 2. Should profiles be editable via CLI?

```bash
jn profile edit @genomoncology/alterations  # Opens $EDITOR
```

**Analysis:** This is just a wrapper for `$EDITOR <path>`. Not worth implementing.

**Decision:** No. Users can edit files directly.

### 3. Should there be a `jn profile validate` command?

Separate from `test` - just validates syntax, doesn't make API calls.

**Decision:** Yes, but call it `jn profile check` and make it fast:
```bash
jn profile check @genomoncology/alterations
✓ Valid JSON
✓ Required fields present
✓ Environment variables set
✓ Params declared: gene, mutation_type, biomarker, page, limit

Ready to use. Run 'jn profile test @genomoncology/alterations' to test with API.
```

---

## Success Criteria

### For Agents
- ✅ Can discover all profiles in <1 second
- ✅ Can get parameter list for any profile in JSON format
- ✅ Can validate profile works before using it
- ✅ Can create new profiles by writing JSON files (no CLI needed)

### For Humans
- ✅ Can browse profiles with tree view
- ✅ Can see example usage for any profile
- ✅ Can test profile with real API call
- ✅ (Optional) Can scaffold new profile from template

---

## Summary

### Recommendation

**Implement Profile CLI with focus on discovery and inspection:**

1. **Phase 1 (MVP):**
   - `jn profile list` (text + JSON)
   - `jn profile info <reference>` (detailed view)
   - Essential for agents to discover and understand profiles

2. **Phase 2:**
   - `jn profile tree` (visual hierarchy)
   - `jn profile test <reference>` (validation)
   - Helpful for debugging

3. **Phase 3 (Optional):**
   - `jn profile new <type> <name>` (templates)
   - Only useful for humans; agents write files directly

### For Agents Specifically

**Use CLI for:**
- ✅ Discovery: `jn profile list --format json`
- ✅ Inspection: `jn profile info @api/source --format json`
- ✅ Validation: `jn profile test @api/source`

**Don't use CLI for:**
- ❌ Creation: Write JSON files directly
- ❌ Editing: Edit JSON files directly

**This gives agents superpowers:**
- Fast discovery (no directory traversal)
- Structured info (JSON output)
- Validation (test before use)
- Direct control (write files for creation)

---

## Example Agent Workflow

**Scenario:** Agent needs to fetch BRAF alterations from GenomOncology API

**Step 1: Discover profiles**
```bash
$ jn profile list --format json | jq '.http | keys[]' | grep genomoncology
"@genomoncology/alterations"
"@genomoncology/annotations"
...
```

**Step 2: Get parameters**
```bash
$ jn profile info @genomoncology/alterations --format json
{
  "reference": "@genomoncology/alterations",
  "type": "http",
  "params": ["gene", "mutation_type", "biomarker", "page", "limit"],
  "env_vars": ["GENOMONCOLOGY_URL", "GENOMONCOLOGY_API_KEY"]
}
```

**Step 3: Use profile**
```bash
$ jn cat @genomoncology/alterations -p gene=BRAF -p limit=10
```

**Total time:** <2 seconds (vs. minutes of browsing files manually)
