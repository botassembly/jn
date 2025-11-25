# Coverage Analysis with JN Profiles

JN provides 7 reusable JQ filter profiles for analyzing `coverage.json` files from any codebase. These profiles work as **adapters** for asking common questions about your test coverage.

## Quick Start

```bash
# Generate coverage.json first
make coverage

# Use any profile to analyze coverage
jn cat coverage.json | jn filter '@coverage/uncovered-functions'
jn cat coverage.json | jn filter '@coverage/functions-below-threshold?threshold=80'
jn cat coverage.json | jn filter '@coverage/summary-by-module'
```

---

## Available Profiles

### 1. `@coverage/uncovered-functions`
**Find functions with 0% coverage**

```bash
jn cat coverage.json | jn filter '@coverage/uncovered-functions'
```

**Output:**
```json
{"file":"types.py","function":"ResolvedAddress.__str__","statements":6,"missing_lines":6}
{"file":"report.py","function":"format_json","statements":10,"missing_lines":10}
{"file":"subprocess_rules.py","function":"SubprocessChecker._is_thread_create","statements":5,"missing_lines":5}
{"file":"scanner.py","function":"find_plugin_files","statements":12,"missing_lines":12}
{"file":"violation.py","function":"Violation.__str__","statements":4,"missing_lines":4}
```

**Use case:** Identify functions that have no test coverage at all - these are the highest priority for adding tests.

---

### 2. `@coverage/functions-below-threshold`
**Find functions below a coverage threshold (parameterized)**

```bash
# Default threshold: 80%
jn cat coverage.json | jn filter '@coverage/functions-below-threshold'

# Custom threshold: 60%
jn cat coverage.json | jn filter '@coverage/functions-below-threshold?threshold=60'
```

**Output:**
```json
{"file":"resolver.py","function":"AddressResolver._resolve_url_and_headers","coverage":58,"statements":38,"missing":16,"branches":20}
{"file":"types.py","function":"ResolvedAddress.__str__","coverage":0,"statements":6,"missing":6,"branches":4}
{"file":"structure.py","function":"StructureChecker.check_file","coverage":57,"statements":22,"missing":9,"branches":16}
```

**Parameters:**
- `threshold` (default: 80) - Coverage percentage threshold

**Use case:** Filter functions that don't meet your coverage standards. Adjust threshold based on your team's requirements.

---

### 3. `@coverage/files-by-coverage`
**Group files by coverage ranges**

```bash
jn cat coverage.json | jn filter '@coverage/files-by-coverage'
```

**Output:**
```json
{"range":"80-100%","files":["__init__.py","parser.py","types.py",...],"count":30,"avg_coverage":92}
{"range":"60-80%","files":["resolver.py","report.py","structure.py",...],"count":15,"avg_coverage":73}
{"range":"40-60%","files":["scanner.py","service.py"],"count":3,"avg_coverage":49}
{"range":"20-40%","files":["sh.py"],"count":1,"avg_coverage":20}
{"range":"0-20%","files":["view.py","gmail.py","jc_fallback.py"],"count":3,"avg_coverage":8}
```

**Use case:** Get a high-level overview of coverage distribution across your codebase. Identify files that need urgent attention.

---

### 4. `@coverage/poor-branch-coverage`
**Find functions with poor branch coverage (parameterized)**

```bash
# Default threshold: 70%
jn cat coverage.json | jn filter '@coverage/poor-branch-coverage'

# Custom threshold: 80%
jn cat coverage.json | jn filter '@coverage/poor-branch-coverage?threshold=80'
```

**Output:**
```json
{"file":"parser.py","function":"_expand_shorthand","branches":2,"covered":1,"branch_coverage":50,"partial_branches":1}
{"file":"parser.py","function":"_validate_address","branches":30,"covered":21,"branch_coverage":70,"partial_branches":9}
{"file":"resolver.py","function":"AddressResolver._find_plugin_by_protocol","branches":8,"covered":5,"branch_coverage":62,"partial_branches":3}
{"file":"resolver.py","function":"AddressResolver._resolve_url_and_headers","branches":20,"covered":12,"branch_coverage":60,"partial_branches":8}
```

**Parameters:**
- `threshold` (default: 70) - Branch coverage percentage threshold

**Use case:** Branch coverage reveals untested code paths (if/else, try/except). Functions with many partial branches indicate missing edge case tests.

---

### 5. `@coverage/largest-gaps`
**Functions with the most missing lines (parameterized)**

```bash
# Default: functions with 5+ missing lines
jn cat coverage.json | jn filter '@coverage/largest-gaps'

# Custom: functions with 3+ missing lines
jn cat coverage.json | jn filter '@coverage/largest-gaps?min_missing=3'
```

