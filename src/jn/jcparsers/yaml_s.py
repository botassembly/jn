"""jc - JSON Convert `yaml` file streaming parser

> This streaming parser outputs JSON Lines (cli) or returns an Iterable of
> Dictionaries (module)

Streaming YAML parser. Parses YAML files and yields JSON objects.
If the YAML contains an array, yields each element. If it's a single object,
yields that object.

Usage (module):

    import jc

    result = jc.parse('yaml_s', yaml_data.splitlines())
    for item in result:
        # do something

Schema:

YAML file converted to dictionaries based on content structure.
"""

from __future__ import annotations

from typing import ClassVar


class info:
    """Provides parser metadata (version, author, etc.)"""

    version: str = "1.0"
    description: str = "YAML file streaming parser"
    author: str = "JN Team"
    author_email: str = "team@jn.dev"
    details: str = "Using ruamel.yaml library"
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
        from ruamel.yaml import YAML
    except ImportError:
        import yaml  # type: ignore

        # Read all data
        content = "".join(data)
        parsed = yaml.safe_load(content)

        # Yield elements
        if isinstance(parsed, list):
            for item in parsed:
                yield item
        elif parsed is not None:
            yield parsed
        return

    # Use ruamel.yaml for better parsing
    yaml_handler = YAML()
    yaml_handler.preserve_quotes = True

    # Read all data
    content = "".join(data)
    parsed = yaml_handler.load(content)

    # Yield elements
    if isinstance(parsed, list):
        for item in parsed:
            yield item
    elif parsed is not None:
        yield parsed
