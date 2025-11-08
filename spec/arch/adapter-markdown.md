# Markdown Source/Target Adapter

## Overview

Markdown adapter for parsing and generating Markdown documents with Front Matter support. Designed as the foundational document adapter for JN, with clean block-level structure suitable for both source extraction and target generation.

## Supported Formats

- **.md, .markdown** - Standard Markdown files
- **Front Matter** - YAML or TOML metadata blocks at file start

## Design Philosophy

**Markdown is the lingua franca**: This is the primary document format for documentation, content pipelines, and knowledge bases. Getting this right enables HTML, documentation sites, and content transformation workflows.

**Block-level parsing**: Focus on structural blocks (headings, paragraphs, lists, tables, code) rather than inline formatting. Inline markup (bold, italic, links) is captured but not decomposed by default.

**Streaming-friendly**: Emit blocks as they're parsed without buffering entire document.

## Libraries

### Reading
- **markdown-it-py** - Pure Python Markdown parser, CommonMark compliant, extensible, supports plugins
- **python-frontmatter** - Clean YAML/TOML front matter extraction

### Writing
- **Direct string construction** - Markdown is simple enough to generate without a library

**Why markdown-it-py?**
- Proper token streaming (unlike markdown → HTML parsers)
- Extensible with plugins (tables, strikethrough, task lists)
- Active maintenance
- CommonMark compliant

## Source Adapter: Markdown → NDJSON

### Record Structure

**Front Matter** (first record, if present):
```json
{
  "_kind": "frontmatter",
  "title": "My Document",
  "date": "2025-01-15",
  "tags": ["tutorial", "python"],
  "author": "Alice"
}
```

**Heading**:
```json
{
  "_kind": "heading",
  "level": 1,
  "text": "Introduction",
  "id": "introduction",
  "line": 5
}
```

**Paragraph**:
```json
{
  "_kind": "paragraph",
  "text": "This is a paragraph with **bold** and *italic* text.",
  "line": 7
}
```

**List** (flat):
```json
{
  "_kind": "list",
  "type": "bullet",
  "items": [
    "First item",
    "Second item",
    "Third item"
  ],
  "line": 10
}
```

**List** (nested, with `--expand-lists`):
```json
{"_kind": "list_item", "type": "bullet", "level": 1, "text": "First item", "line": 10}
{"_kind": "list_item", "type": "bullet", "level": 2, "text": "Nested item", "line": 11}
{"_kind": "list_item", "type": "bullet", "level": 1, "text": "Second item", "line": 12}
```

**Code Block**:
```json
{
  "_kind": "code",
  "language": "python",
  "text": "def hello():\n    print('Hello')",
  "line": 15
}
```

**Table**:
```json
{
  "_kind": "table",
  "headers": ["Name", "Age", "City"],
  "rows": [
    ["Alice", "30", "NYC"],
    ["Bob", "25", "SF"]
  ],
  "line": 20
}
```

**Blockquote**:
```json
{
  "_kind": "blockquote",
  "text": "This is a quote.\nIt can span multiple lines.",
  "line": 25
}
```

**Horizontal Rule**:
```json
{
  "_kind": "hr",
  "line": 30
}
```

**Link (with `--extract-links`)**:
```json
{
  "_kind": "link",
  "text": "Click here",
  "url": "https://example.com",
  "title": "Example site",
  "line": 35
}
```

**Image (with `--extract-images`)**:
```json
{
  "_kind": "image",
  "alt": "Diagram",
  "url": "./images/diagram.png",
  "title": "Architecture diagram",
  "line": 40
}
```

### CLI Options

```bash
# Basic usage
jn cat document.md                   # All blocks with default options

# Front Matter
jn cat document.md --no-frontmatter  # Skip front matter block
jn cat document.md --frontmatter-only # Only emit front matter, skip content

# Structure options
jn cat document.md --expand-lists    # Emit list_item records instead of list
jn cat document.md --expand-tables   # Emit table_row records instead of table
jn cat document.md --headings-only   # Only emit headings (document outline)

# Content extraction
jn cat document.md --extract-links   # Emit link records for all links
jn cat document.md --extract-images  # Emit image records for all images
jn cat document.md --code-blocks-only # Only emit code blocks

# Inline formatting
jn cat document.md --strip-formatting # Remove **bold**, *italic*, etc. from text
jn cat document.md --inline-markup   # Parse inline markup into structured format

# Filtering
jn cat document.md --min-heading 2   # Only headings level 2 and below (##, ###)
jn cat document.md --sections "API Reference" # Only content under this heading
```

