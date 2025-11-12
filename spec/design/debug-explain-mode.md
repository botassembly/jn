# Debug and Explain Mode - Design Specification

## Overview

Add transparency features to JN that show users how data flows through pipelines, how filters transform records, and how profiles are resolved. This addresses the requirement: "Does it show me how it actually generates information?"

## Goals

### Primary Goals

1. **Transparency:** Show users what's happening under the hood
2. **Learning:** Help users understand JN's pipeline model
3. **Debugging:** Diagnose issues in complex pipelines
4. **Trust:** Build confidence through visibility

### Non-Goals

1. Performance profiling (separate feature)
2. Step-through debugging (too complex for CLI tool)
3. Visual flow diagrams (text-only for now)

---

## User Stories

### Story 1: Understanding Profile Resolution

**As a** new JN user
**I want to** see what file my profile reference resolves to
**So that** I can understand where my filter logic comes from

**Example:**
```bash
$ jn filter '@genomoncology/extract-hgvs' --explain
Profile Resolution:
  Reference: @genomoncology/extract-hgvs
  Plugin: jq_
  Search paths:
    1. ~/.local/jn/profiles/jq/genomoncology/extract-hgvs.* (not found)
    2. /home/user/jn/jn_home/profiles/jq/genomoncology/extract-hgvs.* (FOUND)
  Resolved file: /home/user/jn/jn_home/profiles/jq/genomoncology/extract-hgvs.jq

Filter content (first 10 lines):
  # Extract and normalize HGVS nomenclature from GenomOncology annotations
  # Works with both raw annotation records (arrays) or by_transcript output
  ...
```

---

### Story 2: Seeing Filter Transformations

**As a** data analyst
**I want to** see before/after examples of filter transformations
**So that** I can verify the filter does what I expect

**Example:**
```bash
$ jn cat data.json | jn filter '@genomoncology/extract-hgvs' --debug

Input record #1:
{
  "uuid": "abc123",
  "gene": ["BRAF"],
  "hgvs_g": "chr7:g.140453136A>T",
  "hgvs_c": ["NM_004333.4:c.1799T>A"],
  "hgvs_p": ["NP_004324.2:p.Val600Glu"]
}

Output records:
{
  "uuid": "abc123",
  "gene": "BRAF",
  "hgvs_type": "genomic",
  "hgvs": "chr7:g.140453136A>T",
  "chr": "chr7",
  "notation": "g.140453136A>T"
}
{
  "uuid": "abc123",
  "gene": "BRAF",
  "hgvs_type": "coding",
  "hgvs": "NM_004333.4:c.1799T>A",
  "accession": "NM_004333.4",
  "notation": "c.1799T>A"
}
...

Transform: 1 input → 3 outputs (exploded array)
```

---

### Story 3: Pipeline Visibility

**As a** developer
**I want to** see all pipeline stages and their commands
**So that** I can debug complex multi-stage pipelines

**Example:**
```bash
$ jn cat @genomoncology/alterations | jn filter '@genomoncology/extract-alterations' --verbose

Pipeline stages:
  Stage 1: READ @genomoncology/alterations
    Plugin: http_ (/home/user/jn/jn_home/plugins/protocols/http_.py)
    Command: uv run --script /path/to/http_.py --mode read \
             --headers '{"Authorization":"Token ***","Accept":"application/json"}' \
             https://pwb-demo.genomoncology.io/api/alterations
    PID: 12345
    Status: running

  Stage 2: FILTER @genomoncology/extract-alterations
    Plugin: jq_ (/home/user/jn/jn_home/plugins/filters/jq_.py)
    Resolved query: (if .results then .results[] else . end) | ...
    Command: jq -c '(if .results then .results[] else . end) | {...}'
    PID: 12346
    Status: running

Streaming: Stage 1 → Stage 2 (via OS pipe)
Backpressure: Active (64KB buffer)
```

---

## Feature Design

### Mode 1: --explain (Pre-Execution Analysis)

**Purpose:** Show what WILL happen without executing

