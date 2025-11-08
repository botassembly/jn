"""jc - JSON Convert `toml` file streaming parser

> This streaming parser outputs JSON Lines (cli) or returns an Iterable of
> Dictionaries (module)

Streaming TOML parser. Parses TOML files and yields JSON objects.
Yields the entire parsed TOML as a single object, or if it contains a single
top-level array, yields each element.

Usage (module):

    import jc

    result = jc.parse('toml_s', toml_data.splitlines())
    for item in result:
        # do something

Schema:

TOML file converted to dictionaries based on content structure.
"""

from __future__ import annotations

from typing import ClassVar


class info:
    """Provides parser metadata (version, author, etc.)"""

    version: str = "1.0"
    description: str = "TOML file streaming parser"
    author: str = "JN Team"
    author_email: str = "team@jn.dev"
    details: str = "Using tomli/tomllib library"
    compatible: ClassVar[list[str]] = [
        "linux",
        "darwin",
        "cygwin",
        "win32",
        "aix",
        "freebsd",
    ]
    tags: ClassVar[list[str]] = ["standard", "file", "string"]
    streaming: bool = True


__version__ = info.version


def parse(data, raw=False, quiet=False, ignore_exceptions=False):
    """
    Main text parsing generator function. Returns an iterable object.

    Parameters:

        data:              (iterable)  line-based text data to parse
                                       (e.g. sys.stdin or str.splitlines())

        raw:               (boolean)   unprocessed output if True
        quiet:             (boolean)   suppress warning messages if True
        ignore_exceptions: (boolean)   ignore parsing exceptions if True

    Returns:

        Iterable of Dictionaries
    """
    try:
        import tomli
    except ImportError:
        import tomllib as tomli  # Python 3.11+

    # Read all data
    content = "".join(data)
    parsed = tomli.loads(content)

    # If it's a dict with a single key that's a list, yield each element
    if isinstance(parsed, dict) and len(parsed) == 1:
        _key, value = next(iter(parsed.items()))
        if isinstance(value, list):
            yield from value
            return

    # Otherwise yield the whole object
    yield parsed
