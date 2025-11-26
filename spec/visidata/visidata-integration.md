# VisiData Integration

## Overview

JN integrates with [VisiData](https://www.visidata.org/) to provide powerful interactive data exploration. VisiData is a terminal spreadsheet that supports sorting, filtering, aggregation, frequency tables, and much more.

## Installation

VisiData is not bundled with JN. Install it separately:

```bash
uv tool install visidata
```

## Usage

### Basic Pipeline

```bash
# Pipe NDJSON to VisiData
jn cat data.csv | jn vd

# Open source directly
jn vd data.json
jn vd https://api.com/data~json

# With pre-filtering
jn vd data.csv --filter '.age > 30'
```

### Real-World Examples

```bash
# Explore human gene data from NCBI
jn head -n 1000 "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz" | jn vd

# Analyze API response
jn cat https://api.github.com/users/octocat/repos~json | jn vd

# Filter and explore large datasets
jn cat huge_dataset.csv | jn filter '.revenue > 10000' | jn vd
```

## VisiData Quick Reference

Once in VisiData:

| Key | Action |
|-----|--------|
| `q` | Quit |
| `j/k` | Move down/up |
| `h/l` | Move left/right |
| `/` | Search |
| `[` | Sort ascending |
| `]` | Sort descending |
| `Shift+F` | Frequency table for column |
| `.` | Select row |
| `g.` | Select all matching rows |
| `"` | Open selected rows as new sheet |
| `Ctrl+H` | Help |

Full documentation: https://www.visidata.org/man/

## Why VisiData?

VisiData provides capabilities beyond what a simple viewer can offer:

1. **Sorting & Filtering** - Sort by any column, filter rows with expressions
2. **Aggregation** - Group data, compute statistics
3. **Frequency Tables** - Quickly see value distributions
4. **Multi-sheet** - Open filtered subsets as new sheets
5. **Export** - Save to various formats (CSV, JSON, etc.)
6. **Memory Efficient** - Handles large datasets

## Comparison with `jn view`

| Feature | `jn view` | `jn vd` |
|---------|-----------|---------|
| Record-by-record viewing | Yes | No (tabular) |
| Tree view for nested JSON | Yes | Limited |
| Sorting | No | Yes |
| Filtering (in-UI) | Limited | Full |
| Aggregation | No | Yes |
| Frequency tables | No | Yes |
| Multi-sheet navigation | No | Yes |
| Export to formats | No | Yes |
| External dependency | No | Yes (VisiData) |

**Recommendation**: Use `jn vd` for exploring tabular data. Use `jn view` for deeply nested JSON where tree navigation is important.

## Licensing

VisiData is licensed under GPLv3. JN is MIT licensed.

This integration is safe because:
- JN pipes data to VisiData (inter-process communication)
- No VisiData code is embedded in JN
- Users install VisiData separately by choice
- The GPL does not spread through stdin/stdout pipes

## Architecture

```
jn cat source.csv  -->  jn filter '.x > 10'  -->  jn vd
       |                       |                    |
   [NDJSON]               [NDJSON]             [VisiData TUI]
```

The `jn vd` command:
1. Checks if VisiData is installed
2. Optionally reads from a source (like `jn cat`)
3. Optionally filters data (like `jn filter`)
4. Pipes NDJSON to VisiData via stdin
5. VisiData renders the data interactively