**Flags:**
- `jn cat @api/source --explain`
- `jn filter '@profile' --explain`
- `jn run source dest --explain`

**Output:**
1. Profile resolution (which file, parameters substituted)
2. Plugin selection (which plugin matched, why)
3. Command that would be executed
4. No actual data processing

**Use cases:**
- Verify profile exists before running
- Check parameter substitution
- Debug profile resolution issues

---

### Mode 2: --debug (Execution with Samples)

**Purpose:** Show actual data transformations with examples

**Flags:**
- `jn filter '@profile' --debug`
- `jn filter '@profile' --debug-limit=5` (show first 5 records)

**Output:**
1. Show first N input records
2. Show corresponding output records
3. Highlight transformations (1→1, 1→many, many→1)
4. Print summary statistics

**Use cases:**
- Verify filter logic on real data
- See before/after transformations
- Test filters during development

**Implementation note:** Requires tee-ing the stream to stderr for display

---

### Mode 3: --verbose (Execution Details)

**Purpose:** Show pipeline structure and process info

**Flags:**
- `jn cat @api/source --verbose`
- `jn filter '@profile' --verbose`
- Global: `JN_VERBOSE=1 jn cat ...` (environment variable)

**Output:**
1. Plugin discovery (which plugins considered, which matched)
2. Process info (PIDs, command lines)
3. Pipeline structure (stages, connections)
4. Timing info (start/end times, duration)

**Use cases:**
- Debug pipeline issues
- Understand performance
- Troubleshoot plugin loading

---

### Mode 4: --dry-run (No Execution)

**Purpose:** Validate syntax and configuration without running

**Flags:**
- `jn run source dest --dry-run`

**Output:**
1. Profile validation (exists, valid JSON/TOML)
2. Plugin validation (found, executable)
3. Parameter validation (required params present)
4. No data processing, no network calls

**Use cases:**
- CI/CD validation
- Profile testing
- Syntax checking

---

## Implementation Architecture

### Layer 1: Framework Support

**Add debug context to pipeline functions:**

```python
@dataclass
class DebugContext:
    """Debug configuration for pipeline execution."""
    mode: str | None = None  # "explain", "debug", "verbose", None
    debug_limit: int = 3      # Number of sample records to show
    output: TextIO = sys.stderr  # Where to write debug info

def read_source(source: str, ..., debug_ctx: DebugContext | None = None):
    """Read source with optional debug output."""
    if debug_ctx and debug_ctx.mode == "explain":
        # Show resolution without executing
        explain_profile_resolution(source, debug_ctx.output)
        return

    if debug_ctx and debug_ctx.mode == "verbose":
        # Log pipeline details to stderr
        log_pipeline_stage("READ", source, plugin_info, debug_ctx.output)

    # Normal execution...
```

---

### Layer 2: Profile Explainer

**Module:** `src/jn/debug/explainer.py`

**Functions:**

```python
def explain_profile_resolution(reference: str, output: TextIO):
    """Explain how a profile reference resolves to a file."""
    print("Profile Resolution:", file=output)
    print(f"  Reference: {reference}", file=output)

    if reference.startswith("@"):
        # HTTP profile
        api_name, source_name = parse_reference(reference)
        print(f"  API: {api_name}", file=output)
        print(f"  Source: {source_name}", file=output)

        # Show search paths
        print("  Search paths:", file=output)
        for i, path in enumerate(find_profile_paths(), 1):
            profile_path = path / api_name / f"{source_name}.json"
            exists = "FOUND" if profile_path.exists() else "not found"
            print(f"    {i}. {profile_path} ({exists})", file=output)

        # Show resolved content
        try:
            profile = load_hierarchical_profile(api_name, source_name)
            print(f"\nResolved configuration:", file=output)
            print(json.dumps(profile, indent=2), file=output)
        except ProfileError as e:
            print(f"\nError: {e}", file=output)
    else:
        # File path
        print(f"  Type: File", file=output)
        print(f"  Path: {reference}", file=output)


def explain_plugin_selection(source: str, plugins: dict, registry, output: TextIO):
    """Explain which plugin matched and why."""
    print("Plugin Selection:", file=output)
    print(f"  Source: {source}", file=output)

    # Show all plugins considered
    print("  Available plugins:", file=output)
    for name, plugin in plugins.items():
        matches = [m for m in plugin.matches if re.match(m, source)]
        if matches:
            print(f"    ✓ {name}: matches {matches}", file=output)
        else:
            print(f"    ✗ {name}: no match", file=output)

    # Show selected plugin
    matched = registry.match(source)
    if matched:
        plugin = plugins[matched]
        print(f"\n  Selected: {matched}", file=output)
        print(f"  Path: {plugin.path}", file=output)
    else:
        print(f"\n  ERROR: No plugin found", file=output)
```

