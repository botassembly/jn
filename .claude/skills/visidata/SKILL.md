---
name: visidata
description: Expert in VisiData terminal spreadsheet tool for exploring, cleaning, and transforming tabular data. Covers installation via uv, interactive data exploration, conversion between formats (CSV/JSON/Excel/SQLite), filtering, aggregations, and integration with JN pipelines. Use when working with data exploration, analysis, format conversion, or visual data inspection.
allowed-tools: Bash, Read, Write
---

# VisiData Expert

VisiData (vd) is a terminal-based multitool for tabular data exploration, cleaning, editing, and restructuring.

## Installation

**ALWAYS install VisiData using `uv tool install`:**

```bash
# Install VisiData as a uv tool (recommended)
uv tool install visidata

# Verify installation
vd --version

# Check if already installed
uv tool list | grep visidata
```

**Alternative installations (use only if uv not available):**
```bash
# pip (not recommended for this project)
pip install visidata

# System package managers
brew install visidata      # macOS
apt install visidata        # Debian/Ubuntu
```

**Updating:**
```bash
uv tool upgrade visidata
```

## Quick Start

**Launch VisiData:**
```bash
vd                          # Browse current directory
vd data.csv                 # Open CSV file
vd data.json data.xlsx      # Open multiple files
vd -f sqlite db.sqlite      # Force specific format
```

**One-liner conversions (batch mode):**
```bash
vd -b input.csv -o output.json           # CSV → JSON
vd -b input.xlsx -o output.tsv           # Excel → TSV
vd -b data.fixed -o data.csv             # Fixed-width → CSV
vd --play script.vdj -b -o output.tsv    # Replay saved workflow
```

## Core Navigation

**Movement (vim-style):**
```
hjkl          left/down/up/right (or arrow keys)
gg / G        top / bottom of sheet
gh / gl       leftmost / rightmost column
gj / gk       bottom / top row
^F / ^B       page forward / back
zz            center current row
```

**Search:**
```
/ regex       search forward in current column
? regex       search backward in current column
g/ regex      search all visible columns
n / N         next / previous match
< / >         next different value in column
{ / }         next selected row
```

**Jump:**
```
zr N          go to row N (0-indexed)
zc N          go to column N (0-indexed)
c regex       go to column matching regex
```

## Column Operations

**Type Setting:**
```
~             set column type to string
#             set column type to int
%             set column type to float
$             set column type to currency
@             set column type to date
z#            set column type to len (length)
```

**Visibility & Arrangement:**
```
_             toggle column width (full/default)
g_            toggle all column widths
z_ N          set column width to N
-             hide current column
gv            unhide all columns
H / L         move column left / right
gH / gL       move column to far left / right
```

**Key Columns:**
```
!             toggle current column as key column
z!            unset current column as key
```

**Editing:**
```
^             rename current column
e text        edit current cell
ge text       set current column for selected rows
= expr        create new column from Python expression
g= expr       set current column for selected rows
i             add column with incremental values
```

**Transform:**
```
: regex       split column by regex
; regex       extract capture groups
* find Tab replace    find/replace with regex
g*            find/replace in selected rows
(             expand lists/dicts one level
)             unexpand/collapse column
```

## Row Operations

**Selection:**
```
s / t / u     select / toggle / unselect current row
gs / gt / gu  select / toggle / unselect all rows
| regex       select rows matching regex in current column
g| regex      select matching any visible column
, (comma)     select rows matching current cell value
g,            select rows matching current row
```

**Sorting:**
```
[ / ]         sort ascending / descending by current column
g[ / g]       sort by all key columns
z[ / z]       sort but keep existing sort criteria
```

**Filtering:**
```
"             open duplicate sheet with only selected rows
g"            open duplicate sheet with all rows
gz"           open sheet with deepcopy of selected rows
```

**Editing:**
```
a / ga        append blank row(s)
d / gd        delete current / selected rows
y / gy        yank (copy) current / selected rows to clipboard
x / gx        cut current / selected rows
p / P         paste rows after / before current row
f             fill null cells from non-null cells above
```

## Data Analysis

**Aggregations:**
```
+             add aggregator to current column
z+            show aggregator result for selected rows
```

**Common aggregators:** min, max, avg, sum, median, mode, stdev, count, distinct, list

**Derived Sheets:**
```
Shift+F       Frequency table (group by current column)
gF            Frequency table by all key columns
Shift+I       Describe sheet (summary statistics)
Shift+W       Pivot table
Shift+M       Melt sheet (unpivot)
Shift+T       Transpose sheet
```

**Visualization:**
```
. (dot)       plot current numeric column vs key columns
g.            plot all numeric columns
```