**Output:**
```json
{"file":"parser.py","function":"_parse_query_string","missing":3,"statements":37,"coverage":87,"uncovered_pct":8}
{"file":"parser.py","function":"_validate_address","missing":9,"statements":30,"coverage":70,"uncovered_pct":30}
{"file":"resolver.py","function":"AddressResolver.plan_execution","missing":7,"statements":52,"coverage":82,"uncovered_pct":13}
{"file":"resolver.py","function":"AddressResolver._find_plugin","missing":7,"statements":42,"coverage":81,"uncovered_pct":16}
{"file":"resolver.py","function":"AddressResolver._find_plugin_by_protocol","missing":6,"statements":17,"coverage":64,"uncovered_pct":35}
```

**Parameters:**
- `min_missing` (default: 5) - Minimum number of uncovered lines

**Use case:** Focus on functions with significant amounts of uncovered code. Sort by `missing` to prioritize functions with the most untested lines.

---

### 6. `@coverage/summary-by-module`
**Aggregate coverage statistics by module/directory**

```bash
jn cat coverage.json | jn filter '@coverage/summary-by-module'
```

**Output:**
```json
{"module":"src/jn/core","files":4,"statements":21,"covered":21,"coverage":100,"branches":8,"branch_coverage":100}
{"module":"src/jn/__init__.py","files":1,"statements":1,"covered":1,"coverage":100,"branches":0,"branch_coverage":100}
{"module":"src/jn/context.py","files":1,"statements":46,"covered":45,"coverage":97,"branches":8,"branch_coverage":100}
{"module":"src/jn/plugins","files":4,"statements":295,"covered":261,"coverage":88,"branches":100,"branch_coverage":82}
{"module":"src/jn/addressing","files":4,"statements":433,"covered":363,"coverage":83,"branches":212,"branch_coverage":75}
{"module":"src/jn/checker","files":10,"statements":605,"covered":479,"coverage":79,"branches":288,"branch_coverage":63}
{"module":"src/jn/cli","files":17,"statements":1504,"covered":1111,"coverage":73,"branches":582,"branch_coverage":63}
{"module":"src/jn/profiles","files":6,"statements":419,"covered":287,"coverage":68,"branches":182,"branch_coverage":56}
{"module":"src/jn/shell","files":2,"statements":86,"covered":15,"coverage":17,"branches":32,"branch_coverage":3}
```

**Use case:** Get module-level coverage overview. Identify which packages/directories need more testing effort.

---

### 7. `@coverage/hotspots`
**Large functions with low coverage (priority scoring)**

```bash
# Default: functions with 10+ statements and <70% coverage
jn cat coverage.json | jn filter '@coverage/hotspots'

# Custom: smaller functions, higher threshold
jn cat coverage.json | jn filter '@coverage/hotspots?min_statements=5&max_coverage=80'
```

**Output:**
```json
{"file":"parser.py","function":"_validate_address","statements":30,"missing":9,"coverage":70,"complexity_score":9,"priority":"low"}
{"file":"resolver.py","function":"AddressResolver._find_plugin_by_format","statements":11,"missing":2,"coverage":78,"complexity_score":2,"priority":"low"}
{"file":"resolver.py","function":"AddressResolver._find_plugin_by_protocol","statements":17,"missing":6,"coverage":64,"complexity_score":6,"priority":"medium"}
{"file":"resolver.py","function":"AddressResolver._find_plugin_by_pattern","statements":20,"missing":5,"coverage":70,"complexity_score":6,"priority":"low"}
{"file":"resolver.py","function":"AddressResolver._build_config","statements":21,"missing":7,"coverage":70,"complexity_score":6,"priority":"low"}
```

**Parameters:**
- `min_statements` (default: 10) - Minimum function size
- `max_coverage` (default: 70) - Maximum coverage percentage

**Priority levels:**
- `critical` - Coverage < 30%
- `high` - Coverage 30-50%
- `medium` - Coverage 50-70%
- `low` - Coverage 70%+

**Use case:** Identify large, complex functions with low coverage. These are high-risk areas that need testing. The `complexity_score` combines size and coverage gaps to prioritize work.

---

## Common Workflows

### Workflow 1: Identify Testing Priorities
```bash
# Step 1: Get high-level module overview
jn cat coverage.json | jn filter '@coverage/summary-by-module'

# Step 2: Find worst-covered modules and drill down
jn cat coverage.json | jn filter '@coverage/functions-below-threshold?threshold=50'

# Step 3: Find specific hotspots to fix
jn cat coverage.json | jn filter '@coverage/hotspots'
```

### Workflow 2: Track Coverage Improvements
```bash
# Before improvements
jn cat coverage.json | jn filter '@coverage/uncovered-functions' | wc -l
# Output: 15 functions with 0% coverage

# After writing tests
jn cat coverage.json | jn filter '@coverage/uncovered-functions' | wc -l
# Output: 8 functions with 0% coverage (7 functions fixed!)
```

### Workflow 3: Branch Coverage Audit
```bash
# Find all functions with incomplete branch coverage
jn cat coverage.json | jn filter '@coverage/poor-branch-coverage?threshold=100'

# Export to CSV for spreadsheet analysis
jn cat coverage.json | jn filter '@coverage/poor-branch-coverage' | jn put branch-coverage.csv
```

