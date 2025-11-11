#!/usr/bin/env -S uv run --script
"""Parse YAML files (including multi-document) and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ruamel.yaml>=0.18.0"
# ]
# [tool.jn]
# matches = [
#   ".*\\.yaml$",
#   ".*\\.yml$"
# ]
# ///

import json
import sys
from typing import Iterator, Optional

from ruamel.yaml import YAML


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    config = config or {}
    yaml = YAML()
    yaml.preserve_quotes = True
    for doc in yaml.load_all(sys.stdin):
        if doc is not None:
            if isinstance(doc, dict):
                yield doc
            elif isinstance(doc, list):
                for item in doc:
                    if isinstance(item, dict):
                        yield item
                    else:
                        yield {"value": item}
            else:
                yield {"value": doc}


def writes(config: Optional[dict] = None) -> None:
    config = config or {}
    multi_document = config.get("multi_document", True)
    indent = config.get("indent", 2)
    yaml = YAML()
    yaml.indent(mapping=indent, sequence=indent, offset=indent)
    yaml.default_flow_style = False
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            records.append(json.loads(line))
    if not records:
        return
    if multi_document and len(records) > 1:
        for i, record in enumerate(records):
            if i > 0:
                sys.stdout.write("---\n")
            yaml.dump(record, sys.stdout)
    else:
        if len(records) == 1:
            yaml.dump(records[0], sys.stdout)
        else:
            yaml.dump(records, sys.stdout)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="YAML format plugin - read/write YAML files"
    )
    parser.add_argument("--mode", choices=["read", "write"], help="Mode")
    parser.add_argument("--indent", type=int, default=2)
    parser.add_argument("--no-multi-document", dest="multi_document", action="store_false")
    args = parser.parse_args()
    if not args.mode:
        parser.error("--mode is required when not running tests")
    config = {}
    if args.mode == "read":
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        config["multi_document"] = args.multi_document
        config["indent"] = args.indent
        writes(config)
