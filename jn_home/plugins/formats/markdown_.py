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
from typing import Iterator, Optional

try:
    import frontmatter
    import yaml
except ImportError as e:
    print(f"Error: Missing dependency - {e}", file=sys.stderr)
    sys.exit(1)


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read Markdown from stdin, yield NDJSON records.

    Config:
        include_frontmatter: Include frontmatter as separate record (default: True)
        parse_structure: Parse into structured elements vs single doc (default: False)

    Yields:
        Dict per document element (frontmatter, content)
    """
    config = config or {}
    include_frontmatter = config.get("include_frontmatter", True)
    parse_structure = config.get("parse_structure", False)

    # Read entire markdown file
    content = sys.stdin.read()

    # Parse frontmatter
    post = frontmatter.loads(content)

    # Yield frontmatter if present
    if include_frontmatter and post.metadata:
        yield {"type": "frontmatter", "data": post.metadata}

    # For now, yield entire content as single document
    # TODO: Add structure parsing in future enhancement
    if parse_structure:
        # Simple structure parsing - split by headings
        lines = post.content.split("\n")
        current_section = None
        current_text = []

        for line in lines:
            # Check if heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                # Yield previous section if exists
                if current_section:
                    yield current_section
                if current_text:
                    yield {"type": "paragraph", "text": "\n".join(current_text).strip()}
                    current_text = []

                # Start new section
                level = len(heading_match.group(1))
                text = heading_match.group(2)
                current_section = {"type": "heading", "level": level, "text": text}
                yield current_section
                current_section = None
            elif line.strip():
                current_text.append(line)
            elif current_text:
                # Empty line - end of paragraph
                yield {"type": "paragraph", "text": "\n".join(current_text).strip()}
                current_text = []

        # Yield remaining text
        if current_text:
            yield {"type": "paragraph", "text": "\n".join(current_text).strip()}
    else:
        # Yield entire content as single record
        yield {"type": "document", "content": post.content, "metadata": post.metadata}


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write Markdown to stdout.

    Config:
        include_frontmatter: Write frontmatter block (default: True)
        frontmatter_format: 'yaml' or 'toml' (default: 'yaml')

    Reads structured elements and reconstructs Markdown document.
    """
    config = config or {}
    include_frontmatter = config.get("include_frontmatter", True)
    frontmatter_format = config.get("frontmatter_format", "yaml")

    # Collect all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            records.append(json.loads(line))

    if not records:
        return

    # Extract frontmatter if present
    frontmatter_data = None
    content_records = []

    for record in records:
        if record.get("type") == "frontmatter":
            frontmatter_data = record.get("data", {})
        else:
            content_records.append(record)

    # Write frontmatter
    if include_frontmatter and frontmatter_data:
        if frontmatter_format == "yaml":
            sys.stdout.write("---\n")
            sys.stdout.write(yaml.dump(frontmatter_data, default_flow_style=False))
            sys.stdout.write("---\n\n")
        elif frontmatter_format == "toml":
            try:
                import tomli_w
                sys.stdout.write("+++\n")
                sys.stdout.write(tomli_w.dumps(frontmatter_data))
                sys.stdout.write("+++\n\n")
            except ImportError:
                print("Error: tomli-w required for TOML frontmatter", file=sys.stderr)
                sys.exit(1)

    # Write content
    for record in content_records:
        record_type = record.get("type")

        if record_type == "heading":
            level = record.get("level", 1)
            text = record.get("text", "")
            sys.stdout.write(f"{'#' * level} {text}\n\n")

        elif record_type == "paragraph":
            text = record.get("text", "")
            sys.stdout.write(f"{text}\n\n")

        elif record_type == "document":
            # Handle single document record
            content = record.get("content", "")
            sys.stdout.write(content)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Markdown format plugin - read/write Markdown files with frontmatter"
    )
    parser.add_argument(
        "--mode",
        choices=["read", "write"],
        help="Operation mode: read Markdown to NDJSON, or write NDJSON to Markdown",
    )
    parser.add_argument(
        "--no-frontmatter",
        dest="include_frontmatter",
        action="store_false",
        help="Don't include frontmatter when reading/writing",
    )
    parser.add_argument(
        "--parse-structure",
        action="store_true",
        help="Parse structure (split by headings)",
    )
    parser.add_argument(
        "--frontmatter-format",
        choices=["yaml", "toml"],
        default="yaml",
        help="Frontmatter format when writing (default: yaml)",
    )

    args = parser.parse_args()

    if not args.mode:
        parser.error("--mode is required")

    # Build config
    config = {"include_frontmatter": args.include_frontmatter}

    if args.mode == "read":
        config["parse_structure"] = args.parse_structure
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        config["frontmatter_format"] = args.frontmatter_format
        writes(config)
