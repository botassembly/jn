"""Drivers: I/O adapters for sources and targets."""

from dataclasses import dataclass


@dataclass
class Completed:
    """Result of a driver execution."""

    returncode: int
    stdout: bytes
    stderr: bytes