### Streaming Strategy

```python
from markdown_it import MarkdownIt
import frontmatter

# Parse front matter first
with open(filename) as f:
    post = frontmatter.load(f)

# Emit front matter
if post.metadata:
    yield {"_kind": "frontmatter", **post.metadata}

# Parse Markdown content
md = MarkdownIt()
tokens = md.parse(post.content)

# Stream blocks
for token in tokens:
    if token.type == 'heading_open':
        # Emit heading record
        yield heading_record
    elif token.type == 'paragraph_open':
        # Emit paragraph record
        yield paragraph_record
    # ... etc
```

**Benefits**:
- True streaming - emit blocks as parsed
- Low memory footprint
- Can process very large documents (e.g., concatenated docs)

### Front Matter Formats

**YAML** (most common):
```markdown
---
title: My Document
date: 2025-01-15
tags:
  - tutorial
  - python
---

# Content starts here
```

**TOML**:
```markdown
+++
title = "My Document"
date = 2025-01-15
tags = ["tutorial", "python"]
+++

# Content starts here
```

**Auto-detection**: python-frontmatter handles both formats automatically.

### Inline Markup Handling

**Default** (preserve raw Markdown):
```json
{"_kind": "paragraph", "text": "This is **bold** and *italic*."}
```

**With `--strip-formatting`**:
```json
{"_kind": "paragraph", "text": "This is bold and italic."}
```

**With `--inline-markup`** (advanced):
```json
{
  "_kind": "paragraph",
  "text": "This is bold and italic.",
  "markup": [
    {"type": "strong", "start": 8, "end": 12, "text": "bold"},
    {"type": "em", "start": 17, "end": 23, "text": "italic"}
  ]
}
```

**Use case**: Most pipelines don't need inline markup. Default preserves it as-is for reconstruction.

### Edge Cases

**Nested lists**:
- Default: Flatten to single list record with indentation in text
- `--expand-lists`: Emit list_item records with level

**Tables without headers**:
- First row becomes headers
- Add `--no-table-headers` to treat first row as data

**Mixed list types** (bullets + numbers):
- Emit separate list records
- Preserve type (bullet vs ordered)

**HTML blocks in Markdown**:
- Emit as `{"_kind": "html", "text": "<div>...</div>"}`
- Or skip with `--skip-html`

**GFM Extensions** (GitHub Flavored Markdown):
- Task lists: `- [ ] Todo` → `{"_kind": "task", "checked": false, "text": "Todo"}`
- Strikethrough: `~~text~~` → preserved in text by default
- Emoji: `:smile:` → preserved as-is (or expand with `--expand-emoji`)

**Malformed Markdown**:
- markdown-it-py is forgiving - parses best-effort
- Invalid tables → emit as paragraph or skip

### Example Workflows

**Extract document outline**:
```bash
jn cat README.md --headings-only | jq -r '"\(.level) \(.text)"'
```

**Get all code blocks**:
```bash
jn cat tutorial.md --code-blocks-only | jq -r '.text'
```

**Extract front matter metadata**:
```bash
jn cat *.md --frontmatter-only | jq -s 'map({file: input_filename, title, date})'
```

**Convert tables to CSV**:
```bash
jn cat doc.md | jq -r 'select(._kind == "table") | .rows[] | @csv'
```

**Build search index**:
```bash
jn cat docs/**/*.md | jq 'select(._kind == "paragraph" or ._kind == "heading")'
```

**Extract all links**:
```bash
jn cat page.md --extract-links | jq -r '.url'
```

## Target Adapter: NDJSON → Markdown

### Input Requirements

NDJSON records with `_kind` field:
```json
{"_kind": "frontmatter", "title": "My Doc", "date": "2025-01-15"}
{"_kind": "heading", "level": 1, "text": "Introduction"}
{"_kind": "paragraph", "text": "This is a paragraph."}
```

### CLI Options

```bash
# Basic usage
jn cat data.json | jn put output.md

# Options
jn put output.md \
  --frontmatter-format yaml \      # or 'toml', default: yaml
  --heading-style atx \             # or 'setext', default: atx (##)
  --list-marker "-" \               # or '*', '+', default: -
  --line-width 80 \                 # Wrap paragraphs at N chars (0 = no wrap)
  --overwrite                       # Overwrite existing file

# Force format if extension is ambiguous
jn put output.txt --format markdown  # Write Markdown to .txt file
```

