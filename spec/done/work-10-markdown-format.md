# Markdown Format Plugin

## What
Read and write Markdown files (.md), extract frontmatter metadata, convert document structure to NDJSON.

## Why
Documentation is everywhere in Markdown format. Enable processing documentation, extracting metadata, and converting docs to structured data.

## Key Features
- Read Markdown files with frontmatter extraction (YAML/TOML)
- Parse document structure (headings, paragraphs, lists, code blocks)
- Convert to NDJSON (one record per section or paragraph)
- Write NDJSON back to Markdown with frontmatter
- Preserve formatting and structure

## Dependencies
- `python-frontmatter` (parse YAML/TOML frontmatter)
- `mistune` or `markdown` (Markdown parsing)

## Examples
```bash
# Extract frontmatter and headings
jn cat README.md | jn filter '.type == "heading"' | jn jtbl

# Get all code blocks
jn cat tutorial.md | jn filter '.type == "code"' | jn put snippets.json

# Process multiple docs
jn cat docs/*.md | jn filter '.frontmatter.status == "published"' | jn put published.json

# Convert structured data to Markdown
jn cat articles.json | jn put output.md
```

## Document Structure
Each section/element becomes a record:
```json
{"type": "frontmatter", "data": {"title": "...", "date": "..."}}
{"type": "heading", "level": 1, "text": "Introduction"}
{"type": "paragraph", "text": "..."}
{"type": "code", "language": "python", "text": "..."}
{"type": "list", "items": [...]}
```

## Out of Scope
- Markdown rendering (HTML output) - use dedicated tool
- Complex tables - basic support only
- Markdown extensions (GFM specific features) - core syntax first
