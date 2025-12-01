---
name: visidata
description: Expert in VisiData terminal spreadsheet tool for exploring, cleaning, and transforming tabular data. Covers installation via uv, interactive data exploration via tmux, conversion between formats (CSV/JSON/Excel/SQLite), filtering, aggregations, and integration with JN pipelines. Use when working with data exploration, analysis, format conversion, or visual data inspection.
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

## Running VisiData Interactively

**CRITICAL: VisiData is an interactive TUI (Text User Interface) program. ALWAYS use tmux to run it programmatically.**

### Standard tmux Launch Pattern

```bash
# Setup tmux session for VisiData
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
SESSION=claude-visidata

# Start VisiData in tmux
tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "vd data.csv" Enter

# ALWAYS tell user how to monitor
echo "VisiData is running in tmux. Monitor with:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
echo ""
echo "Or capture current view:"
echo "  tmux -S \"$SOCKET\" capture-pane -p -J -t $SESSION:0.0 -S -200"

# Wait for VisiData to load
sleep 2

# Capture initial view
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -50

# Send commands to VisiData
# Example: Go to column 3, sort descending
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "zc 3" Enter
sleep 0.5
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "]" Enter

# Capture result
sleep 1
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -50

# Clean up when done
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "gq" Enter
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

### Why tmux is Required

VisiData requires a TTY (terminal) to run. When running programmatically:
- ❌ Direct `vd file.csv` hangs waiting for user input
- ❌ `vd file.csv < /dev/null` fails with no TTY
- ✅ tmux provides a virtual terminal for VisiData to run in
- ✅ tmux allows programmatic control via send-keys
- ✅ tmux allows capturing output via capture-pane

### Interactive Exploration Pattern

```bash
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
SESSION=claude-vd-explore

# Launch VisiData
tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "vd large_data.csv" Enter

echo "VisiData launched. Attach to explore interactively:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
echo ""
echo "Detach with: Ctrl+b d"
echo "Quit VisiData with: gq"
```

### Automated Analysis Pattern

```bash
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
SESSION=claude-vd-auto

# Start VisiData
tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "vd sales.csv" Enter
sleep 2

# Navigate to 'amount' column (example: column 5)
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "zc 5" Enter
sleep 0.5

# Set column type to currency
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "$" Enter
sleep 0.5

# Sort descending
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "]" Enter
sleep 1

# Open Describe sheet for statistics
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "I" Enter
sleep 1

# Capture the statistics view
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -50

# Save results
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "^S" Enter
sleep 0.5
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- "/tmp/analysis.csv"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

# Quit
sleep 1
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "gq" Enter

# Cleanup
tmux -S "$SOCKET" kill-session -t "$SESSION"

# Show results
cat /tmp/analysis.csv
```

### Sending VisiData Commands via tmux

**Common VisiData keystrokes to send:**

```bash
# Navigation
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "gg"        # Top of sheet
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "G"         # Bottom
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "gh"        # Leftmost column
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "gl"        # Rightmost column

# Column operations
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "!"         # Set as key column
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "#"         # Set type to int
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "%"         # Set type to float
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "-"         # Hide column

# Sorting
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "["         # Sort ascending
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "]"         # Sort descending

# Analysis
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "I"         # Describe (Shift+I)
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "F"         # Frequency (Shift+F)

# Save
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "^S"        # Save (Ctrl+S)
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- "filename.csv"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

# Quit
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "gq"        # Quit all
```

**Use `-l` flag for literal text (filenames, search terms):**
```bash
# Search for pattern
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "/"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- "search pattern"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter
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

**Batch mode (non-interactive, safe to run directly):**
```bash
# One-liner conversions - NO tmux needed for batch mode
vd -b input.csv -o output.json           # CSV → JSON
vd -b input.xlsx -o output.tsv           # Excel → TSV
vd -b data.fixed -o data.csv             # Fixed-width → CSV
vd --play script.vdj -b -o output.tsv    # Replay saved workflow
```

**Interactive mode (REQUIRES tmux):**
```bash
# ALWAYS use tmux for interactive VisiData
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"

tmux -S "$SOCKET" new -d -s claude-vd
tmux -S "$SOCKET" send-keys -t claude-vd:0.0 -- "vd data.csv" Enter

echo "Monitor with: tmux -S \"$SOCKET\" attach -t claude-vd"
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
c regex       go to column matching regex (searches column names)
```

**Navigate to specific columns (via tmux):**
```bash
# Search for column by name
tmux send-keys -t $PANE -- "c"
tmux send-keys -t $PANE -l -- "column_name"
tmux send-keys -t $PANE -- Enter

# Or jump to column number directly
tmux send-keys -t $PANE -l -- "zc 5"  # Column 5
tmux send-keys -t $PANE -- Enter
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

**Via tmux (to see full column content):**
```bash
# Navigate to column, then toggle width to see full content
tmux send-keys -t $PANE -- "c"           # Start column search
tmux send-keys -t $PANE -l -- "payload"  # Find "payload" column
tmux send-keys -t $PANE -- Enter
tmux send-keys -t $PANE -- "_"           # Toggle to full width
```

**Key Columns:**
```
!             toggle current column as key column
z!            unset current column as key
```

**Viewing & Editing:**
```
Enter         open/expand current row (vertical view)
q             go back to previous sheet
^             rename current column
e text        edit current cell
ge text       set current column for selected rows
= expr        create new column from Python expression
g= expr       set current column for selected rows
i             add column with incremental values
```

**Via tmux (open last row for inspection):**
```bash
# Go to bottom and open last row
tmux send-keys -t $PANE -- "G"      # Go to bottom
tmux send-keys -t $PANE -- Enter    # Open row details
sleep 1
tmux capture-pane -p -J -t $PANE -S -30  # View details