---

### Layer 3: Debug Stream Interceptor

**Module:** `src/jn/debug/interceptor.py`

**Purpose:** Tee stream to show sample records

```python
class DebugInterceptor:
    """Intercept stream to show sample records without disrupting flow."""

    def __init__(self, debug_ctx: DebugContext):
        self.ctx = debug_ctx
        self.count = 0
        self.shown = 0

    def intercept(self, proc: subprocess.Popen, label: str):
        """Wrap process stdout to show samples."""
        if self.ctx.mode != "debug":
            return proc.stdout

        # Create wrapper that tees output
        return DebugStreamWrapper(
            proc.stdout,
            label,
            limit=self.ctx.debug_limit,
            output=self.ctx.output
        )


class DebugStreamWrapper:
    """Wrapper that prints samples to stderr while passing through."""

    def __init__(self, stream, label, limit, output):
        self.stream = stream
        self.label = label
        self.limit = limit
        self.output = output
        self.count = 0

    def __iter__(self):
        return self

    def __next__(self):
        line = next(self.stream)

        # Show first N records
        if self.count < self.limit:
            if self.count == 0:
                print(f"\n{self.label} (first {self.limit} records):", file=self.output)
            print(f"  [{self.count+1}] {line.rstrip()}", file=self.output)

        self.count += 1

        # After limit, show summary
        if self.count == self.limit:
            print(f"  ... (showing first {self.limit}, continuing stream)", file=self.output)

        return line  # Pass through unchanged
```

---

### Layer 4: Command Integration

**Add flags to commands:**

```python
# src/jn/cli/commands/cat.py
@click.command()
@click.argument("input_file")
@click.option("--explain", is_flag=True, help="Show profile resolution without executing")
@click.option("--verbose", is_flag=True, help="Show pipeline details")
@pass_context
def cat(ctx, input_file, explain, verbose):
    """Read file and output NDJSON to stdout."""
    debug_ctx = None
    if explain:
        debug_ctx = DebugContext(mode="explain")
    elif verbose:
        debug_ctx = DebugContext(mode="verbose")

    read_source(input_file, ctx.plugin_dir, ctx.cache_path,
                output_stream=sys.stdout, debug_ctx=debug_ctx)


# src/jn/cli/commands/filter.py
@click.command()
@click.argument("query")
@click.option("--explain", is_flag=True, help="Show query resolution without executing")
@click.option("--debug", is_flag=True, help="Show sample input/output records")
@click.option("--debug-limit", type=int, default=3, help="Number of sample records to show")
@pass_context
def filter(ctx, query, explain, debug, debug_limit):
    """Filter NDJSON using jq expression or profile."""
    debug_ctx = None
    if explain:
        debug_ctx = DebugContext(mode="explain")
    elif debug:
        debug_ctx = DebugContext(mode="debug", debug_limit=debug_limit)

    filter_stream(query, ctx.plugin_dir, ctx.cache_path,
                  params=params, debug_ctx=debug_ctx)
```

---

## Output Examples

### Example 1: --explain for HTTP Profile

