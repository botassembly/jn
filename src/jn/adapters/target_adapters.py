"""Target format adapters for converting NDJSON to various output formats."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _parse_ndjson(data: bytes) -> List[Dict[str, Any]]:
    """Parse NDJSON bytes into a list of dictionaries.

    Args:
        data: NDJSON bytes (one JSON object per line)

    Returns:
        List of parsed JSON objects
    """
    if not data or data.strip() == b"":
        return []

    records = []
    for line in data.decode("utf-8").strip().split("\n"):
        if line.strip():
            records.append(json.loads(line))
    return records


def _convert_to_json(data: bytes, extension: str) -> bytes:
    """Convert NDJSON to JSON format.

    Strategy:
    - .jsonl and .ndjson: Keep as NDJSON (one object per line)
    - .json: Wrap in array brackets

    Args:
        data: NDJSON input bytes
        extension: File extension (.json, .jsonl, .ndjson)

    Returns:
        Formatted JSON bytes
    """
    ext = extension.lower()

    # For JSONL/NDJSON, pass through as-is (already in NDJSON format)
    if ext in [".jsonl", ".ndjson"]:
        return data

    # For .json, wrap in array
    if ext == ".json":
        records = _parse_ndjson(data)
        return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"

    # Default: pass through
    return data


def _convert_to_csv(data: bytes) -> bytes:
    """Convert NDJSON to CSV format.

    Args:
        data: NDJSON input bytes

    Returns:
        CSV formatted bytes
    """
    records = _parse_ndjson(data)
    if not records:
        return b""

    # Extract all unique field names from all records (union of all keys)
    fieldnames = []
    seen_fields = set()
    for record in records:
        for key in record.keys():
            if key not in seen_fields:
                fieldnames.append(key)
                seen_fields.add(key)

    # Write CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(records)

    return output.getvalue().encode("utf-8")


def _convert_to_yaml(data: bytes) -> bytes:
    """Convert NDJSON to YAML format.

    Args:
        data: NDJSON input bytes

    Returns:
        YAML formatted bytes
    """
    try:
        from ruamel.yaml import YAML
    except ImportError:
        # Fallback to PyYAML if ruamel.yaml not available
        import yaml  # type: ignore

        records = _parse_ndjson(data)
        return yaml.dump(records, default_flow_style=False, allow_unicode=True).encode("utf-8")

    records = _parse_ndjson(data)

    # Use ruamel.yaml for better formatting
    yaml_handler = YAML()
    yaml_handler.default_flow_style = False
    yaml_handler.allow_unicode = True

    output = io.StringIO()
    yaml_handler.dump(records, output)

    return output.getvalue().encode("utf-8")


def _convert_to_toml(data: bytes) -> bytes:
    """Convert NDJSON to TOML format.

    TOML requires a top-level table, so we wrap records in an array.

    Args:
        data: NDJSON input bytes

    Returns:
        TOML formatted bytes
    """
    try:
        import tomli_w  # type: ignore
    except ImportError:
        raise ImportError(
            "tomli_w is required for TOML output. "
            "Install it with: pip install tomli-w"
        )

    records = _parse_ndjson(data)

    # TOML top-level must be a table, so wrap records in array
    toml_data = {"records": records}

    return tomli_w.dumps(toml_data).encode("utf-8")


def _convert_to_xml(data: bytes) -> bytes:
    """Convert NDJSON to XML format.

    Args:
        data: NDJSON input bytes

    Returns:
        XML formatted bytes
    """
    try:
        import xmltodict  # type: ignore
    except ImportError:
        raise ImportError(
            "xmltodict is required for XML output. "
            "Install it with: pip install xmltodict"
        )

    records = _parse_ndjson(data)

    # Wrap records in a root element
    xml_data = {"root": {"record": records}}

    return xmltodict.unparse(xml_data, pretty=True, encoding="utf-8")


def _detect_target_format(path: str) -> Optional[str]:
    """Detect target format from file extension.

    Args:
        path: File path

    Returns:
        Format name (json, csv, yaml, toml, xml) or None
    """
    ext = Path(path).suffix.lower()
    format_map = {
        ".json": "json",
        ".jsonl": "json",
        ".ndjson": "json",
        ".csv": "csv",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".xml": "xml",
    }
    return format_map.get(ext)


def convert_target_format(data: bytes, path: str) -> bytes:
    """Convert NDJSON data to the appropriate format based on file extension.

    Args:
        data: NDJSON input bytes
        path: Target file path (used for extension detection)

    Returns:
        Converted bytes in the target format
    """
    target_format = _detect_target_format(path)
    ext = Path(path).suffix.lower()

    if target_format == "json":
        return _convert_to_json(data, ext)
    elif target_format == "csv":
        return _convert_to_csv(data)
    elif target_format == "yaml":
        return _convert_to_yaml(data)
    elif target_format == "toml":
        return _convert_to_toml(data)
    elif target_format == "xml":
        return _convert_to_xml(data)
    else:
        # No conversion needed, pass through as-is
        return data


__all__ = ["convert_target_format"]
