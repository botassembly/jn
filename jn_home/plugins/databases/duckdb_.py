#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["duckdb>=1.0.0"]
# [tool.jn]
# matches = ["^duckdb://.*", ".*\\.duckdb$", ".*\\.ddb$", "^@.*/.*"]
# role = "protocol"
# manages_parameters = true
# supports_container = true
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


def _get_profile_paths() -> list[Path]:
    """Get profile search paths in priority order.

    Uses JN_HOME and JN_PROJECT_DIR environment variables passed by framework.
    """
    import os

    paths = []

    # 1. Project profiles (highest priority) - from JN_PROJECT_DIR env var
    project_dir_env = os.getenv("JN_PROJECT_DIR")
    if project_dir_env:
        project_dir = Path(project_dir_env) / "profiles" / "duckdb"
        if project_dir.exists():
            paths.append(project_dir)

    # 2. User profiles - from JN_HOME env var (framework always sets this)
    jn_home = os.getenv("JN_HOME", str(Path.home() / ".jn"))
    user_dir = Path(jn_home) / "profiles" / "duckdb"
    if user_dir.exists():
        paths.append(user_dir)

    return paths


def _extract_declared_params(sql_content: str) -> list[str]:
    """Extract declared parameters from SQL content.

    Looks for "-- Parameters: param1, param2" comment pattern.
    If not found, returns empty list (no auto-NULL injection).

    Args:
        sql_content: SQL query content

    Returns:
        List of declared parameter names
    """
    for line in sql_content.split("\n")[:20]:
        line = line.strip()
        if "-- Parameters:" in line:
            params_text = line.split("Parameters:", 1)[1].strip()
            return [p.split("(")[0].strip() for p in params_text.split(",") if p.strip()]
    return []


def _load_profile(reference: str) -> Tuple[str, str, dict]:
    """Load DuckDB profile from filesystem.

    Vendored from framework to make plugin self-contained.

    Args:
        reference: Profile reference like "@test/all-users"

    Returns:
        Tuple of (db_path, sql_content, metadata)

    Raises:
        ValueError: If profile not found
    """
    if not reference.startswith("@"):
        raise ValueError(f"Invalid profile reference: {reference}")

    # Parse @namespace/query
    parts = reference[1:].split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid profile reference format: {reference}")

    namespace, query_name = parts

    # Search for profile in priority order
    for profile_root in _get_profile_paths():
        namespace_dir = profile_root / namespace
        sql_file = namespace_dir / f"{query_name}.sql"

        if sql_file.exists():
            # Load SQL
            sql_content = sql_file.read_text()

            # Load _meta.json from namespace directory
            meta_path = namespace_dir / "_meta.json"
            if not meta_path.exists():
                raise ValueError(
                    f"Profile meta file not found: {meta_path}\n"
                    f"  Create a _meta.json file with database path and settings"
                )

            meta = json.loads(meta_path.read_text())
            db_path = meta.get("path")

            if not db_path:
                raise ValueError(
                    f"Profile missing 'path' in meta file: {meta_path}"
                )

            # Resolve relative paths
            if not Path(db_path).is_absolute():
                db_path = str(meta_path.parent / db_path)

            return db_path, sql_content, meta

    # Profile not found
    raise ValueError(
        f"DuckDB profile not found: {reference}\n"
        f"  Run 'jn profile list --type duckdb' to see available profiles"
    )


def inspect_profiles() -> Iterator[dict]:
    """List all available DuckDB profiles.

    Called by framework with --mode inspect-profiles.
    Returns ProfileInfo-compatible records.
    """
    for profile_root in _get_profile_paths():
        # Scan each namespace directory
        for namespace_dir in sorted(profile_root.iterdir()):
            if not namespace_dir.is_dir():
                continue

            namespace = namespace_dir.name

            # Load namespace metadata
            meta_path = namespace_dir / "_meta.json"
            if not meta_path.exists():
                continue

            try:
                meta = json.loads(meta_path.read_text())
            except json.JSONDecodeError:
                continue

            # Scan .sql files in namespace
            for sql_file in sorted(namespace_dir.glob("*.sql")):
                if sql_file.name.startswith("_"):
                    continue

                # Parse profile metadata from SQL file
                description = ""
                params = []

                try:
                    content = sql_file.read_text()
                    for line in content.split("\n")[:20]:
                        line = line.strip()

                        # Description from first comment
                        if line.startswith("--") and not description:
                            desc = line.lstrip("-").strip()
                            if desc and not desc.startswith("Parameters:"):
                                description = desc

                        # Parameters from "-- Parameters: x, y, z"
                        if "-- Parameters:" in line:
                            params_text = line.split("Parameters:", 1)[1].strip()
                            params = [p.split("(")[0].strip() for p in params_text.split(",")]
                            break

                    # If no explicit parameters, find $param or :param in SQL
                    if not params:
                        params = list(set(re.findall(r"[$:](\\w+)", content)))

                except Exception:
                    pass

                # Build profile info
                query_name = sql_file.stem
                reference = f"@{namespace}/{query_name}"

                yield {
                    "reference": reference,
                    "type": "duckdb",
                    "namespace": namespace,
                    "name": query_name,
                    "path": str(sql_file),
                    "description": description,
                    "params": params,
                    "examples": [],
                }