```bash
$ jn cat @genomoncology/alterations --explain

Profile Resolution:
  Reference: @genomoncology/alterations
  Type: HTTP profile
  API: genomoncology
  Source: alterations

Search paths:
  1. ~/.local/jn/profiles/http/genomoncology/alterations.json (not found)
  2. /home/user/jn/jn_home/profiles/http/genomoncology/alterations.json (FOUND)

Resolved configuration:
  _meta.json:
    base_url: https://${GENOMONCOLOGY_URL}/api
    headers:
      Authorization: Token ${GENOMONCOLOGY_API_KEY}
      Accept: application/json
    timeout: 60

  alterations.json:
    path: /alterations
    method: GET
    type: source

Environment variables:
  GENOMONCOLOGY_URL: pwb-demo.genomoncology.io ✓
  GENOMONCOLOGY_API_KEY: *** (set) ✓

Final URL: https://pwb-demo.genomoncology.io/api/alterations

Plugin Selection:
  Matched: http_
  Path: /home/user/jn/jn_home/plugins/protocols/http_.py
  Reason: Pattern match: ^https?://.*

Would execute:
  uv run --script /home/user/jn/jn_home/plugins/protocols/http_.py \
    --mode read \
    --headers '{"Authorization":"Token ***","Accept":"application/json"}' \
    https://pwb-demo.genomoncology.io/api/alterations

(Not executing - use without --explain to run)
```

---

### Example 2: --explain for Filter Profile

```bash
$ jn filter '@genomoncology/extract-hgvs' --explain

Profile Resolution:
  Reference: @genomoncology/extract-hgvs
  Plugin: jq_ (filter plugin)

Search paths:
  1. ~/.local/jn/profiles/jq/genomoncology/extract-hgvs.* (not found)
  2. /home/user/jn/jn_home/profiles/jq/genomoncology/extract-hgvs.* (FOUND)

Resolved file: /home/user/jn/jn_home/profiles/jq/genomoncology/extract-hgvs.jq
File size: 2,847 bytes
Last modified: 2025-01-10 14:23:45

Filter content (first 20 lines):
   1 # Extract and normalize HGVS nomenclature from GenomOncology annotations
   2 # Works with both raw annotation records (arrays) or by_transcript output
   3 #
   4 # HGVS (Human Genome Variation Society) nomenclature includes:
   5 #   g. = genomic reference (chr7:g.140453136A>T)
   6 #   c. = coding DNA reference (NM_004333.4:c.1799T>A)
   7 #   p. = protein reference (NP_004324.2:p.Val600Glu)
   8 ...
  20 # Example Output:

Parameters: None

Would execute:
  jq -c '. as $base | ($base.gene | if type == "array" ...'

(Not executing - use without --explain to run)
```

---

### Example 3: --debug for Filter

```bash
$ jn cat test.json | jn filter '@genomoncology/extract-hgvs' --debug --debug-limit=2

Filter: @genomoncology/extract-hgvs
Plugin: jq_
Query: . as $base | ($base.gene | if type == "array" ...

Input record [1]:
{
  "uuid": "abc123",
  "gene": ["BRAF"],
  "hgvs_g": "chr7:g.140453136A>T",
  "hgvs_c": ["NM_004333.4:c.1799T>A", "NM_004333.5:c.1799T>A"],
  "hgvs_p": ["NP_004324.2:p.Val600Glu"]
}

Output records:
{
  "uuid": "abc123",
  "gene": "BRAF",
  "hgvs_type": "genomic",
  "hgvs": "chr7:g.140453136A>T",
  "chr": "chr7",
  "notation": "g.140453136A>T"
}
{
  "uuid": "abc123",
  "gene": "BRAF",
  "hgvs_type": "coding",
  "hgvs": "NM_004333.4:c.1799T>A",
  "accession": "NM_004333.4",
  "notation": "c.1799T>A"
}
{
  "uuid": "abc123",
  "gene": "BRAF",
  "hgvs_type": "coding",
  "hgvs": "NM_004333.5:c.1799T>A",
  "accession": "NM_004333.5",
  "notation": "c.1799T>A"
}
{
  "uuid": "abc123",
  "gene": "BRAF",
  "hgvs_type": "protein",
  "hgvs": "NP_004324.2:p.Val600Glu",
  "accession": "NP_004324.2",
  "notation": "p.Val600Glu"
}

Transform: 1 input → 4 outputs (array explosion)

Input record [2]:
{
  "uuid": "xyz789",
  "gene": ["EGFR"],
  "hgvs_g": "",
  "hgvs_c": [],
  "hgvs_p": null
}

Output records:
{
  "uuid": "xyz789",
  "gene": ["EGFR"],
  "hgvs_g": "",
  "hgvs_c": [],
  "hgvs_p": null
}

Transform: 1 input → 1 output (no HGVS found, returned original)

... (showing first 2 inputs, continuing stream)
```

