"""jc - JSON Convert `tsv` file streaming parser

> This streaming parser outputs JSON Lines (cli) or returns an Iterable of
> Dictionaries (module)

Streaming TSV (tab-separated values) parser. Uses Python's csv.DictReader
with tab dialect. The first row must be a header row.

Usage (module):

    import jc

    result = jc.parse('tsv_s', tsv_data.splitlines())
    for item in result:
        # do something

Schema:

TSV file converted to a Dictionary where each row is a dict:
https://docs.python.org/3/library/csv.html

    {
      "column_name1":     string,
      "column_name2":     string
    }
"""

from __future__ import annotations

import csv
from typing import ClassVar


class info:
    """Provides parser metadata (version, author, etc.)"""

    version: str = "1.0"
    description: str = "TSV file streaming parser"
    author: str = "JN Team"
    author_email: str = "team@jn.dev"
    details: str = "Using the python standard csv library with tab dialect"
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
    reader = csv.DictReader(data, dialect=csv.excel_tab)
    yield from reader
