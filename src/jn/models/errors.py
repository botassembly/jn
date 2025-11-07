"""Result and error models used across the config layer."""

from __future__ import annotations

from pydantic import BaseModel


class Error(BaseModel):
    """Error result from operations."""

    message: str

    def __str__(self) -> str:
        return self.message


class Completed(BaseModel):
    """Result of a subprocess execution."""

    returncode: int
    stdout: bytes
    stderr: bytes


__all__ = ["Completed", "Error"]
