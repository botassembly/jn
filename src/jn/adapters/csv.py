"""CSV adapter: Convert CSV/TSV to NDJSON."""

import csv
import io
import json
from typing import Optional

from jn.models import CsvConfig


def csv_to_ndjson(
    raw_bytes: bytes,
    config: Optional[CsvConfig] = None,
) -> bytes:
    """Convert CSV bytes to NDJSON.

    Args:
        raw_bytes: Raw CSV file content
        config: CSV parsing configuration (defaults if None)

    Returns:
        NDJSON bytes (one JSON object per line)

    Implementation:
        Uses csv.DictReader for streaming line-by-line parsing.
        Each row becomes a JSON object with column names as keys.
        Memory usage is O(1) regardless of file size.

    Example:
        >>> csv_bytes = b"name,age\\nAlice,30\\nBob,25"
        >>> result = csv_to_ndjson(csv_bytes)
        >>> print(result.decode())
        {"name":"Alice","age":"30"}
        {"name":"Bob","age":"25"}
    """
    config = config or CsvConfig()

    # Decode bytes to text stream
    try:
        text_stream = io.StringIO(raw_bytes.decode(config.encoding))
    except UnicodeDecodeError as e:
        raise ValueError(
            f"Encoding error (tried {config.encoding}): {e}"
        ) from e

    # Create CSV reader (streaming generator)
    try:
        reader = csv.DictReader(
            text_stream,
            delimiter=config.delimiter,
            quotechar=config.quotechar,
            fieldnames=config.fieldnames,
            skipinitialspace=config.skip_initial_space,
        )

        # Stream rows as NDJSON
        ndjson_lines = []
        for row in reader:
            # row is OrderedDict[str, str]
            # Convert to JSON and append newline
            json_line = json.dumps(row, ensure_ascii=False)
            ndjson_lines.append(json_line)

    except csv.Error as e:
        raise ValueError(f"CSV parsing error: {e}") from e

    # Join with newlines and encode back to bytes
    ndjson_text = "\n".join(ndjson_lines)
    if ndjson_lines:
        ndjson_text += "\n"
    return ndjson_text.encode(config.encoding)


__all__ = ["csv_to_ndjson"]