## Metasheets

**Essential metasheets:**
```
Shift+S       Sheets sheet (navigate between sheets)
Shift+C       Columns sheet (edit column properties)
Shift+O       Options sheet (configure settings)
Shift+D       CommandLog (save/replay workflows)
^T            Threads sheet (view async operations)
^E            Error sheet (view errors)
```

## File Operations

**Opening:**
```
o filename    open file
zo            open file from current cell path
```

**Saving:**
```
^S filename   save current sheet (format by extension)
g^S filename  save all sheets
z^S filename  save current column only
```

**Supported formats:** tsv, csv, json, jsonl, xlsx, xls, sqlite, html, xml, yaml, parquet, and more

## Macros & Replay

**Recording:**
```
m keystroke   start/stop recording macro, bind to keystroke
gm            view all macros
```

**CommandLog:**
```
Shift+D       open CommandLog
^D filename   save CommandLog to .vdj file
```

**Replaying:**
```bash
vd --play script.vdj                     # Replay interactively
vd --play script.vdj -b -o output.tsv    # Replay in batch mode
vd --play script.vdj -w 1                # Wait 1 sec between commands
```

## JN Integration

### VisiData → JN Pipeline

**Explore with VisiData, then pipe to JN:**
```bash
# 1. Explore data interactively with VisiData
vd large_dataset.csv

# 2. After exploration, process with JN
vd -b large_dataset.csv -o - | jn cat - | jn filter '.amount > 1000' | jn put results.json
```

**Save filtered data and continue with JN:**
```bash
# In VisiData: select rows, then ^S selected.csv
# Then:
jn cat selected.csv | jn put results.json
```

### JN → VisiData Pipeline

**Preview JN output with VisiData:**
```bash
# Generate NDJSON with JN, convert to CSV for VisiData
jn cat data.csv | jn filter '.active' > /tmp/filtered.ndjson
vd /tmp/filtered.ndjson

# Or direct pipe (VisiData auto-detects NDJSON)
jn cat data.csv | jn filter '.active' | vd -f jsonl
```

### Round-trip Workflow

**1. Export from JN for visual exploration:**
```bash
jn cat api_data.json | jn put /tmp/explore.csv
vd /tmp/explore.csv
```

**2. Edit/filter in VisiData, save selection**
```
# In VisiData:
# - Select rows with 's'
# - Filter columns
# - ^S save to /tmp/cleaned.csv
```

**3. Continue with JN:**
```bash
jn cat /tmp/cleaned.csv | jn put final.json
```

### Create VisiData Plugin for JN

**Use VisiData from JN plugin:**
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.vd$"]
# ///

import subprocess
import json
import sys

def reads(config=None):
    """Launch VisiData, save selection as JSONL, yield records."""
    # This would require interactive VisiData session
    # Better to use VisiData separately, then process with JN
    pass

