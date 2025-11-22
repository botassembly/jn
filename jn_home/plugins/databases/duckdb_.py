#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["duckdb>=1.0.0"]
# [tool.jn]
# matches = ["^duckdb://.*", ".*\\.duckdb$", ".*\\.ddb$"]
# role = "protocol"
# ///

"""DuckDB plugin for JN - query analytical databases."""

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

import duckdb


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read from DuckDB database, yielding NDJSON records.

    Config keys:
        path: Database file path
        query: SQL query to execute
        params: Dict of bind parameters
        limit: Optional row limit
        profile_sql: SQL from profile file (takes precedence over query)
    """
    cfg = config or {}

    # Profile mode: SQL comes from .sql file
    if cfg.get("profile_sql"):
        db_path = cfg["db_path"]
        query = cfg["profile_sql"]
        params = cfg.get("params") or {}
    # Direct mode: Parse address
    else:
        raw_path = (
            cfg.get("path") or
            cfg.get("address") or
            cfg.get("url")
        )
        if not raw_path:
            raise ValueError("Database path required")

        db_path, query, params, table = _parse_address(str(raw_path))

        # Merge params from config
        user_params = cfg.get("params") or {}
        params = {**params, **user_params}

        # Override query from config
        if cfg.get("query"):
            query = cfg["query"]
        # Table shortcut: duckdb://db.duckdb/table_name
        elif table:
            query = f"SELECT * FROM {table}"

        if not query:
            raise ValueError(
                "SQL query required. Use:\n"
                "  duckdb://db.duckdb?query=SELECT * FROM table\n"
                "  duckdb://db.duckdb/table_name (shortcut)\n"
                "  jn cat '@profile/query'"
            )

    # Handle limit
    limit = cfg.get("limit")
    if limit:
        query = _apply_limit(query, limit)

    # Execute query
    conn = None
    try:
        conn = duckdb.connect(db_path, read_only=True)

        # Convert :param to $param for consistency
        query = query.replace(":", "$")

        # Execute with parameters
        cursor = conn.execute(query, params or None)
        columns = [col[0] for col in cursor.description]

        # Stream results
        row = cursor.fetchone()
        while row is not None:
            yield dict(zip(columns, row))
            row = cursor.fetchone()

    except duckdb.Error as e:
        raise RuntimeError(f"DuckDB error: {e}\nSQL: {query}") from e
    finally:
        if conn:
            conn.close()


def writes(config: Optional[dict] = None) -> None:
    """Write mode not yet supported."""
    raise NotImplementedError(
        "DuckDB writes not yet supported. Use DuckDB CLI for loading data."
    )


def _parse_address(address: str) -> Tuple[str, Optional[str], Dict[str, str], Optional[str]]:
    """Parse duckdb:// address into components.

    Formats:
        duckdb://path/to/file.duckdb?query=SELECT...&param=value
        duckdb://path/to/file.duckdb/table_name
        file.duckdb (plain file path)

    Returns:
        (db_path, query_sql, params, table_name)
    """
    if not address.startswith("duckdb://"):
        # Plain file path
        return address, None, {}, None

    parsed = urllib.parse.urlparse(address)
    raw_path = parsed.netloc + parsed.path
    query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    # Extract query
    query_sql = query_params.pop("query", [None])[0]

    # Extract params (everything except query and limit)
    limit = query_params.pop("limit", [None])[0]
    params = {
        key: values[-1]
        for key, values in query_params.items()
        if values
    }

    # Handle limit separately (converted to int by caller)
    if limit:
        params["limit"] = limit

    # Split db path and table name
    db_path, table = _split_db_and_table(raw_path)

    return db_path or "", query_sql, params, table


def _split_db_and_table(raw_path: str) -> Tuple[str, Optional[str]]:
    """Split path like 'db.duckdb/table' into ('db.duckdb', 'table')."""
    if not raw_path:
        return raw_path, None

    for ext in (".duckdb", ".ddb"):
        idx = raw_path.find(ext)
        if idx != -1:
            db_path = raw_path[:idx + len(ext)]
            suffix = raw_path[idx + len(ext):].lstrip("/")
            return db_path or raw_path, suffix or None

    return raw_path, None


def _apply_limit(query: str, limit: int) -> str:
    """Append LIMIT clause if not present."""
    if re.search(r"\bLIMIT\b", query, re.IGNORECASE):
        return query

    trimmed = query.rstrip().rstrip(";")
    return f"{trimmed} LIMIT {limit}"


if __name__ == "__main__":
    # DEBUG
    sys.stderr.write(f"DEBUG: sys.argv = {sys.argv}\n")
    sys.stderr.flush()

    parser = argparse.ArgumentParser(description="JN DuckDB plugin")
    parser.add_argument("--mode", required=True, choices=["read", "write"])
    parser.add_argument("--path", help="Database path or duckdb:// URL")
    parser.add_argument("--query", help="SQL query")
    parser.add_argument("--limit", type=int, help="Row limit")
    parser.add_argument("--db-path", help="Database path (for profile mode)")
    parser.add_argument("--profile-sql", help="SQL from profile file")
    parser.add_argument("address", nargs="?", help="Alternative to --path")

    # Parse --param-* arguments
    args, unknown = parser.parse_known_args()

    # DEBUG
    sys.stderr.write(f"DEBUG: unknown args = {unknown}\n")
    sys.stderr.flush()

    params = {}
    i = 0
    while i < len(unknown):
        if unknown[i].startswith("--param-"):
            param_name = unknown[i][8:]  # Strip '--param-'
            sys.stderr.write(f"DEBUG: Found param {param_name} at index {i}, len={len(unknown)}\n")
            sys.stderr.flush()
            if i + 1 < len(unknown):
                params[param_name] = unknown[i + 1]
                sys.stderr.write(f"DEBUG: Set param {param_name} = {unknown[i + 1]}\n")
                sys.stderr.flush()
                i += 2
            else:
                sys.stderr.write(f"Missing value for {unknown[i]}\n")
                sys.exit(1)
        else:
            i += 1

    if args.mode == "write":
        sys.stderr.write("Write mode not supported\n")
        sys.exit(1)

    # Build config
    config = {"params": params}

    if args.profile_sql:
        # Profile mode
        config["profile_sql"] = args.profile_sql
        config["db_path"] = args.db_path or args.path or args.address
    else:
        # Direct mode
        config["path"] = args.path or args.address
        if args.query:
            config["query"] = args.query
        if args.limit:
            config["limit"] = args.limit

    # Execute
    try:
        for row in reads(config):
            print(json.dumps(row), flush=True)
    except (ValueError, RuntimeError) as e:
        sys.stderr.write(f"{e}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
