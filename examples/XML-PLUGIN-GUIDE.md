# JN XML Plugin Guide

The XML plugin provides comprehensive support for reading and writing XML files with JN pipelines.

## Reading XML (4 modes)

### 1. Flatten Mode (default)
**Use case:** Process each XML element independently

Each XML element becomes a separate NDJSON record with its path, tag, attributes, and text.

```bash
jn cat books-simple.xml
# Output: One record per element (catalog, book, title, author, etc.)
```

**Example output:**
```json
{"path": "catalog/book", "tag": "book", "id": "1", "_attributes": {"id": "1"}, "_children_count": 4}
{"path": "catalog/book/title", "tag": "title", "text": "The Great Gatsby"}
{"path": "catalog/book/author", "tag": "author", "text": "F. Scott Fitzgerald"}
```

**When to use:**
- Extract specific elements across the document
- Process elements independently
- Search for specific tags or attributes

### 2. Tree Mode
**Use case:** Preserve full XML structure

The entire XML document is represented as a single nested record.

```bash
python jn_home/plugins/formats/xml_.py --mode read --parse-mode tree < users-flat.xml
```

**Example output:**
```json
{
  "_tag": "users",
  "_children": {
    "user": [
      {
        "_tag": "user",
        "_attributes": {"id": "1", "email": "alice@example.com"},
        "_children": {
          "username": {"_tag": "username", "_text": "alice"},
          "age": {"_tag": "age", "_text": "30"}
        }
      }
    ]
  }
}
```

**When to use:**
- Need complete document structure
- Round-trip XML (read and write back)
- Navigate relationships between elements

### 3. Coverage Mode
**Use case:** Specialized for coverage.xml files

Extracts line-level coverage data with full context (filename, line numbers, hits, branches).

```bash
python jn_home/plugins/formats/xml_.py --mode read --parse-mode coverage < coverage.xml
```

**Example output:**
```json
{
  "package": ".",
  "filename": "filtering.py",
  "class": "filtering.py",
  "file_line_rate": 0.8276,
  "file_branch_rate": 0.7955,
  "line_number": 66,
  "hits": 0,
  "branch": true,
  "condition_coverage": "0% (0/2)",
  "missing_branches": "67,69"
}
```

**When to use:**
- Analyzing pytest/coverage.py XML reports
- Finding uncovered lines
- Reporting on branch coverage

### 4. XMLtodict Mode
**Use case:** Using xmltodict library for intuitive representation

Requires the `xmltodict` package to be installed.

```bash
python jn_home/plugins/formats/xml_.py --mode read --parse-mode xmltodict < file.xml
```

## Writing XML (3 modes)

### 1. Records Mode (default)
**Use case:** Convert each NDJSON record to an XML element

Each record becomes a child element with fields as sub-elements.

```bash
jn cat products.json | jn put output.xml
```

**Input (NDJSON):**
```json
{"id": 1, "name": "Laptop", "price": 999.99}
{"id": 2, "name": "Chair", "price": 199.99}
```

**Output (XML):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <item>
    <id>1</id>
    <name>Laptop</name>
    <price>999.99</price>
  </item>
  <item>
    <id>2</id>
    <name>Chair</name>
    <price>199.99</price>
  </item>
</root>
```

**Customize tags:**
```bash
jn cat products.json | python jn_home/plugins/formats/xml_.py \
  --mode write --write-mode records \
  --root-tag catalog --item-tag product
```

### 2. Tree Mode
**Use case:** Preserve complex XML structure from tree mode reads

Converts structured records (with `_tag`, `_attributes`, `_children`) back to XML.

```bash
# Perfect round-trip
python jn_home/plugins/formats/xml_.py --mode read --parse-mode tree < input.xml | \
python jn_home/plugins/formats/xml_.py --mode write --write-mode tree > output.xml
```

**When to use:**
- Round-trip XML transformations
- Preserve exact structure and attributes
- Work with nested hierarchies

### 3. Raw Mode
**Use case:** Records contain XML structure information

Handles records that have `tag` or `_tag` fields specifying element names.

```bash
# Input has tag information
echo '{"tag": "person", "_attributes": {"id": "1"}, "name": "Alice"}' | \
python jn_home/plugins/formats/xml_.py --mode write --write-mode raw
```

## Common Patterns

### Pattern 1: Extract data from XML to CSV
```bash
jn cat books-simple.xml | \
jn filter 'select(.tag == "book") | {id: ._attributes.id}' | \
jn put books.csv
```

### Pattern 2: Filter and write back to XML
```bash
jn cat users-flat.xml | \
jn filter 'select(.tag == "user" and ._attributes.active == "true")' | \
jn put active-users.xml
```

### Pattern 3: Transform JSON to XML
```bash
jn cat data.json | \
jn filter '{name, email, age}' | \
jn put users.xml
```

### Pattern 4: Round-trip with transformation
```bash
# Read XML, transform, write back
python jn_home/plugins/formats/xml_.py --mode read --parse-mode tree < input.xml | \
jn filter '._children.users._children.user |= map(select(._attributes.active == "true"))' | \
python jn_home/plugins/formats/xml_.py --mode write --write-mode tree > filtered.xml
```

### Pattern 5: Extract specific elements
```bash
# Get all book titles
jn cat books-simple.xml | \
jn filter 'select(.tag == "title")' | \
jn filter '{title: .text}'
```

### Pattern 6: Analyze coverage data
```bash
# Find files with lowest coverage
python jn_home/plugins/formats/xml_.py --mode read --parse-mode coverage < coverage.xml | \
jn filter 'group_by(.filename) | map({file: .[0].filename, uncovered: length})' | \
jn filter 'sort_by(.uncovered) | reverse | .[0:10]'
```

## Command-Line Options

### Read Mode
```bash
python jn_home/plugins/formats/xml_.py --mode read \
  --parse-mode {flatten|tree|xmltodict|coverage}
```

### Write Mode
```bash
python jn_home/plugins/formats/xml_.py --mode write \
  --write-mode {records|tree|raw} \
  --root-tag <tag> \
  --item-tag <tag> \
  --indent
```

## Field Conventions

The plugin uses these special field names:

- `_tag` - Element tag name
- `_attributes` - Element attributes (dict)
- `_text` - Text content of element
- `_children` - Child elements (dict or list)
- `_children_count` - Number of child elements
- `tag` - Alternative to `_tag` (for user data)
- `text` - Alternative to `_text` (for user data)
- `path` - Full path to element (flatten mode only)

## Examples Files

This directory contains sample XML files:

- `books-simple.xml` - Simple catalog structure
- `company-nested.xml` - Complex nested departments/employees
- `users-flat.xml` - Flat list of users with attributes
- `products.json` - Sample JSON for conversion to XML

## Tips

1. **Use tree mode for round-trips** - It preserves exact structure including attributes
2. **Use flatten mode for search** - Easier to filter specific elements
3. **Customize root/item tags** - Make output more semantic with `--root-tag` and `--item-tag`
4. **Coverage mode is specialized** - Only works with Cobertura coverage.xml format
5. **Attributes vs Elements** - Records mode converts fields to child elements; use tree mode to preserve attributes

## Integration with JN

The XML plugin is automatically detected by JN based on file extension:

```bash
jn cat file.xml        # Uses XML plugin automatically
jn put output.xml      # Uses XML plugin for writing
jn cat data.csv | jn put output.xml  # CSV to XML conversion
```

For fine-grained control, call the plugin directly with custom options.
