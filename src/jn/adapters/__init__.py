"""Adapters for format boundary handling (non-JSON ↔ JSON)."""

from .csv import csv_to_ndjson

__all__ = ["csv_to_ndjson"]
