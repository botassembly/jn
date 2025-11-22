#!/usr/bin/env python3
"""Test DuckDB profile resolution."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from jn.addressing import parse_address, AddressResolver

# Parse address with parameter
addr = parse_address("@test/by-id?user_id=1")
print(f"Parsed address: {addr}")
print(f"  Type: {addr.type}")
print(f"  Base: {addr.base}")
print(f"  Parameters: {addr.parameters}")

# Create resolver
resolver = AddressResolver(Path(".jn/plugins"), Path(".jn/plugin_cache.json"))

# Resolve address
try:
    resolved = resolver.resolve(addr, mode="read")
    print(f"\nResolved:")
    print(f"  Plugin: {resolved.plugin_name}")
    print(f"  Plugin path: {resolved.plugin_path}")
    print(f"  Config: {resolved.config}")
    print(f"  URL: {resolved.url}")
    print(f"  Headers: {resolved.headers}")

    # Build command like cat.py would
    cmd = ["uv", "run", "--script", resolved.plugin_path, "--mode", "read"]
    for key, value in resolved.config.items():
        cmd.extend([f"--{key}", str(value)])
    if resolved.url:
        cmd.append(resolved.url)

    print(f"\nCommand that would be executed:")
    print(f"  {' '.join(cmd)}")
except Exception as e:
    print(f"\nError resolving: {e}")
    import traceback
    traceback.print_exc()