def _list_tables(db_path: str) -> Iterator[dict]:
    """List tables in DuckDB database (for container inspection).

    Yields table listings compatible with inspect command.
    """
    conn = None
    try:
        conn = duckdb.connect(db_path, read_only=True)

        # Query information schema for tables
        cursor = conn.execute("""
            SELECT
                table_name,
                table_type,
                COALESCE(
                    (SELECT COUNT(*) FROM information_schema.columns
                     WHERE table_name = t.table_name),
                    0
                ) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'main'
            ORDER BY table_name
        """)

        for row in cursor.fetchall():
            table_name, table_type, column_count = row
            yield {
                "_type": "table",
                "_container": db_path,
                "name": table_name,
                "type": table_type.lower(),
                "columns": column_count,
            }
    except duckdb.Error as e:
        raise RuntimeError(f"DuckDB error listing tables: {e}") from e
    finally:
        if conn:
            conn.close()


def _list_profile_queries(namespace: str) -> Iterator[dict]:
    """List available queries in a DuckDB profile namespace.

    Yields query listings compatible with inspect command.
    """
    from pathlib import Path
    import os

    # Find profile directory
    jn_home = Path(os.getenv("JN_HOME", Path.home() / ".jn"))
    profile_dir = jn_home / "profiles" / "duckdb" / namespace

    if not profile_dir.exists():
        return

    # List .sql files
    for sql_file in sorted(profile_dir.glob("*.sql")):
        if sql_file.name == "_meta.sql":
            continue

        # Read first comment line as description
        description = ""
        params = []
        try:
            content = sql_file.read_text()
            for line in content.split("\n")[:20]:
                line = line.strip()
                if line.startswith("--") and not description:
                    desc = line.lstrip("-").strip()
                    if desc and not desc.startswith("Parameters:"):
                        description = desc
                # Parse parameters
                if "-- Parameters:" in line:
                    params_text = line.split("Parameters:", 1)[1].strip()
                    params = [p.split("(")[0].strip() for p in params_text.split(",")]
                    break
        except Exception:
            pass

        # Build query name from file name
        query_name = sql_file.stem

        yield {
            "_type": "query",
            "_container": f"@{namespace}",
            "name": query_name,
            "reference": f"@{namespace}/{query_name}",
            "description": description,
            "params": params,
        }


def reads(config: Optional[dict] = None) -> Iterator[dict]:
    """Read from DuckDB database, yielding NDJSON records.

    Config keys:
        path: Database file path or @namespace/query reference
        query: SQL query to execute
        params: Dict of bind parameters
        limit: Optional row limit
    """
    cfg = config or {}

    raw_path = (
        cfg.get("url") or  # URL includes parameters
        cfg.get("path") or
        cfg.get("address")
    )

    if not raw_path:
        raise ValueError("Database path required")

    # Profile container mode: List queries in namespace
    if raw_path.startswith("@") and "/" not in raw_path[1:]:
        # Bare @namespace - list available queries
        namespace = raw_path[1:]
        yield from _list_profile_queries(namespace)
        return

    # Profile query mode: Load from @namespace/query
    if raw_path.startswith("@") and "/" in raw_path[1:]:
        # Parse parameters from URL if present
        import urllib.parse

        if "?" in raw_path:
            ref_part, query_string = raw_path.split("?", 1)
            url_params = urllib.parse.parse_qs(query_string)
            # Flatten lists to single values
            url_params = {k: v[0] if len(v) == 1 else v for k, v in url_params.items()}
        else:
            ref_part = raw_path
            url_params = {}

        # Load profile
        db_path, query, meta = _load_profile(ref_part)

        # Get params from config and merge with URL params
        config_params = cfg.get("params") or {}
        params = {**url_params, **config_params}  # config params override URL params

        # Optional parameter pattern: Inject NULL for declared but missing parameters
        # This enables SQL patterns like: ($param IS NULL OR column = $param)
        declared_params = _extract_declared_params(query)
        for param in declared_params:
            if param not in params:
                params[param] = None
    # Direct mode: Parse duckdb:// address or file path
    else:
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
        # Container mode: List tables (for inspect command)
        elif not query:
            yield from _list_tables(db_path)
            return

    # Handle limit
    limit = cfg.get("limit")
    if limit:
        query = _apply_limit(query, limit)

    # Execute query
    conn = None
    try:
        conn = duckdb.connect(db_path, read_only=True)

        # Convert :param to $param for consistency (only parameter tokens, not all colons)
        # Negative lookbehind (?<!:) ensures we don't match :: cast operators
        # Only match identifiers starting with letter/underscore to avoid time literals
        query = re.sub(r"(?<!:):([a-zA-Z_]\w*)", r"$\1", query)

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
    sys.stderr.flush()

    parser = argparse.ArgumentParser(description="JN DuckDB plugin")
    parser.add_argument("--mode", required=True, choices=["read", "write", "inspect-profiles"])
    parser.add_argument("--path", help="Database path or duckdb:// URL or @namespace/query")
    parser.add_argument("--query", help="SQL query")
    parser.add_argument("--limit", type=int, help="Row limit")
    parser.add_argument("address", nargs="?", help="Alternative to --path")

    # Parse --param-* arguments
    args, unknown = parser.parse_known_args()

    # If address was captured as positional, add it to unknown args
    if args.address:
        unknown.append(args.address)

    # DEBUG
    sys.stderr.flush()

    params = {}
    i = 0
    while i < len(unknown):
        if unknown[i].startswith("--param-"):
            param_name = unknown[i][8:]  # Strip '--param-'
            sys.stderr.flush()
            if i + 1 < len(unknown):
                params[param_name] = unknown[i + 1]
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

    # Handle inspect-profiles mode
    if args.mode == "inspect-profiles":
        try:
            for profile in inspect_profiles():
                print(json.dumps(profile), flush=True)
        except Exception as e:
            sys.stderr.write(f"Error listing profiles: {e}\n")
            sys.exit(1)
        sys.exit(0)

    # Build config for read mode
    config = {"params": params}
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
