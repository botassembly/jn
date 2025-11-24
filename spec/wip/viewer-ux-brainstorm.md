# JSON Viewer UX Brainstorming

Based on hands-on exploration of the viewer with the NCBI gene database.

## Known Issues (Observed)

1. **Quote Escaping Bug in FindByFieldDialog**: User reported `Symbol = "BRAF"` produces `.Symbol == ""BRAF""` (double-double quotes). The `_convert_to_jq` method adds extra quotes around already-quoted strings.

2. **BrokenPipeError on Invalid jq**: Fixed in this PR, but user hit it before the fix was deployed.

## What Works Well

- **Tree navigation** is intuitive (j/k, expand/collapse)
- **Record navigation** (n/p) feels natural
- **Search with Python filters** is now instant (was hanging before fix)
- **Bookmarks** are useful for comparing records
- **Subtitle shows context** - record position, search status, bookmarks
- **Help screen** is comprehensive

## UX Pain Points

### 1. No Quick Field Summary
With 16 columns, you have to scroll to see what fields exist. Wish there was a way to:
- Toggle between "full record" and "summary view" (show only key fields)
- See field list/schema at a glance
- Auto-detect and highlight "interesting" fields (IDs, names, status)

### 2. Search Could Show Preview
When you search, it just jumps to the first match. Would be nice to:
- Show a list of all matches with previews (like grep output)
- See how many matches per value (faceted search)
- Quick peek at match distribution across records

### 3. No Field-Level Filtering in View
The current search is per-record. What if you want to:
- Hide certain columns (like "Other_designations" which is always long)
- Reorder fields (put Symbol, GeneID first)
- Pin important fields to always show at top

### 4. Long Values Are Truncated
The viewer truncates strings at 100 chars. Would be nice to:
- Click/Enter on a field to see full value in a popup
- Copy single field value (not whole record)
- Word-wrap option for long text

### 5. No Cross-Record Comparison
Bookmarks let you mark records, but you can't:
- View two records side-by-side
- Diff two records to see differences
- Select multiple records for batch export

### 6. No Integration with jn inspect
The `jn inspect` command shows great faceted data (chromosome distribution, gene types). Would be cool to:
- Launch facet view from within viewer
- Click on facet value to filter to those records
- See statistics inline (count of each chromosome)

### 7. No Text Search (Substring Match)
Python filter requires exact match. Common use case:
- "Find all genes with 'kinase' in description"
- "Find symbols containing 'ACT'"
- Fuzzy matching for typos

## Feature Ideas

### Tier 1: High Impact, Feasible

1. **Field Value Popup** (`Enter` on field to see full value)
2. **Substring Search** (add `contains` pattern to Python filter)
3. **Fix Quote Escaping** in FindByFieldDialog
4. **Summary/Compact View** toggle (show only first 5 fields)

### Tier 2: Medium Complexity

5. **Match List View** (show all matches as selectable list)
6. **Field Reordering** (config to specify field order)
7. **Column Visibility** (hide/show specific fields)
8. **Copy Single Field** (y on highlighted field copies that value)

### Tier 3: Advanced

9. **Side-by-Side Compare** (split view for 2 records)
10. **Faceted Navigation** (show counts, click to filter)
11. **Integration with jn inspect** (launch stats view)
12. **Fuzzy Search** (Levenshtein distance matching)

## Design Principles

1. **Don't break streaming** - Viewer should work with 70k records without loading all into memory for features
2. **Keyboard-first** - All features accessible via keyboard shortcuts
3. **Progressive disclosure** - Simple by default, power features discoverable
4. **JN philosophy** - Viewer is for exploration, heavy transforms go back to pipeline

## Questions to Consider

- Should viewer support editing? (Currently read-only, probably good)
- Should viewer have export formats? (Currently just JSON, maybe add CSV?)
- Should search persist across sessions? (History of searches)
- Should bookmarks be saveable? (Export/import bookmark sets)
