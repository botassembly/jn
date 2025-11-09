"""jc - JSON Convert `generic` streaming parser

> This streaming parser outputs JSON Lines (cli) or returns an Iterable of
> Dictionaries (module)

Generic streaming parser for unknown commands. Wraps each output line in
a JSON object with metadata (command, args, line number, text).

This is a fallback parser that ensures ALL command output can be converted
to JSON, even when no specific parser exists.

Usage (module):

    import jc

    result = jc.parse('generic_s', command_output.splitlines())
    for item in result:
        # do something with item['text']

Schema:

Each line of output is wrapped in a dictionary:

    {
      "line":     integer,    # Line number (1-indexed)
      "text":     string      # Line content (without trailing newline)
    }

Note: Command name and arguments should be added by the caller
via context if needed.
"""

from __future__ import annotations

from typing import ClassVar


class info:
    """Provides parser metadata (version, author, etc.)"""

    version: str = "1.0"
    description: str = (
        "Generic streaming parser (fallback for unknown commands)"
    )
    author: str = "JN Team"
    author_email: str = "team@jn.dev"
    details: str = "Wraps each line in JSON with line number and text"
    compatible: ClassVar[list[str]] = [
        "linux",
        "darwin",
        "cygwin",
        "win32",
        "aix",
        "freebsd",
    ]
    tags: ClassVar[list[str]] = ["standard", "generic", "string"]
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
    for line_num, line_text in enumerate(data, start=1):
        yield {
            "line": line_num,
            "text": line_text.rstrip("\n\r"),
        }
