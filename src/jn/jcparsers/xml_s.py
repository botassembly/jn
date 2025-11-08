"""jc - JSON Convert `xml` file streaming parser

> This streaming parser outputs JSON Lines (cli) or returns an Iterable of
> Dictionaries (module)

Streaming XML parser. Parses XML files and yields the entire parsed structure
as a single JSON object.

Usage (module):

    import jc

    result = jc.parse('xml_s', xml_data.splitlines())
    for item in result:
        # do something

Schema:

XML file converted to dictionaries using xmltodict.
"""

from __future__ import annotations

from typing import ClassVar


class info:
    """Provides parser metadata (version, author, etc.)"""

    version: str = "1.0"
    description: str = "XML file streaming parser"
    author: str = "JN Team"
    author_email: str = "team@jn.dev"
    details: str = "Using xmltodict library"
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
    import xmltodict

    # Read all data
    content = "".join(data)
    parsed = xmltodict.parse(content)

    # Yield the parsed XML as a single object
    yield parsed
