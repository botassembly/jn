"""NDJSON writer (streaming passthrough)."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator


def write_ndjson(
    records: Iterator[Dict[str, Any]],
    output_file: str | Path | None = None,
    append: bool = False,
) -> None:
    """Write NDJSON records to NDJSON format (streaming passthrough).

    Args:
        records: Iterator of JSON objects (dicts)
        output_file: Output file path, or None for stdout
        append: Whether to append to existing file (default: False)

    Notes:
        - Fully streaming (memory efficient)
        - Each record is one line of JSON
        - Suitable for large datasets
    """

    if output_file:
        mode = "a" if append else "w"
        with open(output_file, mode) as output:
            for record in records:
                output.write(json.dumps(record) + "\n")
    else:
        for record in records:
            sys.stdout.write(json.dumps(record) + "\n")
