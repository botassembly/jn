import json


def test_plugin_call_markdown_read_structure(invoke):
    """Test reading Markdown with frontmatter."""
    markdown_content = """---
title: Test Document
author: Alice
---

# Introduction

This is a test document.
"""
    res = invoke(
        ["plugin", "call", "markdown_", "--mode", "read"],
        input_data=markdown_content,
    )
    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]

    # Parse records
    records = [json.loads(line) for line in lines]

    # Check frontmatter (fields are flattened, not wrapped in "data")
    frontmatter = next(
        (r for r in records if r.get("type") == "frontmatter"), None
    )
    assert frontmatter is not None
    assert frontmatter["title"] == "Test Document"
    assert frontmatter["author"] == "Alice"

    # Check document content (type is "content", not "document")
    doc = next((r for r in records if r.get("type") == "content"), None)
    assert doc is not None
    assert "# Introduction" in doc["content"]
    assert "This is a test document." in doc["content"]


def test_plugin_call_markdown_write(invoke):
    """Test writing NDJSON to Markdown.

    Note: Plugin only converts "frontmatter" and "content" types.
    Other types (like "heading", "paragraph") are JSON-dumped to content.
    """
    # Use format the plugin actually understands
    ndjson = """{"type": "frontmatter", "title": "Test"}
{"type": "content", "content": "# Introduction\\n\\nThis is a test."}
"""
    res = invoke(
        ["plugin", "call", "markdown_", "--mode", "write"], input_data=ndjson
    )
    assert res.exit_code == 0
    output = res.output.strip()

    assert "---" in output  # Frontmatter delimiter
    assert "title: Test" in output
    assert "# Introduction" in output
    assert "This is a test." in output


def test_plugin_call_markdown_no_frontmatter(invoke):
    """Test reading Markdown without frontmatter."""
    markdown_content = """# Title

Plain markdown without frontmatter.
"""
    res = invoke(
        ["plugin", "call", "markdown_", "--mode", "read"],
        input_data=markdown_content,
    )
    assert res.exit_code == 0
    lines = [l for l in res.output.strip().split("\n") if l]
    records = [json.loads(line) for line in lines]

    # Should not have frontmatter record
    frontmatter = next(
        (r for r in records if r.get("type") == "frontmatter"), None
    )
    assert frontmatter is None

    # Should have content (type is "content", not "document")
    doc = next((r for r in records if r.get("type") == "content"), None)
    assert doc is not None
    assert "# Title" in doc["content"]
    assert "Plain markdown" in doc["content"]
