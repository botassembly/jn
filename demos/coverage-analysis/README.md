# Coverage Analysis Demo

Analyze pytest coverage reports using JN's reusable JQ filter profiles.

## Quick Start

```bash
cd demos/coverage-analysis
./run_examples.sh
```

This demo uses the 7 coverage analysis profiles to extract insights from `coverage.json`:

1. **`@coverage/uncovered-functions`** - Functions with 0% coverage
2. **`@coverage/functions-below-threshold`** - Functions below a coverage threshold
3. **`@coverage/files-by-coverage`** - Files grouped by coverage ranges
4. **`@coverage/poor-branch-coverage`** - Functions with poor branch coverage
5. **`@coverage/largest-gaps`** - Functions with most missing lines
6. **`@coverage/summary-by-module`** - Module-level coverage aggregation
7. **`@coverage/hotspots`** - Large under-tested functions (priority scoring)

## Manual Examples

### Find Uncovered Functions
```bash
jn cat coverage.json | jn filter '@coverage/uncovered-functions'
```

Output:
```json
{"file":"types.py","function":"ResolvedAddress.__str__","statements":6,"missing_lines":6}
{"file":"report.py","function":"format_json","statements":10,"missing_lines":10}
{"file":"scanner.py","function":"find_plugin_files","statements":12,"missing_lines":12}
```

### Functions Below Threshold (Parameterized)
```bash
jn cat coverage.json | jn filter '@coverage/functions-below-threshold?threshold=60'
```

Output:
```json
{"file":"resolver.py","function":"AddressResolver._resolve_url_and_headers","coverage":58,"statements":38,"missing":16,"branches":20}
{"file":"structure.py","function":"StructureChecker.check_file","coverage":57,"statements":22,"missing":9,"branches":16}
```

### Module-Level Summary
```bash
jn cat coverage.json | jn filter '@coverage/summary-by-module'
```

Output:
```json
{"module":"src/jn/core","files":4,"statements":21,"covered":21,"coverage":100,"branches":8,"branch_coverage":100}
{"module":"src/jn/plugins","files":4,"statements":295,"covered":261,"coverage":88,"branches":100,"branch_coverage":82}
{"module":"src/jn/addressing","files":4,"statements":433,"covered":363,"coverage":83,"branches":212,"branch_coverage":75}
{"module":"src/jn/cli","files":17,"statements":1504,"covered":1111,"coverage":73,"branches":582,"branch_coverage":63}
```

### Coverage Hotspots
```bash
jn cat coverage.json | jn filter '@coverage/hotspots?min_statements=10&max_coverage=70'
```

Output:
```json
{"file":"parser.py","function":"_validate_address","statements":30,"missing":9,"coverage":70,"complexity_score":9,"priority":"low"}
{"file":"resolver.py","function":"AddressResolver._find_plugin_by_protocol","statements":17,"missing":6,"coverage":64,"complexity_score":6,"priority":"medium"}
```

## Common Workflows

### Workflow 1: Identify Testing Priorities
```bash
# Get high-level module overview
jn cat coverage.json | jn filter '@coverage/summary-by-module'

# Find worst-covered modules
jn cat coverage.json | jn filter '@coverage/functions-below-threshold?threshold=50'

# Find specific hotspots to fix
jn cat coverage.json | jn filter '@coverage/hotspots'
```

### Workflow 2: Track Coverage Improvements
```bash
# Before improvements
jn cat coverage.json | jn filter '@coverage/uncovered-functions' | wc -l
# Output: 17 functions with 0% coverage

# After writing tests
jn cat coverage.json | jn filter '@coverage/uncovered-functions' | wc -l
# Output: 10 functions with 0% coverage (7 functions fixed!)
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
# The demo script (run_examples.sh) generates a comprehensive markdown report
./run_examples.sh

# View the generated report
cat coverage_report.md
```

## Profile Parameters

Profiles support parameterization via query string syntax:

| Profile | Parameters | Default | Example |
|---------|-----------|---------|---------|
| `functions-below-threshold` | `threshold` | 80 | `?threshold=60` |
| `poor-branch-coverage` | `threshold` | 70 | `?threshold=80` |
| `largest-gaps` | `min_missing` | 5 | `?min_missing=3` |
| `hotspots` | `min_statements`, `max_coverage` | 10, 70 | `?min_statements=5&max_coverage=80` |

## Portability

**Key Feature**: These profiles work on ANY `coverage.json` file from ANY codebase.

```bash
# Your project
jn cat ./coverage.json | jn filter '@coverage/summary-by-module'

# Different project
jn cat /path/to/other/project/coverage.json | jn filter '@coverage/summary-by-module'

# Remote coverage file
jn cat https://example.com/coverage.json | jn filter '@coverage/uncovered-functions'
```

No hardcoded paths - profiles adapt to any coverage.json structure.

## Generating coverage.json

To generate `coverage.json` for your own project:

```bash
# Install pytest-cov
pip install pytest-cov

# Configure in pyproject.toml or .coveragerc
# [tool.coverage.json]
# output = "coverage.json"

# Run tests with coverage
pytest --cov=src --cov-report=json

# Analyze with JN
jn cat coverage.json | jn filter '@coverage/summary-by-module'
```

## Output Files

The demo script generates these files:

- `uncovered.json` - Functions with 0% coverage
- `low_coverage.json` - Functions below 60% threshold
- `coverage_ranges.json` - Files grouped by coverage ranges
- `poor_branches.json` - Functions with poor branch coverage
- `gaps.json` - Functions with most missing lines
- `summary.json` - Module-level coverage summary
- `hotspots.json` - Large under-tested functions
- `coverage_report.md` - Comprehensive markdown report
- `hotspots.csv`, `summary.csv` - CSV exports for spreadsheets

## See Also

- **examples/COVERAGE-PROFILES-GUIDE.md** - Comprehensive guide with all workflows
- **examples/FUNCTION-COVERAGE-ANALYSIS.md** - Analysis of coverage formats (JSON vs XML vs HTML)
- **jn_home/profiles/jq/coverage/** - Profile source files
