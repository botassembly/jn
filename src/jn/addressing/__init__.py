"""Universal addressability system for JN.

This module provides address parsing and resolution for all JN data sources:
- Files: data.csv, /path/to/file.json
- Protocols: http://..., s3://..., gmail://...
- Profiles: @namespace/component
- Plugins: @plugin
- Stdio: - (stdin/stdout)

Syntax:
    address[~format][?parameters]

Examples:
    data.csv                        # Auto-detect format
    data.txt~csv                    # Force CSV format
    -~csv?delimiter=;               # Stdin as CSV with semicolon delimiter
    @api/source?limit=100           # Profile with parameters
    -~table.grid                    # Stdout as grid table (shorthand)
"""

from .parser import parse_address
from .resolver import AddressResolutionError, AddressResolver, ExecutionStage
from .types import Address, AddressType, ResolvedAddress

__all__ = [
    "Address",
    "AddressResolutionError",
    "AddressResolver",
    "AddressType",
    "ExecutionStage",
    "ResolvedAddress",
    "parse_address",
]