def writes(config=None):
    """Read NDJSON, write temp file, open in VisiData."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for line in sys.stdin:
            f.write(line)
        temp_path = f.name

    # Open in VisiData
    subprocess.run(['vd', temp_path])
```

## Common Workflows

### Data Exploration
```bash
# Quick exploration
vd data.csv

# Navigate with hjkl
# Press Shift+I for summary statistics
# Press Shift+F to see frequency distribution
# Press [ to sort by column
```

### Data Cleaning
```bash
# Open file
vd messy_data.csv

# 1. Fix column types: # % $ @
# 2. Filter bad rows: | regex, then gd to delete selected
# 3. Fill nulls: position on column, press f
# 4. Remove duplicates: set key columns with !, then Shift+F, then Enter
# 5. Save: ^S cleaned.csv
```

### Data Transformation
```bash
# Open source
vd input.csv

# 1. Create derived column: = expression
#    Example: =price * quantity
# 2. Rename columns: ^
# 3. Hide unnecessary columns: -
# 4. Reorder columns: H L
# 5. Save: ^S output.csv
```

### Format Conversion
```bash
# Simple conversion (batch mode)
vd -b input.xlsx -o output.csv

# Complex conversion with filtering
vd input.xlsx
# Select rows, filter columns
# ^S output.json
```

### Aggregation & Reporting
```bash
vd sales.csv

# 1. Set key column (e.g., 'region'): move to column, press !
# 2. Set aggregators on amount column: +, choose 'sum', 'avg', etc.
# 3. Create frequency table: Shift+F
# 4. Save report: ^S sales_by_region.csv
```

## Configuration

**Runtime options (Shift+O):**
```
csv-delimiter        Set CSV delimiter
default-width        Default column width
disp-date-fmt        Date format string
wrap                 Wrap text to window width
color-*              Color scheme options
```

**Config file (~/.visidatarc):**
```python
# Python configuration
options.min_memory_mb = 100
options.csv_delimiter = '|'
options.disp_date_fmt = '%Y-%m-%d'

# Custom keybinding
bindkey('0', 'go-leftmost')

# Custom aggregator
def median(values):
    L = sorted(values)
    return L[len(L)//2]
vd.aggregator('median', median)
```

## Troubleshooting

**File won't open:**
```bash
# Force format
vd -f csv data.txt
vd -f json data.log

# Specify delimiter
vd -d '|' data.psv

# Skip header rows
vd --skip 2 --header 1 data.csv
```

**Performance issues:**
```bash
# Limit rows loaded
vd --max-rows 10000 huge.csv

# Use streaming for very large files
vd -f jsonl huge.ndjson  # NDJSON streams better than JSON
```

**Memory errors:**
```
# Set minimum memory threshold
vd --min-memory-mb 500 data.csv
```

## Quick Reference Card

| Task | Command |
|------|---------|
| Open file | `vd file.csv` |
| Batch convert | `vd -b in.xlsx -o out.csv` |
| Navigate | `hjkl` or arrows |
| Search | `/` forward, `?` backward |
| Select rows | `s` select, `gs` all |
| Filter sheet | `"` (selected only) |
| Sort | `[` asc, `]` desc |
| Set type | `~#%$@` str/int/float/curr/date |
| Hide column | `-` |
| Key column | `!` |
| Edit cell | `e` |
| New column | `= expression` |
| Frequency | `Shift+F` |
| Statistics | `Shift+I` |
| Pivot | `Shift+W` |
| Save | `^S filename` |
| Quit | `q` sheet, `gq` all |

## Best Practices

**1. Always install via uv:**
```bash
uv tool install visidata
```

**2. Use batch mode for scripted conversions:**
```bash
vd -b input.csv -o output.json
```

**3. Save CommandLogs for reproducible workflows:**
```bash
# In VisiData: Shift+D, then ^S workflow.vdj
# Replay: vd --play workflow.vdj -b -o output.tsv
```

**4. Set column types early:**
- Improves sort accuracy
- Enables numeric aggregations
- Better visualizations

**5. Use key columns for grouping:**
```
! to set key, then Shift+F for frequency table
```

**6. Combine with JN for ETL pipelines:**
```bash
# Visual exploration
vd data.csv

# Automated processing
jn cat data.csv | jn filter '.verified' | jn put clean.json
```

**7. Use NDJSON for large datasets:**
```bash
# Better memory usage than JSON arrays
jn cat huge.csv | jn put huge.jsonl
vd -f jsonl huge.jsonl
```

## Advanced Features

**SQL-like joins:**
```
# 1. Open both sheets: vd file1.csv file2.csv
# 2. Go to Sheets sheet: Shift+S
# 3. Select both sheets: s on each
# 4. Join: & then choose join type (inner/outer/full)
```

**Python expressions:**
```
= price * 1.1                    # 10% markup
= date.year                      # Extract year
= row.first_name + ' ' + row.last_name  # Concatenate
```

**Graphing:**
```
# Set key column (x-axis): !
# Move to numeric column (y-axis)
# Press . to plot
# +/- to zoom, s to select points
```

**Command palette:**
```
Space          Open command palette
Tab            Cycle through commands
0-9            Execute numbered command
Enter          Execute highlighted command
```

## Resources

**Help:**
```
g^H            View man page
z^H            View commands for current sheet
Alt+H          Activate help menu
```

**Online:**
- Documentation: https://visidata.org/docs
- Formats: https://visidata.org/formats
- Cheatsheet: https://jsvine.github.io/visidata-cheat-sheet/en/

## Examples

**Example 1: Quick data inspection**
```bash
# Download and inspect API data
curl https://api.example.com/data | vd -f json
```

**Example 2: Sales report**
```bash
vd sales.csv
# Set 'region' as key: !
# On 'amount' column: + sum, + avg
# Frequency table: Shift+F
# Save: ^S sales_report.csv
```

**Example 3: CSV to SQLite**
```bash
vd -b data.csv -o data.sqlite
```

**Example 4: Filter and export for JN**
```bash
vd large_dataset.csv
# Select rows: | .*, s to select matches
# Save selected: ^S filtered.csv
# Process with JN:
jn cat filtered.csv | jn put results.json
```

**Example 5: Combine multiple files**
```bash
vd file1.csv file2.csv file3.csv
# Shift+S (Sheets sheet)
# Select all: gs
# Append: & append
# Save: ^S combined.csv
```
