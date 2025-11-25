#!/usr/bin/env -S uv run --script
"""Parse XML files and convert to/from NDJSON."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "xmltodict>=0.13.0"
# ]
# [tool.jn]
# matches = [
#   ".*\\.xml$"
# ]
# ///

import json
import sys
import xml.etree.ElementTree as ET
from typing import Any, Iterator, Optional

try:
    import xmltodict
    HAS_XMLTODICT = True
except ImportError:
    HAS_XMLTODICT = False


def element_to_dict(elem: ET.Element) -> dict:
    """Convert an XML element to a dictionary."""
    result: dict[str, Any] = {}

    # Add tag name
    result["_tag"] = elem.tag

    # Add attributes
    if elem.attrib:
        result["_attributes"] = elem.attrib

    # Add text content
    if elem.text and elem.text.strip():
        result["_text"] = elem.text.strip()

    # Add children
    children = list(elem)
    if children:
        child_data: dict[str, Any] = {}
        for child in children:
            child_dict = element_to_dict(child)
            child_tag = child.tag

            # Handle multiple children with same tag
            if child_tag in child_data:
                if not isinstance(child_data[child_tag], list):
                    child_data[child_tag] = [child_data[child_tag]]
                child_data[child_tag].append(child_dict)
            else:
                child_data[child_tag] = child_dict

        result["_children"] = child_data

    # If tail text exists (text after closing tag)
    if elem.tail and elem.tail.strip():
        result["_tail"] = elem.tail.strip()

    return result


def flatten_elements(elem: ET.Element, parent_path: str = "") -> Iterator[dict]:
    """Recursively flatten XML elements into individual records."""
    path = f"{parent_path}/{elem.tag}" if parent_path else elem.tag

    record = {
        "path": path,
        "tag": elem.tag,
    }

    # Add attributes
    if elem.attrib:
        record.update(elem.attrib)
        record["_attributes"] = elem.attrib

    # Add text
    if elem.text and elem.text.strip():
        record["text"] = elem.text.strip()

    # Count children
    children = list(elem)
    if children:
        record["_children_count"] = len(children)

    yield record

    # Recursively process children
    for child in children:
        yield from flatten_elements(child, path)


def extract_coverage_lines(root: ET.Element) -> Iterator[dict]:
    """Extract line-level coverage data from coverage.xml format."""
    # Navigate through the XML structure
    packages = root.find("packages")
    if packages is None:
        return

    for package in packages.findall("package"):
        package_name = package.get("name", "")

        classes_elem = package.find("classes")
        if classes_elem is None:
            continue

        for class_elem in classes_elem.findall("class"):
            filename = class_elem.get("filename", "")
            class_name = class_elem.get("name", "")
            line_rate = class_elem.get("line-rate", "0")
            branch_rate = class_elem.get("branch-rate", "0")

            # Get lines
            lines_elem = class_elem.find("lines")
            if lines_elem is None:
                continue

            for line_elem in lines_elem.findall("line"):
                record = {
                    "package": package_name,
                    "filename": filename,
                    "class": class_name,
                    "file_line_rate": float(line_rate),
                    "file_branch_rate": float(branch_rate),
                    "line_number": int(line_elem.get("number", "0")),
                    "hits": int(line_elem.get("hits", "0")),
                }

                # Add branch info if present
                if line_elem.get("branch") == "true":
                    record["branch"] = True
                    record["condition_coverage"] = line_elem.get("condition-coverage", "")
                    record["missing_branches"] = line_elem.get("missing-branches", "")

                yield record


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read XML from stdin, yield NDJSON records."""
    config = config or {}
    mode = config.get("mode", "flatten")  # flatten, tree, xmltodict, or coverage

    content = sys.stdin.read().strip()
    if not content:
        return

    if mode == "coverage":
        # Special mode for coverage.xml files
        root = ET.fromstring(content)
        yield from extract_coverage_lines(root)
    elif mode == "xmltodict" and HAS_XMLTODICT:
        # Use xmltodict for a more intuitive representation
        data = xmltodict.parse(content)
        yield data
    elif mode == "tree":
        # Return the entire tree as a single record
        root = ET.fromstring(content)
        yield element_to_dict(root)
    else:
        # Flatten mode: yield each element as a separate record
        root = ET.fromstring(content)
        yield from flatten_elements(root)