---

### Example 4: --verbose for Pipeline

```bash
$ jn run @genomoncology/alterations output.csv --verbose

Pipeline: @genomoncology/alterations → output.csv

Stage 1: READ @genomoncology/alterations
  Profile: HTTP source
  Plugin: http_ (/home/user/jn/jn_home/plugins/protocols/http_.py)
  URL: https://pwb-demo.genomoncology.io/api/alterations
  Headers: Authorization=Token ***, Accept=application/json
  Command: uv run --script /path/to/http_.py --mode read ...
  PID: 45231
  Started: 2025-01-10 15:42:13
  Status: running

Stage 2: WRITE output.csv
  Plugin: csv_ (/home/user/jn/jn_home/plugins/formats/csv_.py)
  Dialect: excel (default)
  Command: uv run --script /path/to/csv_.py --mode write
  PID: 45232
  Started: 2025-01-10 15:42:13
  Status: running

Pipeline structure:
  http_ (45231) --pipe--> csv_ (45232) --> output.csv

Backpressure: Active (OS pipe buffer ~64KB)

Execution:
  Stage 1: completed in 2.3s (exit code 0)
  Stage 2: completed in 2.4s (exit code 0)

Output: output.csv (3.2 MB, 55,839 records)
```

---

## Configuration

### Environment Variables

```bash
# Global debug mode (affects all commands)
export JN_DEBUG=1         # Equivalent to --debug
export JN_VERBOSE=1       # Equivalent to --verbose
export JN_EXPLAIN=1       # Equivalent to --explain

# Debug output destination
export JN_DEBUG_OUTPUT=/tmp/jn-debug.log  # Log to file instead of stderr
```

---

## Performance Impact

### --explain
- **Impact:** None (no execution)
- **Use case:** Pre-flight checks, CI/CD

### --debug
- **Impact:** Minimal (small buffer for samples)
- **Implementation:** Tee first N records to stderr, pass through rest
- **Memory:** ~1KB per sample record

### --verbose
- **Impact:** Minimal (logging to stderr)
- **Implementation:** Print metadata, don't touch data stream
- **Memory:** Negligible

### General Principle
Debug modes MUST NOT:
- Buffer entire dataset in memory
- Slow down streaming (except sample capture)
- Break backpressure mechanism

---

## Testing Strategy

### Unit Tests

```python
def test_explain_profile_resolution():
    """Test --explain shows correct profile paths."""
    output = io.StringIO()
    debug_ctx = DebugContext(mode="explain", output=output)
    read_source("@genomoncology/alterations", ..., debug_ctx=debug_ctx)

    assert "Profile Resolution:" in output.getvalue()
    assert "genomoncology" in output.getvalue()
    assert "alterations.json (FOUND)" in output.getvalue()


def test_debug_filter_shows_samples():
    """Test --debug shows input/output samples."""
    input_data = '{"uuid":"abc","gene":["BRAF"]}\n'
    output = io.StringIO()
    debug_ctx = DebugContext(mode="debug", debug_limit=1, output=output)

    filter_stream(
        "@genomoncology/extract-hgvs",
        ...,
        input_stream=io.StringIO(input_data),
        debug_ctx=debug_ctx
    )

    assert "Input record [1]:" in output.getvalue()
    assert "Output records:" in output.getvalue()
```

### Integration Tests