### Writing Strategy

**Stream directly to file**:
```python
def write_markdown(records, output):
    for record in records:
        if record["_kind"] == "frontmatter":
            output.write("---\n")
            output.write(yaml.dump(record))
            output.write("---\n\n")

        elif record["_kind"] == "heading":
            level = record["level"]
            text = record["text"]
            output.write(f"{'#' * level} {text}\n\n")

        elif record["_kind"] == "paragraph":
            text = record["text"]
            output.write(f"{text}\n\n")

        # ... etc
```

**No buffering needed**: Can write line-by-line as records arrive.

### Record Type Handling

**Front Matter**:
- Must be first record
- All fields except `_kind` → YAML/TOML
- Emits `---` delimiters

**Heading**:
- Requires: `level` (1-6), `text`
- ATX style: `## Heading`
- Setext style (levels 1-2 only): `Heading\n=======`

**Paragraph**:
- Requires: `text`
- Wraps at `--line-width` if specified
- Preserves inline Markdown markup

**List**:
- Requires: `items` (array)
- Optional: `type` (bullet or ordered)
- Emits with specified marker (`-`, `*`, `+`) or numbers

**List Item** (from `--expand-lists`):
- Requires: `level`, `text`
- Reconstructs nested list from levels

**Code Block**:
- Requires: `text`
- Optional: `language`
- Emits fenced code block: ` ```language`

**Table**:
- Requires: `headers`, `rows`
- Emits GFM table with alignment
- Auto-sizes columns

**Blockquote**:
- Requires: `text`
- Emits with `> ` prefix

**Horizontal Rule**:
- Emits `---` or `***`

**Link** (if using `--extract-links` in reverse):
- Not typically used - links are inline
- Could emit as paragraph with link

**Image**:
- Requires: `url`, `alt`
- Emits: `![alt](url "title")`

### Edge Cases

**Missing fields**:
- Heading without level → default to level 1
- Code without language → emit without language tag
- Table with mismatched row lengths → pad with empty cells

**Invalid level values**:
- Level > 6 → clamp to 6
- Level < 1 → clamp to 1

**Special characters**:
- Escape: `#` at line start (unless heading)
- Escape: `|` in table cells
- No escaping needed for most inline content

**Reconstructing nested lists**:
- If `list_item` records have `level`, indent appropriately
- Requires sorting by line number to maintain order
- Switch between bullet/numbered based on `type`

**Front Matter in middle of stream**:
- Error or warning - front matter must be first
- Alternative: treat as YAML code block

**Empty text fields**:
- Paragraph with empty text → emit blank line
- Heading with empty text → skip or error

### Example Workflows

**JSON data → Markdown report**:
```bash
jn cat users.json | jq '{_kind: "paragraph", text: "\(.name) - \(.email)"}' | jn put report.md
```

**Build README from structured data**:
```bash
cat <<EOF | jn put README.md
{"_kind": "frontmatter", "title": "My Project"}
{"_kind": "heading", "level": 1, "text": "Overview"}
{"_kind": "paragraph", "text": "This is my project."}
EOF
```

**Convert CSV to Markdown table**:
```bash
jn cat data.csv | jq -s '{_kind: "table", headers: (.[0] | keys), rows: map([.name, .age, .city])}' | jn put table.md
```

**Round-trip conversion**:
```bash
jn cat input.md | jn put output.md
# Should preserve structure (not necessarily formatting)
```

## Implementation Notes

### Parser Registration

**Not a JC parser**: Markdown is too complex. Implement as native adapter.

### File Structure

```
src/jn/adapters/
  markdown.py          # Main adapter logic
  markdown_reader.py   # Streaming parser using markdown-it-py
  markdown_writer.py   # Streaming writer
```

### Auto-Detection

In `src/jn/cli/cat.py`, extend `_detect_file_parser()`:

```python
parser_map = {
    ".csv": "csv_s",
    ".tsv": "tsv_s",
    ".psv": "psv_s",
    ".xlsx": "excel",
    ".xls": "excel",
    ".md": "markdown",      # New
    ".markdown": "markdown", # New
}
```

### Testing Strategy

**Unit tests**:
- Front matter parsing (YAML, TOML)
- Each block type (heading, paragraph, list, etc.)
- Inline markup handling
- Edge cases (empty fields, invalid levels)

**Integration tests**:
- Full documents with mixed content
- Round-trip: MD → NDJSON → MD
- GFM extensions (tables, task lists)

