"""JSON writer for NDJSON data."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator


def write_json(
    records: Iterator[Dict[str, Any]],
    output_file: str | Path | None = None,
    pretty: bool = False,
) -> None:
    """Write NDJSON records to JSON array format.

    Args:
        records: Iterator of JSON objects (dicts)
        output_file: Output file path, or None for stdout
        pretty: Whether to pretty-print with indentation (default: False)

    Notes:
        - Buffers all records in memory (must collect to write array brackets)
        - For large datasets, consider using NDJSON format instead
    """

    # Collect all records (must buffer for JSON array)
    records_list = list(records)

    # Write JSON array
    if output_file:
        with open(output_file, "w") as output:
            if pretty:
                json.dump(records_list, output, indent=2)
            else:
                json.dump(records_list, output)
            output.write("\n")  # Add trailing newline
    else:
        if pretty:
            json.dump(records_list, sys.stdout, indent=2)
        else:
            json.dump(records_list, sys.stdout)
        sys.stdout.write("\n")  # Add trailing newline
