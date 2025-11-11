#!/usr/bin/env -S uv run --script
"""Parse Markdown files with frontmatter and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-frontmatter>=1.0.0",
#   "pyyaml>=6.0"
# ]
# [tool.jn]
# matches = [
#   ".*\\.md$",
#   ".*\\.markdown$"
# ]
# ///

import json
import re
import sys
from typing import Iterator

import frontmatter
import yaml


def reads(
    include_frontmatter: bool = True,
    parse_structure: bool = False,
) -> Iterator[dict]:
    """Read Markdown from stdin, yield NDJSON records.

    Args:
        include_frontmatter: Include frontmatter as separate record
        parse_structure: Parse into structured elements vs single doc

    Yields:
        Dict per document element (frontmatter, content)
    """
    content = sys.stdin.read()
    post = frontmatter.loads(content)

    # Yield frontmatter if present
    if include_frontmatter and post.metadata:
        yield {"type": "frontmatter", **post.metadata}

    # Parse structure or yield as single doc
    if parse_structure:
        yield from _parse_structure(post.content)
    else:
        yield {"type": "content", "content": post.content}


def writes(
    include_frontmatter: bool = True,
    default_frontmatter: dict = None,
) -> None:
    """Read NDJSON from stdin, write Markdown to stdout.

    Args:
        include_frontmatter: Include frontmatter in output
        default_frontmatter: Default frontmatter fields
    """
    default_frontmatter = default_frontmatter or {}

    # Collect all records
    records = []
    for line in sys.stdin:
        records.append(json.loads(line))

    # Separate frontmatter from content
    fm = default_frontmatter.copy()
    content_parts = []

    for record in records:
        if record.get("type") == "frontmatter":
            # Merge frontmatter
            fm_data = {k: v for k, v in record.items() if k != "type"}
            fm.update(fm_data)
        elif record.get("type") == "content":
            # Add content
            content_parts.append(record.get("content", ""))
        else:
            # Generic record - add as content
            content_parts.append(json.dumps(record, indent=2))

    # Assemble markdown
    content = "\n\n".join(content_parts)

    if include_frontmatter and fm:
        # Create frontmatter post
        post = frontmatter.Post(content, **fm)
        print(frontmatter.dumps(post))
    else:
        # Just content
        print(content)


def _parse_structure(content: str) -> Iterator[dict]:
    """Parse markdown into structured elements."""
    lines = content.split("\n")
    current_element = {"type": "text", "content": []}

    for line in lines:
        # Headers
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            if current_element["content"]:
                yield {**current_element, "content": "\n".join(current_element["content"])}
            level = len(header_match.group(1))
            yield {"type": "heading", "level": level, "text": header_match.group(2)}
            current_element = {"type": "text", "content": []}
            continue

        # Code blocks
        if line.strip().startswith("```"):
            if current_element.get("type") == "code":
                # End code block
                yield {**current_element, "content": "\n".join(current_element["content"])}
                current_element = {"type": "text", "content": []}
            else:
                # Start code block
                if current_element["content"]:
                    yield {**current_element, "content": "\n".join(current_element["content"])}
                lang = line.strip()[3:].strip()
                current_element = {"type": "code", "language": lang, "content": []}
            continue

        # Add line to current element
        current_element["content"].append(line)

    # Yield final element
    if current_element["content"]:
        yield {**current_element, "content": "\n".join(current_element["content"])}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Markdown format plugin")
    parser.add_argument("--mode", required=True, choices=["read", "write"], help="Operation mode")
    parser.add_argument(
        "--include-frontmatter", action="store_true", default=True, help="Include frontmatter"
    )
    parser.add_argument("--parse-structure", action="store_true", help="Parse structure")

    args = parser.parse_args()

    if args.mode == "read":
        for record in reads(
            include_frontmatter=args.include_frontmatter,
            parse_structure=args.parse_structure,
        ):
            print(json.dumps(record), flush=True)
    else:
        writes(include_frontmatter=args.include_frontmatter)
