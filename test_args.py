#!/usr/bin/env python3
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--mode", required=True)
parser.add_argument("--profile-sql")
parser.add_argument("--db-path")

args, unknown = parser.parse_known_args()

print(f"Known args: {args}")
print(f"Unknown args: {unknown}")

# Parse params
params = {}
i = 0
while i < len(unknown):
    if unknown[i].startswith("--param-"):
        param_name = unknown[i][8:]
        print(f"Found param: {param_name}, i={i}, len={len(unknown)}")
        if i + 1 < len(unknown):
            params[param_name] = unknown[i + 1]
            print(f"  Value: {unknown[i + 1]}")
            i += 2
        else:
            print(f"  Missing value!")
            sys.exit(1)
    else:
        print(f"Skipping: {unknown[i]}")
        i += 1

print(f"Params: {params}")