```bash
# Test explain mode
jn cat @genomoncology/alterations --explain 2>&1 | grep "Profile Resolution"

# Test debug mode
echo '{"uuid":"abc","gene":["BRAF"],"hgvs_c":["NM_004333.4:c.1799T>A"]}' | \
  jn filter '@genomoncology/extract-hgvs' --debug 2>&1 | grep "Transform:"

# Test verbose mode
jn run test.json test.csv --verbose 2>&1 | grep "Pipeline:"
```

---

## Future Enhancements

### Phase 2: Interactive Mode

```bash
$ jn filter '@genomoncology/extract-hgvs' --interactive
Processing record 1/100...
  Input: {"uuid":"abc","gene":["BRAF"],...}
  Output (4 records): genomic, coding, coding, protein
  Continue? [y/n/q] y

Processing record 2/100...
  ...
```

### Phase 3: Visual Pipeline Diagrams

```bash
$ jn run complex.json output.csv --visualize
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ csv_reader  │───▶│ jq_filter    │───▶│ json_writer │
│ PID: 12345  │    │ PID: 12346   │    │ PID: 12347  │
│ ●  Running  │    │ ●  Running   │    │ ●  Running  │
└─────────────┘    └──────────────┘    └─────────────┘
   2.1 MB/s            Backpressure         1.9 MB/s
```

### Phase 4: Performance Profiling

```bash
$ jn run input.json output.csv --profile
Plugin Performance:
  csv_reader: 1.2s CPU, 45MB read, 2000 records/sec
  jq_filter:  0.8s CPU, filtering took 40% of time
  json_writer: 1.1s CPU, 38MB written, 1800 records/sec

Bottleneck: json_writer (slowest stage)
```

---

## Documentation Updates

### User Guide

Add new section: "Debugging and Understanding Pipelines"

- How to use --explain for profile exploration
- How to use --debug for filter development
- How to use --verbose for troubleshooting
- Common debugging patterns

### Reference

Add flags to command documentation:
- `jn cat --help` → document --explain, --verbose
- `jn filter --help` → document --explain, --debug, --debug-limit
- `jn run --help` → document --verbose, --dry-run

---

## Success Metrics

### Adoption
- 20%+ of advanced users use --explain regularly
- 10%+ of filter development uses --debug

### Support
- Reduce "how does this work?" questions by 50%
- Reduce "profile not found" errors by 30%

### Trust
- User feedback: "JN is transparent and understandable"
- New users can debug issues independently

---

## Appendix: Implementation Checklist

### Core Infrastructure
- [ ] Create `src/jn/debug/` module
- [ ] Add `DebugContext` dataclass
- [ ] Add debug parameters to pipeline functions
- [ ] Create `explainer.py` with resolution logic
- [ ] Create `interceptor.py` with stream tee logic

### Command Integration
- [ ] Add `--explain` to `jn cat`
- [ ] Add `--verbose` to `jn cat`
- [ ] Add `--explain` to `jn filter`
- [ ] Add `--debug` to `jn filter`
- [ ] Add `--debug-limit` to `jn filter`
- [ ] Add `--verbose` to `jn run`
- [ ] Add `--dry-run` to `jn run`

### Profile Explainers
- [ ] HTTP profile explainer
- [ ] JQ profile explainer
- [ ] Generic file explainer

### Plugin Explainers
- [ ] Plugin discovery explainer
- [ ] Plugin matching explainer
- [ ] Plugin command builder explainer

### Testing
- [ ] Unit tests for explainer functions
- [ ] Unit tests for debug interceptor
- [ ] Integration tests for each debug mode
- [ ] Test with complex pipelines

### Documentation
- [ ] User guide: Debugging section
- [ ] Reference: Updated command docs
- [ ] Examples: Common debugging patterns
- [ ] Troubleshooting: Common issues guide

### Environment Variables
- [ ] Support JN_DEBUG
- [ ] Support JN_VERBOSE
- [ ] Support JN_EXPLAIN
- [ ] Support JN_DEBUG_OUTPUT
