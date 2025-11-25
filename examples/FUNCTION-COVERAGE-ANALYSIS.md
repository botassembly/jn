# Function-Level Coverage Analysis

## Coverage Format Comparison

| Format | Function-Level Stats | Line-Level Stats | Best For |
|--------|---------------------|------------------|----------|
| **JSON** | ✅ Full details | ✅ Yes | **Programmatic analysis, complete data** |
| **XML** | ❌ Empty `<methods/>` | ✅ Yes | CI/CD tools, line-level analysis |
| **HTML** | ✅ Full details | ✅ Yes | Visual inspection, browsing |

### JSON Format: Complete Function-Level Data

The `coverage.json` file contains comprehensive function-level statistics:

```json
{
  "files": {
    "src/jn/addressing/parser.py": {
      "functions": {
        "parse_address": {
          "executed_lines": [50, 51, 53, 57, 65, ...],
          "summary": {
            "covered_lines": 36,
            "num_statements": 36,
            "percent_covered": 100.0,
            "missing_lines": 0,
            "num_branches": 18,
            "covered_branches": 18,
            "missing_branches": 0
          },
          "missing_lines": [],
          "executed_branches": [[50,51], [50,53], ...],
          "missing_branches": []
        }
      }
    }
  }
}
```

### XML Format: Limited to Line-Level

The `coverage.xml` (Cobertura format) has `<methods/>` tags but they're always empty:

```xml
<class name="parser.py" filename="parser.py" line-rate="0.86" branch-rate="0.78">
    <methods/>  <!-- Empty! No function-level data -->
    <lines>
        <line number="50" hits="1"/>
        <line number="51" hits="1" branch="true" condition-coverage="100% (2/2)"/>
        ...
    </lines>
</class>
```

## Extracting Function-Level Statistics

### Using JN to Extract Low-Coverage Functions

```bash
# Functions with < 80% coverage
jq -r '
.files
| to_entries
| map(.key as $file | .value.functions | to_entries | map({
    file: ($file | split("/") | .[-1]),
    function: .key,
    coverage: (.value.summary.percent_covered | floor),
    statements: .value.summary.num_statements,
    missing: .value.summary.missing_lines
  }))
| .[] | .[]
| select(.function != "" and .coverage < 80)
| [.file, .function, .coverage, .missing]
| @csv
' coverage.json
```

### Output Example

```csv
"File","Function","Coverage%","Statements","Missing","Branches"
"parser.py","_expand_shorthand",60,3,1,2
"parser.py","_validate_address",70,30,9,30
"resolver.py","AddressResolver._find_plugin_by_protocol",64,17,6,8
"resolver.py","AddressResolver._resolve_url_and_headers",58,38,16,20
"types.py","ResolvedAddress.__str__",0,6,6,4
"report.py","format_json",0,10,10,2
"structure.py","StructureChecker.check_file",57,22,9,16
```

## HTML Function Index

The HTML coverage report includes a dedicated **function_index.html** page:

- **Location**: `coverage-html/function_index.html`
- **Features**:
  - Sortable columns (file, function, statements, missing, branches, coverage)
  - Clickable links to source code
  - Filter capability
  - Branch coverage details

### Sample HTML Structure

```html
<tr class="region">
    <td class="name left">src/jn/addressing/parser.py</td>
    <td class="name left">parse_address</td>
    <td>36</td>  <!-- statements -->
    <td>0</td>   <!-- missing -->
    <td>0</td>   <!-- excluded -->
    <td>18</td>  <!-- branches -->
    <td>0</td>   <!-- partial -->
    <td class="right">100%</td>
</tr>
```

## Analysis Patterns

### Pattern 1: Find Functions Needing Tests

```bash
# Functions with 0% coverage
jq '.files
| to_entries[]
| .value.functions
| to_entries[]
| select(.value.summary.percent_covered == 0)
| {function: .key, file: input_filename}' coverage.json
```

