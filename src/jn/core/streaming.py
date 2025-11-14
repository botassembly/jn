"""NDJSON stream utilities.

Utilities for manipulating NDJSON streams:
- head: First N records
- tail: Last N records
- Other stream transformations
"""

from collections import deque
from collections import deque as DequeType
from typing import TextIO


def head(input_stream: TextIO, n: int, output_stream: TextIO) -> None:
    """Output first N lines from input stream to output stream.

    Args:
        input_stream: Input stream to read from
        n: Number of lines to output
        output_stream: Output stream to write to
    """
    for count, line in enumerate(input_stream):
        if count >= n:
            break
        output_stream.write(line)


def tail(input_stream: TextIO, n: int, output_stream: TextIO) -> None:
    """Output last N lines from input stream to output stream.

    Uses a circular buffer to maintain constant memory regardless of input size.

    Args:
        input_stream: Input stream to read from
        n: Number of lines to output
        output_stream: Output stream to write to
    """
    # Use deque with maxlen for efficient circular buffer
    buffer: DequeType[str] = deque(maxlen=n)

    # Read all lines into buffer (only last N kept)
    for line in input_stream:
        buffer.append(line)

    # Output buffered lines
    for line in buffer:
        output_stream.write(line)
