"""Custom JC parser for simple key-value format.

Example input:
    name: John Doe
    age: 30
    city: New York
    status: active

Example output:
    {
      "name": "John Doe",
      "age": "30",
      "city": "New York",
      "status": "active"
    }

Usage:
    # Via jc command (after installing as plugin)
    cat data.txt | jc --keyvalue

    # Via Python API
    import jc
    data = open('data.txt').read()
    result = jc.parse('keyvalue', data)
"""


class info:
    """Parser metadata required by jc."""

    version = "1.0"
    description = "Key-value parser for simple colon-separated format"
    author = "JN Team"
    author_email = "team@example.com"
    compatible = ["linux", "darwin", "win32", "cygwin", "aix", "freebsd"]
    tags = ["command", "file", "string"]
    magic_commands = []  # Not a command parser, just a format parser


def parse(data, raw=False, quiet=False):
    """Parse key-value text into a dictionary.

    Args:
        data (str): Text input in key-value format (key: value per line)
        raw (bool): If True, return raw parsed data (no post-processing)
        quiet (bool): If True, suppress warning messages

    Returns:
        dict: Parsed key-value pairs

    Example:
        >>> text = "name: Alice\\nage: 25"
        >>> parse(text)
        {'name': 'Alice', 'age': '25'}
    """
    if not isinstance(data, str):
        data = data.decode("utf-8", errors="ignore")

    result = {}

    for line in data.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            # Skip empty lines and comments
            continue

        if ":" not in line:
            if not quiet:
                import sys

                print(
                    f"Warning: Skipping line without colon: {line}",
                    file=sys.stderr,
                )
            continue

        # Split on first colon only
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        # Store in result
        result[key] = value

    # Post-processing (if not raw mode)
    if not raw:
        # Could add type conversions here
        # For now, keep everything as strings
        pass

    return result


if __name__ == "__main__":
    # Quick test
    sample = """
    name: John Doe
    age: 30
    city: New York
    status: active
    # This is a comment
    country: USA
    """

    result = parse(sample)
    print("Parsed result:")
    import json

    print(json.dumps(result, indent=2))