**Results:**
- `ResolvedAddress.__str__` (types.py)
- `format_json` (report.py)
- `SubprocessChecker._is_thread_create` (subprocess_rules.py)
- `find_plugin_files` (scanner.py)
- `Violation.__str__` (violation.py)

### Pattern 2: Functions with Poor Branch Coverage

```bash
# Functions with branches but < 70% branch coverage
jq '.files
| to_entries[]
| .value.functions
| to_entries[]
| select(.value.summary.num_branches > 0)
| select((.value.summary.covered_branches * 100.0 / .value.summary.num_branches) < 70)
| {
    function: .key,
    branch_coverage: ((.value.summary.covered_branches * 100 / .value.summary.num_branches) | floor)
  }' coverage.json
```

### Pattern 3: Largest Uncovered Functions

```bash
# Functions with most missing statements
jq -r '.files
| to_entries[]
| .value.functions
| to_entries[]
| select(.value.summary.missing_lines > 5)
| [.key, .value.summary.missing_lines, .value.summary.percent_covered]
| @tsv' coverage.json | sort -k2 -nr
```

**Top uncovered functions:**
- `AddressResolver._resolve_url_and_headers` - 16 missing lines (58% coverage)
- `StructureChecker.check_dependencies` - 14 missing lines (55% coverage)
- `Whitelist._matches_pattern` - 14 missing lines (53% coverage)
- `format_json` - 10 missing lines (0% coverage)
- `StructureChecker.check_file` - 9 missing lines (57% coverage)

## Creating Custom Reports

### Export to CSV for Excel Analysis

```bash
jq -r '
["File", "Function", "Coverage%", "Statements", "Covered", "Missing", "Branches", "Branch_Coverage%"],
(.files | to_entries[] | .key as $file | .value.functions | to_entries[]
| select(.key != "")
| [
    ($file | split("/") | .[-1]),
    .key,
    (.value.summary.percent_covered | floor),
    .value.summary.num_statements,
    .value.summary.covered_lines,
    .value.summary.missing_lines,
    .value.summary.num_branches,
    (if .value.summary.num_branches > 0
     then ((.value.summary.covered_branches * 100.0 / .value.summary.num_branches) | floor)
     else 100 end)
  ])
| @csv' coverage.json > function-coverage-full.csv
```

### Filter by Module

```bash
# Only checker module functions
jq '.files
| to_entries[]
| select(.key | startswith("src/jn/checker/"))
| .value.functions' coverage.json
```

## Key Insights from Current Coverage

### Functions Needing Immediate Attention (0% coverage)

1. **types.py::ResolvedAddress.__str__** - String representation not tested
2. **report.py::format_json** - JSON formatting not tested
3. **subprocess_rules.py::SubprocessChecker._is_thread_create** - Thread detection untested
4. **scanner.py::find_plugin_files** - Plugin file discovery untested
5. **violation.py::Violation.__str__** - Violation display untested

### Functions with Complex Logic Needing More Tests (< 60% coverage)

1. **resolver.py::AddressResolver._resolve_url_and_headers** - 58% (URL resolution)
2. **structure.py::StructureChecker.check_dependencies** - 55% (Dependency checking)
3. **structure.py::StructureChecker.check_file** - 57% (File structure validation)
4. **whitelist.py::Whitelist._matches_pattern** - 53% (Pattern matching)

### Well-Tested Functions (100% coverage)

- `parse_address` (parser.py)
- `_determine_type` (parser.py)
- All functions in `core/streaming.py`
- All functions in `core/plugins.py`

## Recommendation

**Use JSON format for function-level analysis** because:
- ✅ Complete function-level statistics
- ✅ Branch coverage per function
- ✅ Executed vs missing lines per function
- ✅ Easy to query with jq/jn
- ✅ Programmatically accessible

**Use HTML for visual exploration:**
- Browse `coverage-html/function_index.html` in a browser
- Sort by coverage percentage
- Click through to see specific line coverage

**XML format limitations:**
- ❌ No function-level data (empty `<methods/>` tags)
- ✅ Still useful for line-level analysis and CI/CD tools