**Golden stream tests**:
```
test-fixtures/markdown/
  simple.md → simple.ndjson (expected output)
  frontmatter.md → frontmatter.ndjson
  complex.md → complex.ndjson (nested lists, tables, code)
```

**Comparison strategy**:
- Parse both as JSON and compare structures
- Ignore line numbers (they may shift)
- Normalize whitespace in text fields

### Error Handling

```python
try:
    post = frontmatter.load(f)
except frontmatter.YAMLError as e:
    raise JnError("markdown", filename, "Invalid front matter YAML")
```

**Specific errors**:
- File not found
- Invalid UTF-8 encoding
- Malformed front matter
- markdown-it-py parse errors (rare - it's forgiving)

## Performance Characteristics

**Reading**:
- True streaming - processes blocks as parsed
- Memory: ~10MB for any document size
- Speed: ~1MB/sec (~10K paragraphs/sec)

**Writing**:
- Stream directly to file
- No buffering needed
- Speed: ~5MB/sec

## GFM (GitHub Flavored Markdown) Support

**Extensions to enable**:
- Tables (most important)
- Strikethrough (`~~text~~`)
- Task lists (`- [ ] Todo`)
- Autolinks (URLs without `<>`)

**Using markdown-it-py plugins**:
```python
from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.footnote import footnote_plugin

md = MarkdownIt().enable('table').enable('strikethrough')
```

**Task List Record**:
```json
{
  "_kind": "task",
  "checked": false,
  "text": "Complete the tutorial",
  "line": 15
}
```

## Future Enhancements

**Phase 2 features**:
- Full inline markup parsing (bold, italic, code spans)
- Footnote extraction
- Definition list support
- Math blocks (LaTeX)
- Mermaid diagram detection
- Obsidian wiki-link support (`[[page]]`)

**Advanced front matter**:
- JSON front matter (rare but exists)
- Multiple front matter blocks (not standard)
- Front matter validation against schema

**Target adapter enhancements**:
- Smart wrapping (respect sentence boundaries)
- Table column auto-alignment (left, center, right)
- Preserve original formatting hints
- Syntax highlighting in code blocks (via Pygments)

## Use Cases

### Documentation Pipelines
```bash
# Extract all code examples from docs
jn cat docs/**/*.md --code-blocks-only > examples.ndjson

# Build navigation from headings
jn cat docs/**/*.md --headings-only | jq '{file: input_filename, title: .text, level}'
```

### Content Management
```bash
# Extract metadata from blog posts
jn cat posts/*.md --frontmatter-only | jq -s 'sort_by(.date) | reverse'

# Generate RSS feed from Markdown posts
jn cat posts/*.md | jq '...' | jn put feed.xml --format rss
```

### Knowledge Base
```bash
# Build search index
jn cat knowledge/**/*.md | jq 'select(._kind == "paragraph")' | elasticsearch-bulk

# Extract all internal links
jn cat wiki/*.md --extract-links | jq 'select(.url | startswith("./"))'
```

### Report Generation
```bash
# Database → Markdown report
jn cat postgres://localhost/db/sales | jq '{_kind: "table", headers: ..., rows: ...}' | jn put report.md
```

## Security Considerations

**Risks**:
- XSS via HTML blocks (if rendering to HTML later)
- Path traversal via image URLs
- YAML deserialization attacks (in front matter)
- Malicious Markdown with deeply nested structures (DoS)

**Mitigations**:
- Sanitize front matter with safe YAML loader
- Validate image/link URLs (warn on absolute paths or `file://`)
- Set nesting depth limits (max list level, blockquote depth)
- Strip dangerous HTML tags by default

## Dependencies

Add to `pyproject.toml`:
```toml
[tool.poetry.dependencies]
markdown-it-py = "^3.0.0"      # Markdown parser
mdit-py-plugins = "^0.4.0"     # GFM extensions
python-frontmatter = "^1.0.0"  # Front matter parsing
```

## Success Criteria

- [x] Parses Front Matter (YAML and TOML)
- [x] Emits all standard Markdown blocks
- [x] Supports GFM tables
- [x] True streaming (no buffering)
- [x] Can round-trip: MD → NDJSON → MD (structure preserved)
- [x] Works as target adapter (NDJSON → MD)
- [x] Handles nested lists correctly
- [x] Test coverage >85%
- [x] Works in cat/head/tail pipeline
- [x] Clear error messages
- [x] Documentation with examples