# Go back to main sheet
tmux send-keys -t $PANE -- "q"
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

### Interactive Workflow: tmux + VisiData + JN

**Pattern: Explore with VisiData, process with JN**

```bash
# 1. Export JN data for exploration
jn cat api_data.json | jn put /tmp/explore.csv

# 2. Launch VisiData in tmux
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
SESSION=claude-vd-jn

tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "vd /tmp/explore.csv" Enter

echo "Explore data in VisiData:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
echo ""
echo "When done exploring:"
echo "  1. Select rows you want (s key)"
echo "  2. Save with ^S → /tmp/selected.csv"
echo "  3. Detach with Ctrl+b d"

# 3. After user explores and saves, process with JN
# (Run this after user detaches)
jn cat /tmp/selected.csv | jn put final.json

# 4. Cleanup
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

## Common Workflows

### Data Exploration (via tmux)
```bash
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
SESSION=claude-vd-explore

# Launch VisiData
tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "vd data.csv" Enter
sleep 2

echo "VisiData running. Attach to explore:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
echo ""
echo "Quick commands:"
echo "  hjkl - navigate"
echo "  I - statistics (Shift+I)"
echo "  F - frequency (Shift+F)"
echo "  [ ] - sort"
echo "  gq - quit"
```

### Data Cleaning (via tmux)
```bash
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
SESSION=claude-vd-clean

tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "vd messy_data.csv" Enter
sleep 2

# Example: Set column 3 to float type, sort descending
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "zc 3" Enter
sleep 0.5
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "%" Enter  # Float type
sleep 0.5
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "]" Enter  # Sort desc

echo "Data cleaning in progress. Monitor:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
echo ""
echo "Or capture current state:"
echo "  tmux -S \"$SOCKET\" capture-pane -p -J -t $SESSION:0.0 -S -50"
```

### Data Transformation (via tmux)
```bash
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
SESSION=claude-vd-transform

tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "vd input.csv" Enter
sleep 2

echo "VisiData loaded. Attach to transform:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
echo ""
echo "Common transforms:"
echo "  = expression - create derived column"
echo "  ^ - rename column"
echo "  - - hide column"
echo "  H L - move column"
echo "  ^S - save result"
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

**2. ALWAYS use tmux for interactive VisiData:**
```bash
# ✅ Correct - use tmux
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
tmux -S "$SOCKET" new -d -s claude-vd
tmux -S "$SOCKET" send-keys -t claude-vd:0.0 -- "vd data.csv" Enter

# ❌ Wrong - direct call hangs
vd data.csv  # This hangs when run programmatically!
```

**3. Use batch mode for non-interactive conversions:**
```bash
# Batch mode doesn't need tmux
vd -b input.csv -o output.json
```

**4. Save CommandLogs for reproducible workflows:**
```bash
# In VisiData: Shift+D, then ^S workflow.vdj
# Replay in batch mode (no tmux needed):
vd --play workflow.vdj -b -o output.tsv
```

**5. Set column types early:**
- Improves sort accuracy
- Enables numeric aggregations
- Better visualizations

**6. Use key columns for grouping:**
```
! to set key, then Shift+F for frequency table
```

**7. Combine with JN for ETL pipelines:**
```bash
# Visual exploration (with tmux)
jn cat data.csv | jn put /tmp/explore.csv
# Then launch VisiData in tmux (see patterns above)

# Automated processing (no tmux)
jn cat data.csv | jn filter '.verified' | jn put clean.json
```

**8. Use NDJSON for large datasets:**
```bash
# Better memory usage than JSON arrays
jn cat huge.csv | jn put huge.jsonl
vd -f jsonl huge.jsonl  # Remember: use tmux if interactive!
```

**9. Always tell user how to monitor:**
```bash
# After starting tmux session, ALWAYS print:
echo "Monitor with: tmux -S \"$SOCKET\" attach -t $SESSION"
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

**Example 2: Sales report (via tmux)**
```bash
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
SESSION=claude-vd-sales

tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "vd sales.csv" Enter
sleep 2

# Navigate to 'region' column (example: column 2)
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "zc 2" Enter
sleep 0.5

# Set as key column
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "!" Enter
sleep 0.5

# Navigate to 'amount' column (example: column 5)
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "zc 5" Enter
sleep 0.5

# Open Frequency table (Shift+F)
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "F" Enter
sleep 1

# Capture the report
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -50

# Save
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "^S" Enter
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -l -- "sales_report.csv"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- Enter

echo "Report saved. Attach to view:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
```

**Example 3: CSV to SQLite**
```bash
vd -b data.csv -o data.sqlite
```

**Example 4: Filter and export for JN (via tmux)**
```bash
SOCKET_DIR=${TMPDIR:-/tmp}/claude-tmux-sockets
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/claude.sock"
SESSION=claude-vd-filter

tmux -S "$SOCKET" new -d -s "$SESSION"
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "vd large_dataset.csv" Enter
sleep 2

echo "VisiData launched. Attach to filter data:"
echo "  tmux -S \"$SOCKET\" attach -t $SESSION"
echo ""
echo "Filter workflow:"
echo "  1. Use | to select rows by regex"
echo "  2. Press s to select matching rows"
echo "  3. Press ^S to save selected rows"
echo "  4. Enter filename: filtered.csv"
echo "  5. Detach with Ctrl+b d"
echo ""
echo "After filtering, process with JN:"
echo "  jn cat filtered.csv | jn put results.json"
```

**Example 5: Combine multiple files**
```bash
vd file1.csv file2.csv file3.csv
# Shift+S (Sheets sheet)
# Select all: gs
# Append: & append
# Save: ^S combined.csv
```