def dict_to_element(data: dict, parent: Optional[ET.Element] = None) -> ET.Element:
    """Convert a dictionary (from tree mode) back to an XML element."""
    tag = data.get("_tag", "item")
    elem = ET.Element(tag) if parent is None else ET.SubElement(parent, tag)

    # Add attributes
    if "_attributes" in data:
        for key, value in data["_attributes"].items():
            elem.set(key, str(value))

    # Add text content
    if "_text" in data:
        elem.text = data["_text"]

    # Add children
    if "_children" in data:
        for child_tag, child_data in data["_children"].items():
            if isinstance(child_data, list):
                # Multiple children with same tag
                for child_item in child_data:
                    dict_to_element(child_item, elem)
            elif isinstance(child_data, dict):
                # Single child
                dict_to_element(child_data, elem)

    # Handle tail text (rare)
    if "_tail" in data:
        elem.tail = data["_tail"]

    return elem


def record_to_element(record: dict, root_tag: str = "item") -> ET.Element:
    """Convert a simple record (key-value pairs) to an XML element."""
    # Determine the tag name
    tag = record.get("_tag") or record.get("tag") or root_tag
    elem = ET.Element(tag)

    # Separate attributes from child elements
    attributes = record.get("_attributes", {})
    children = {}
    text_content = None

    for key, value in record.items():
        if key in ("_tag", "tag", "_attributes", "_children", "_children_count"):
            continue
        elif key == "text" or key == "_text":
            text_content = value
        elif key in attributes:
            # Already an attribute
            continue
        else:
            # Make it a child element
            children[key] = value

    # Add attributes
    for attr_key, attr_value in attributes.items():
        elem.set(attr_key, str(attr_value))

    # Add text content
    if text_content:
        elem.text = str(text_content)
    elif not children:
        # If no children and no text, check if all non-special keys should be children
        for key, value in record.items():
            if not key.startswith("_") and key not in ("tag",):
                child = ET.SubElement(elem, key)
                child.text = str(value)
    else:
        # Add children
        for child_key, child_value in children.items():
            child = ET.SubElement(elem, child_key)
            child.text = str(child_value)

    return elem


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write XML to stdout."""
    config = config or {}
    mode = config.get("mode", "records")  # records, tree, or raw
    root_tag = config.get("root_tag", "root")
    item_tag = config.get("item_tag", "item")
    indent_output = config.get("indent", True)

    # Collect all records
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            records.append(json.loads(line))

    if not records:
        print("<?xml version=\"1.0\" encoding=\"UTF-8\"?>", flush=True)
        print(f"<{root_tag}/>", flush=True)
        return

    if mode == "tree":
        # Single record represents entire tree structure
        if len(records) == 1:
            root = dict_to_element(records[0])
        else:
            # Multiple records: wrap in root
            root = ET.Element(root_tag)
            for record in records:
                dict_to_element(record, root)
    elif mode == "raw":
        # Records already have XML structure info
        root = ET.Element(root_tag)
        for record in records:
            if "_tag" in record or "tag" in record:
                elem = record_to_element(record, item_tag)
                root.append(elem)
            else:
                # Simple record: convert to child elements
                item = ET.SubElement(root, item_tag)
                for key, value in record.items():
                    if not key.startswith("_"):
                        child = ET.SubElement(item, key)
                        child.text = str(value)
    else:
        # records mode (default): each record becomes an element
        root = ET.Element(root_tag)
        for record in records:
            elem = record_to_element(record, item_tag)
            root.append(elem)

    # Pretty print
    if indent_output:
        ET.indent(root, space="  ")

    # Output with XML declaration
    print("<?xml version=\"1.0\" encoding=\"UTF-8\"?>", flush=True)
    xml_string = ET.tostring(root, encoding="unicode")
    print(xml_string, flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="XML format plugin - read/write XML files"
    )
    parser.add_argument("--mode", choices=["read", "write"], help="Mode")
    parser.add_argument(
        "--parse-mode",
        choices=["flatten", "tree", "xmltodict", "coverage"],
        default="flatten",
        help="XML parsing mode (for read mode)"
    )
    parser.add_argument(
        "--write-mode",
        choices=["records", "tree", "raw"],
        default="records",
        help="XML write mode: records (each NDJSON->element), tree (preserve structure), raw (with tag info)"
    )
    parser.add_argument("--root-tag", default="root", help="Root element tag name")
    parser.add_argument("--item-tag", default="item", help="Item element tag name")
    parser.add_argument("--indent", action="store_true", default=True, help="Pretty print XML")

    args = parser.parse_args()

    if not args.mode:
        parser.error("--mode is required")

    config = {}
    if args.mode == "read":
        config["mode"] = args.parse_mode
        for record in reads(config):
            print(json.dumps(record), flush=True)
    else:
        config["mode"] = args.write_mode
        config["root_tag"] = args.root_tag
        config["item_tag"] = args.item_tag
        config["indent"] = args.indent
        writes(config)
