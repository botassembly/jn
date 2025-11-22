"""Tests for DuckDB plugin and profiles."""

import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def test_db(tmp_path):
    """Create a test DuckDB database."""
    db_path = tmp_path / "test.duckdb"

    # Create database with sample data
    subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "duckdb",
            "python",
            "-c",
            f"""
import duckdb
conn = duckdb.connect('{db_path}')
conn.execute('CREATE TABLE users (id INT, name VARCHAR)')
conn.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob')")
conn.close()
""",
        ],
        check=True,
        capture_output=True,
    )

    return db_path


def test_duckdb_direct_table(invoke, test_db):
    """Test direct DuckDB table query."""
    res = invoke(["cat", f"duckdb://{test_db}/users"])
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 2

    # Check first row
    row1 = json.loads(lines[0])
    assert row1["id"] == 1
    assert row1["name"] == "Alice"


def test_duckdb_direct_query(invoke, test_db):
    """Test direct DuckDB SQL query."""
    query = "SELECT * FROM users WHERE id = 1"
    res = invoke(["cat", f"duckdb://{test_db}?query={query}"])
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 1

    row = json.loads(lines[0])
    assert row["id"] == 1
    assert row["name"] == "Alice"


def test_duckdb_inspect_database(invoke, test_db):
    """Test inspecting DuckDB database tables."""
    res = invoke(["inspect", f"duckdb://{test_db}", "--format", "json"])
    assert res.exit_code == 0

    result = json.loads(res.output)
    assert result["transport"] == "duckdb"
    assert len(result["tables"]) == 1
    assert result["tables"][0]["name"] == "users"
    assert result["tables"][0]["columns"] == 2


def test_duckdb_profile_query(invoke, tmp_path, test_db, monkeypatch):
    """Test DuckDB profile query."""
    # Create profile directory
    profile_dir = tmp_path / "profiles" / "duckdb" / "testdb"
    profile_dir.mkdir(parents=True)

    # Create meta file
    meta = {
        "driver": "duckdb",
        "path": str(test_db),
        "description": "Test database",
    }
    (profile_dir / "_meta.json").write_text(json.dumps(meta))

    # Create SQL query
    (profile_dir / "all-users.sql").write_text(
        "-- All users\nSELECT * FROM users;"
    )

    # Set JN_HOME
    monkeypatch.setenv("JN_HOME", str(tmp_path))

    # Test the query
    res = invoke(["cat", "@testdb/all-users"])
    assert res.exit_code == 0

    lines = [
        line
        for line in res.output.strip().split("\n")
        if line and not line.startswith("Installed")
    ]
    assert len(lines) == 2


def test_duckdb_profile_parameterized(invoke, tmp_path, test_db, monkeypatch):
    """Test DuckDB profile with parameters."""
    # Create profile
    profile_dir = tmp_path / "profiles" / "duckdb" / "testdb"
    profile_dir.mkdir(parents=True)

    meta = {
        "driver": "duckdb",
        "path": str(test_db),
    }
    (profile_dir / "_meta.json").write_text(json.dumps(meta))

    (profile_dir / "by-id.sql").write_text(
        "-- User by ID\n-- Parameters: user_id\nSELECT * FROM users WHERE id = $user_id;"
    )

    monkeypatch.setenv("JN_HOME", str(tmp_path))

    res = invoke(["cat", "@testdb/by-id?user_id=1"])
    assert res.exit_code == 0

    lines = [
        line
        for line in res.output.strip().split("\n")
        if line and not line.startswith("Installed")
    ]
    assert len(lines) == 1

    row = json.loads(lines[0])
    assert row["id"] == 1
    assert row["name"] == "Alice"


def test_duckdb_profile_list(invoke, tmp_path, test_db, monkeypatch):
    """Test listing DuckDB profiles.

    TODO: This test currently fails due to module-level caching in context.py.
    The cache is populated by the session fixture before individual tests run,
    and clearing it in-test doesn't affect CliRunner subprocess imports.
    The code works correctly when tested manually. Fix requires refactoring
    context.py to not use module-level caching or passing JN_HOME to subprocesses.
    """
    # Create JN_HOME structure
    (tmp_path / "plugins").mkdir(
        parents=True
    )  # Empty plugins dir for fallback
    profile_dir = tmp_path / "profiles" / "duckdb" / "testdb"
    profile_dir.mkdir(parents=True)

    meta = {"driver": "duckdb", "path": str(test_db)}
    (profile_dir / "_meta.json").write_text(json.dumps(meta))
    (profile_dir / "query1.sql").write_text("SELECT 1;")
    (profile_dir / "query2.sql").write_text("SELECT 2;")

    # Set JN_HOME and change directory so plugin subprocess uses tmp_path
    monkeypatch.setenv("JN_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # Clear the context cache so resolve_home() picks up the new JN_HOME
    import jn.context

    jn.context._cached_home = None

    res = invoke(["profile", "list", "--type", "duckdb"])
    assert res.exit_code == 0
    assert "@testdb/query1" in res.output
    assert "@testdb/query2" in res.output


def test_duckdb_inspect_profile(invoke, tmp_path, test_db, monkeypatch):
    """Test inspecting DuckDB profile.

    TODO: This test currently fails due to module-level caching in context.py.
    See test_duckdb_profile_list for details.
    """
    # Create JN_HOME structure
    (tmp_path / "plugins").mkdir(
        parents=True
    )  # Empty plugins dir for fallback
    profile_dir = tmp_path / "profiles" / "duckdb" / "testdb"
    profile_dir.mkdir(parents=True)

    meta = {"driver": "duckdb", "path": str(test_db)}
    (profile_dir / "_meta.json").write_text(json.dumps(meta))
    (profile_dir / "users.sql").write_text(
        "-- Get users\n-- Parameters: limit\nSELECT * FROM users LIMIT $limit;"
    )

    # Set JN_HOME and change directory so plugin subprocess uses tmp_path
    monkeypatch.setenv("JN_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # Clear the context cache so resolve_home() picks up the new JN_HOME
    import jn.context

    jn.context._cached_home = None

    res = invoke(["inspect", "@testdb", "--format", "json"])
    assert res.exit_code == 0

    result = json.loads(res.output)
    assert result["transport"] == "duckdb-profile"
    assert len(result["queries"]) == 1
    assert result["queries"][0]["name"] == "users"
    assert "limit" in result["queries"][0]["params"]
