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

    # Set JN_HOME - reads fresh from environment now
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

    # Set JN_HOME - reads fresh from environment now
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


@pytest.fixture
def test_db_with_status(tmp_path):
    """Create a test DuckDB database with status column for optional param tests."""
    db_path = tmp_path / "test_status.duckdb"

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
conn.execute('CREATE TABLE users (id INT, name VARCHAR, status VARCHAR)')
conn.execute("INSERT INTO users VALUES (1, 'Alice', 'active')")
conn.execute("INSERT INTO users VALUES (2, 'Bob', 'inactive')")
conn.execute("INSERT INTO users VALUES (3, 'Charlie', 'active')")
conn.close()
""",
        ],
        check=True,
        capture_output=True,
    )

    return db_path


def test_duckdb_optional_param_no_value(
    invoke, tmp_path, test_db_with_status, monkeypatch
):
    """Test optional parameter pattern - no param provided returns all rows."""
    # Create profile with optional parameter pattern
    profile_dir = tmp_path / "profiles" / "duckdb" / "testdb"
    profile_dir.mkdir(parents=True)

    meta = {
        "driver": "duckdb",
        "path": str(test_db_with_status),
    }
    (profile_dir / "_meta.json").write_text(json.dumps(meta))

    # Use optional parameter pattern: ($param IS NULL OR column = $param)
    (profile_dir / "by-status.sql").write_text(
        """-- Users with optional status filter
-- Parameters: status
SELECT * FROM users WHERE ($status IS NULL OR status = $status);
"""
    )

    monkeypatch.setenv("JN_HOME", str(tmp_path))

    # Test without parameter - should return all 3 users
    res = invoke(["cat", "@testdb/by-status"])
    assert res.exit_code == 0, f"Failed: {res.output}"

    lines = [
        line
        for line in res.output.strip().split("\n")
        if line and not line.startswith("Installed")
    ]
    assert len(lines) == 3, f"Expected 3 rows, got {len(lines)}: {lines}"


def test_duckdb_optional_param_with_value(
    invoke, tmp_path, test_db_with_status, monkeypatch
):
    """Test optional parameter pattern - param provided filters rows."""
    # Create profile with optional parameter pattern
    profile_dir = tmp_path / "profiles" / "duckdb" / "testdb"
    profile_dir.mkdir(parents=True)

    meta = {
        "driver": "duckdb",
        "path": str(test_db_with_status),
    }
    (profile_dir / "_meta.json").write_text(json.dumps(meta))

    (profile_dir / "by-status.sql").write_text(
        """-- Users with optional status filter
-- Parameters: status
SELECT * FROM users WHERE ($status IS NULL OR status = $status);
"""
    )

    monkeypatch.setenv("JN_HOME", str(tmp_path))

    # Test with status=active - should return 2 users (Alice and Charlie)
    res = invoke(["cat", "@testdb/by-status?status=active"])
    assert res.exit_code == 0, f"Failed: {res.output}"

    lines = [
        line
        for line in res.output.strip().split("\n")
        if line and not line.startswith("Installed")
    ]
    assert len(lines) == 2, f"Expected 2 rows, got {len(lines)}: {lines}"

    # Verify the correct users
    names = [json.loads(line)["name"] for line in lines]
    assert "Alice" in names
    assert "Charlie" in names
    assert "Bob" not in names


def test_duckdb_optional_param_multiple(invoke, tmp_path, monkeypatch):
    """Test multiple optional parameters."""
    db_path = tmp_path / "multi.duckdb"

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
conn.execute('CREATE TABLE treatments (id INT, regimen VARCHAR, os_months INT)')
conn.execute("INSERT INTO treatments VALUES (1, 'FOLFOX', 24)")
conn.execute("INSERT INTO treatments VALUES (2, 'FOLFIRI', 18)")
conn.execute("INSERT INTO treatments VALUES (3, 'FOLFOX', 12)")
conn.execute("INSERT INTO treatments VALUES (4, 'FOLFIRI', 30)")
conn.close()
""",
        ],
        check=True,
        capture_output=True,
    )

    profile_dir = tmp_path / "profiles" / "duckdb" / "genie"
    profile_dir.mkdir(parents=True)

    meta = {"driver": "duckdb", "path": str(db_path)}
    (profile_dir / "_meta.json").write_text(json.dumps(meta))

    (profile_dir / "treatment.sql").write_text(
        """-- Treatment query with optional filters
-- Parameters: regimen, min_survival
SELECT * FROM treatments
WHERE ($regimen IS NULL OR regimen = $regimen)
  AND ($min_survival IS NULL OR os_months >= $min_survival);
"""
    )

    monkeypatch.setenv("JN_HOME", str(tmp_path))

    # Test 1: No params - all 4 rows
    res = invoke(["cat", "@genie/treatment"])
    assert res.exit_code == 0
    lines = [
        line
        for line in res.output.strip().split("\n")
        if line and not line.startswith("Installed")
    ]
    assert len(lines) == 4

    # Test 2: Only regimen - filter by regimen
    res = invoke(["cat", "@genie/treatment?regimen=FOLFOX"])
    assert res.exit_code == 0
    lines = [
        line
        for line in res.output.strip().split("\n")
        if line and not line.startswith("Installed")
    ]
    assert len(lines) == 2

    # Test 3: Both params - filter by both
    res = invoke(["cat", "@genie/treatment?regimen=FOLFIRI&min_survival=20"])
    assert res.exit_code == 0
    lines = [
        line
        for line in res.output.strip().split("\n")
        if line and not line.startswith("Installed")
    ]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["regimen"] == "FOLFIRI"
    assert row["os_months"] == 30