### Workflow 4: Generate Coverage Report
```bash
# Create a multi-section coverage report
echo "# Coverage Report" > report.md
echo "" >> report.md

echo "## Summary by Module" >> report.md
jn cat coverage.json | jn filter '@coverage/summary-by-module' | jn put summary.csv
echo "\`\`\`" >> report.md
cat summary.csv >> report.md
echo "\`\`\`" >> report.md
echo "" >> report.md

echo "## Uncovered Functions" >> report.md
jn cat coverage.json | jn filter '@coverage/uncovered-functions' | jn put uncovered.csv
echo "\`\`\`" >> report.md
cat uncovered.csv >> report.md
echo "\`\`\`" >> report.md
```

### Workflow 5: Compare Coverage Across Branches
```bash
# Generate baseline on main branch
git checkout main
make coverage
jn cat coverage.json | jn filter '@coverage/summary-by-module' > main-coverage.json

# Generate coverage on feature branch
git checkout feature-branch
make coverage
jn cat coverage.json | jn filter '@coverage/summary-by-module' > feature-coverage.json

# Compare results
diff main-coverage.json feature-coverage.json
```

---

## Combining Profiles with Other JN Commands

### Pipe to `jn head` for sampling
```bash
jn cat coverage.json | jn filter '@coverage/poor-branch-coverage' | jn head -n 10
```

### Export to CSV for spreadsheets
```bash
jn cat coverage.json | jn filter '@coverage/hotspots' | jn put hotspots.csv
```

### Filter results further
```bash
# Find functions in a specific module with low coverage
jn cat coverage.json | jn filter '@coverage/functions-below-threshold?threshold=80' | \
  jn filter 'select(.file | contains("parser"))'
```

### Count results
```bash
# How many functions have 0% coverage?
jn cat coverage.json | jn filter '@coverage/uncovered-functions' | wc -l
```

---

## Profile Portability

**Key Feature:** These profiles work on ANY `coverage.json` file from ANY codebase.

```bash
# Your project
jn cat ./coverage.json | jn filter '@coverage/summary-by-module'

# Different project
jn cat /path/to/other/project/coverage.json | jn filter '@coverage/summary-by-module'

# Remote coverage file
jn cat https://example.com/coverage.json | jn filter '@coverage/uncovered-functions'
```

No hardcoded paths - profiles adapt to any coverage.json structure.

---

## Tips and Best Practices

1. **Start with summary-by-module** - Get the big picture before diving into function details
2. **Use thresholds that match your team's standards** - Don't hardcode 80% if your team aims for 90%
3. **Combine profiles with grep/jq for custom analysis** - Profiles are building blocks
4. **Export to CSV for sharing** - Makes coverage data accessible to non-technical stakeholders
5. **Track trends over time** - Save coverage reports and compare them across sprints/releases
6. **Focus on branch coverage** - Line coverage alone misses untested code paths
7. **Prioritize hotspots** - Large functions with low coverage are highest risk

---

## Profile Locations

Profiles are stored in: `jn_home/profiles/jq/coverage/`

Available profiles:
- `uncovered-functions.jq`
- `functions-below-threshold.jq`
- `files-by-coverage.jq`
- `poor-branch-coverage.jq`
- `largest-gaps.jq`
- `summary-by-module.jq`
- `hotspots.jq`

You can create custom profiles by adding new `.jq` files to this directory or to your user-level profiles in `~/.local/jn/profiles/jq/coverage/`.

---

## See Also

- **FUNCTION-COVERAGE-ANALYSIS.md** - Detailed analysis of coverage formats (JSON vs XML vs HTML)
- **XML-PLUGIN-GUIDE.md** - Using JN's XML plugin for coverage.xml analysis
- **jq Documentation** - Advanced jq filtering techniques

---

## Examples Summary

| Question | Profile | Example |
|----------|---------|---------|
| What functions have 0% coverage? | `uncovered-functions` | `jn cat coverage.json \| jn filter '@coverage/uncovered-functions'` |
| What functions are below 60% coverage? | `functions-below-threshold` | `jn cat coverage.json \| jn filter '@coverage/functions-below-threshold?threshold=60'` |
| How are files distributed by coverage? | `files-by-coverage` | `jn cat coverage.json \| jn filter '@coverage/files-by-coverage'` |
| What functions have poor branch coverage? | `poor-branch-coverage` | `jn cat coverage.json \| jn filter '@coverage/poor-branch-coverage'` |
| What functions have the most missing lines? | `largest-gaps` | `jn cat coverage.json \| jn filter '@coverage/largest-gaps?min_missing=5'` |
| What is coverage by module? | `summary-by-module` | `jn cat coverage.json \| jn filter '@coverage/summary-by-module'` |
| What large functions need testing? | `hotspots` | `jn cat coverage.json \| jn filter '@coverage/hotspots'` |
