# LCOV Analysis Demo

Analyze LCOV coverage reports using JN's reusable JQ filter profiles.

## Quick Start

```bash
cd demos/lcov-analysis
./run_examples.sh
```

This demo uses the 7 LCOV analysis profiles to extract insights from `coverage.lcov`:

1. **`@lcov/uncovered-functions`** - Functions with 0% coverage
2. **`@lcov/functions-below-threshold`** - Functions below a coverage threshold
3. **`@lcov/files-by-coverage`** - Files grouped by coverage ranges
4. **`@lcov/poor-branch-coverage`** - Functions with poor branch coverage
5. **`@lcov/largest-gaps`** - Functions with most missing lines
6. **`@lcov/summary-by-module`** - Module-level coverage aggregation
7. **`@lcov/hotspots`** - Large under-tested functions (priority scoring)

## Manual Examples

### Find Uncovered Functions
```bash
jn cat coverage.lcov | jn filter '@lcov/uncovered-functions'
```

### Functions Below Threshold (Parameterized)
```bash
jn cat coverage.lcov | jn filter '@lcov/functions-below-threshold?threshold=60'
```

### Module-Level Summary
```bash
jn cat coverage.lcov | jn filter '@lcov/summary-by-module'
```

### Coverage Hotspots
```bash
jn cat coverage.lcov | jn filter '@lcov/hotspots?min_lines=10&max_coverage=70'
```

## Profile Parameters

Profiles support parameterization via query string syntax:

| Profile | Parameters | Default | Example |
|---------|-----------|---------|---------|
| `functions-below-threshold` | `threshold` | 80 | `?threshold=60` |
| `poor-branch-coverage` | `threshold` | 70 | `?threshold=80` |
| `largest-gaps` | `min_missing` | 5 | `?min_missing=3` |
| `hotspots` | `min_lines`, `max_coverage` | 10, 70 | `?min_lines=5&max_coverage=80` |

## Generating coverage.lcov

To generate `coverage.lcov` for your own project:

```bash
# Install pytest-cov
pip install pytest-cov

# Run tests with coverage
pytest --cov=src --cov-report=lcov

# Analyze with JN
jn cat coverage.lcov | jn filter '@lcov/summary-by-module'
```

## See Also

- **jn_home/profiles/jq/lcov/** - Profile source files
