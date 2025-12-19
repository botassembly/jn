"""Integration tests for the db tool.

These tests verify the db tool works correctly by invoking it
through the jn orchestrator with subprocess.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


# Path to jn binary
JN_BIN = Path(__file__).parent.parent.parent / "dist" / "bin" / "jn"


def run_db(args: list, cwd: Path = None, input_data: str = None) -> tuple:
    """Run db tool command and return (returncode, stdout, stderr)."""
    if not JN_BIN.exists():
        pytest.skip("jn not built (run 'make build')")

    cmd = [str(JN_BIN), "tool", "db"] + args
    env = os.environ.copy()

    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture
def db_dir(tmp_path):
    """Create a temp directory for db operations."""
    return tmp_path


@pytest.fixture
def initialized_db(db_dir):
    """Create an initialized database with sample data."""
    code, stdout, stderr = run_db(["init"], cwd=db_dir)
    assert code == 0, f"init failed: {stderr}"

    # Insert sample records
    run_db(["insert", '{"name":"Alice","age":30}'], cwd=db_dir)
    run_db(["insert", '{"name":"Bob","age":25}'], cwd=db_dir)
    run_db(["insert", '{"name":"Charlie","age":35}'], cwd=db_dir)

    return db_dir


# =============================================================================
# Basic CRUD Tests
# =============================================================================

class TestDbInit:
    """Tests for db init command."""

    def test_init_creates_file(self, db_dir):
        """db init should create the database file."""
        code, stdout, stderr = run_db(["init"], cwd=db_dir)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        db_file = db_dir / ".db.jsonl"
        assert db_file.exists()

    def test_init_idempotent(self, db_dir):
        """db init should be idempotent."""
        run_db(["init"], cwd=db_dir)
        code, stdout, stderr = run_db(["init"], cwd=db_dir)
        assert code == 0


class TestDbInsert:
    """Tests for db insert command."""

    def test_insert_creates_record(self, db_dir):
        """db insert should create a record with _meta."""
        run_db(["init"], cwd=db_dir)

        code, stdout, stderr = run_db(
            ["insert", '{"name":"Alice","age":30}'],
            cwd=db_dir
        )
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        # Parse the output record
        output = stdout + stderr
        lines = [l for l in output.strip().split("\n") if l.startswith("{")]
        assert len(lines) >= 1

        record = json.loads(lines[0])
        assert record["name"] == "Alice"
        assert record["age"] == 30
        assert "_meta" in record
        assert record["_meta"]["id"] == 1
        assert record["_meta"]["version"] == 1
        assert record["_meta"]["deleted"] == False

    def test_insert_auto_increments_id(self, db_dir):
        """db insert should auto-increment IDs."""
        run_db(["init"], cwd=db_dir)
        run_db(["insert", '{"x":1}'], cwd=db_dir)

        code, stdout, stderr = run_db(["insert", '{"x":2}'], cwd=db_dir)
        assert code == 0

        output = stdout + stderr
        lines = [l for l in output.strip().split("\n") if l.startswith("{")]
        record = json.loads(lines[0])
        assert record["_meta"]["id"] == 2

    def test_insert_rejects_non_object(self, db_dir):
        """db insert should reject non-object JSON."""
        run_db(["init"], cwd=db_dir)

        code, stdout, stderr = run_db(
            ["insert", '"just a string"'],
            cwd=db_dir
        )
        assert code != 0
        assert "object" in (stdout + stderr).lower()


class TestDbGet:
    """Tests for db get command."""

    def test_get_returns_record(self, initialized_db):
        """db get should return record by ID."""
        code, stdout, stderr = run_db(["get", "2"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        record = json.loads(stdout.strip())
        assert record["name"] == "Bob"
        assert record["_meta"]["id"] == 2

    def test_get_nonexistent_fails(self, initialized_db):
        """db get should fail for nonexistent ID."""
        code, stdout, stderr = run_db(["get", "999"], cwd=initialized_db)
        assert code != 0
        assert "not found" in (stdout + stderr).lower()


class TestDbList:
    """Tests for db list command."""

    def test_list_returns_all_active(self, initialized_db):
        """db list should return all active records."""
        code, stdout, stderr = run_db(["list"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 3

    def test_list_excludes_deleted(self, initialized_db):
        """db list should exclude deleted records by default."""
        run_db(["delete", "2"], cwd=initialized_db)

        code, stdout, stderr = run_db(["list"], cwd=initialized_db)
        assert code == 0

        lines = [l for l in stdout.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 2

        names = [json.loads(l)["name"] for l in lines]
        assert "Bob" not in names

    def test_list_include_deleted(self, initialized_db):
        """db list --include-deleted should show all records."""
        run_db(["delete", "2"], cwd=initialized_db)

        code, stdout, stderr = run_db(["list", "--include-deleted"], cwd=initialized_db)
        assert code == 0

        lines = [l for l in stdout.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 3

    def test_list_only_deleted(self, initialized_db):
        """db list --only-deleted should show only deleted records."""
        run_db(["delete", "2"], cwd=initialized_db)

        code, stdout, stderr = run_db(["list", "--only-deleted"], cwd=initialized_db)
        assert code == 0

        lines = [l for l in stdout.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 1
        assert json.loads(lines[0])["name"] == "Bob"


class TestDbQuery:
    """Tests for db query command."""

    def test_query_select_filter(self, initialized_db):
        """db query should filter records with zq expression."""
        code, stdout, stderr = run_db(
            ["query", "select(.age > 28)"],
            cwd=initialized_db
        )
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 2

        names = [json.loads(l)["name"] for l in lines]
        assert "Alice" in names
        assert "Charlie" in names
        assert "Bob" not in names


# =============================================================================
# Mutation Tests
# =============================================================================

class TestDbUpdate:
    """Tests for db update command."""

    def test_update_modifies_field(self, initialized_db):
        """db update should modify record fields."""
        code, stdout, stderr = run_db(
            ["update", "1", ".age:=31"],
            cwd=initialized_db
        )
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        code, stdout, _ = run_db(["get", "1"], cwd=initialized_db)
        record = json.loads(stdout.strip())
        assert record["age"] == 31
        assert record["_meta"]["version"] == 2

    def test_update_preserves_immutable_meta(self, initialized_db):
        """db update should preserve immutable _meta fields."""
        # Get original record
        code, stdout, _ = run_db(["get", "1"], cwd=initialized_db)
        original = json.loads(stdout.strip())

        # Try to change _meta.id
        run_db(["update", "1", "._meta.id:=999"], cwd=initialized_db)

        code, stdout, _ = run_db(["get", "1"], cwd=initialized_db)
        updated = json.loads(stdout.strip())

        # ID should still be 1 (protected in safe mode)
        assert updated["_meta"]["id"] == 1
        assert updated["_meta"]["created_at"] == original["_meta"]["created_at"]


class TestDbSet:
    """Tests for db set command."""

    def test_set_field(self, initialized_db):
        """db set should set a field value."""
        code, stdout, stderr = run_db(
            ["set", "1", "age", "32"],
            cwd=initialized_db
        )
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        code, stdout, _ = run_db(["get", "1"], cwd=initialized_db)
        record = json.loads(stdout.strip())
        assert record["age"] == 32

    def test_set_rejects_meta(self, initialized_db):
        """db set should reject _meta field changes without --unsafe."""
        code, stdout, stderr = run_db(
            ["set", "1", "_meta.id", "999"],
            cwd=initialized_db
        )
        assert code != 0
        assert "unsafe" in (stdout + stderr).lower()


class TestDbUnset:
    """Tests for db unset command."""

    def test_unset_removes_field(self, initialized_db):
        """db unset should remove a field."""
        # First add a field
        run_db(["update", "1", ".temp:=42"], cwd=initialized_db)

        code, stdout, _ = run_db(["get", "1"], cwd=initialized_db)
        assert "temp" in json.loads(stdout.strip())

        # Now unset it
        code, stdout, stderr = run_db(["unset", "1", "temp"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        code, stdout, _ = run_db(["get", "1"], cwd=initialized_db)
        assert "temp" not in json.loads(stdout.strip())


# =============================================================================
# Soft Delete Tests
# =============================================================================

class TestDbDelete:
    """Tests for db delete command."""

    def test_delete_sets_deleted_flag(self, initialized_db):
        """db delete should set deleted flag."""
        code, stdout, stderr = run_db(["delete", "2"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        code, stdout, _ = run_db(["get", "--include-deleted", "2"], cwd=initialized_db)
        record = json.loads(stdout.strip())
        assert record["_meta"]["deleted"] == True
        assert record["_meta"]["deleted_at"] is not None

    def test_delete_increments_version(self, initialized_db):
        """db delete should increment version."""
        code, stdout, _ = run_db(["get", "2"], cwd=initialized_db)
        original_version = json.loads(stdout.strip())["_meta"]["version"]

        run_db(["delete", "2"], cwd=initialized_db)

        code, stdout, _ = run_db(["get", "--include-deleted", "2"], cwd=initialized_db)
        new_version = json.loads(stdout.strip())["_meta"]["version"]
        assert new_version == original_version + 1


class TestDbUndelete:
    """Tests for db undelete command."""

    def test_undelete_restores_record(self, initialized_db):
        """db undelete should restore a deleted record."""
        run_db(["delete", "2"], cwd=initialized_db)

        # Need --include-deleted to see deleted records for undelete
        code, stdout, stderr = run_db(["--include-deleted", "undelete", "2"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        code, stdout, _ = run_db(["get", "2"], cwd=initialized_db)
        record = json.loads(stdout.strip())
        assert record["_meta"]["deleted"] == False
        assert record["_meta"]["deleted_at"] is None


class TestDbPurge:
    """Tests for db purge command."""

    def test_purge_removes_deleted(self, initialized_db):
        """db purge should permanently remove deleted records."""
        run_db(["delete", "2"], cwd=initialized_db)

        code, stdout, stderr = run_db(["purge"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        # Record should be completely gone
        code, stdout, stderr = run_db(["get", "--include-deleted", "2"], cwd=initialized_db)
        assert code != 0
        assert "not found" in (stdout + stderr).lower()

    def test_purge_preserves_active(self, initialized_db):
        """db purge should not affect active records."""
        run_db(["delete", "2"], cwd=initialized_db)
        run_db(["purge"], cwd=initialized_db)

        code, stdout, _ = run_db(["list"], cwd=initialized_db)
        lines = [l for l in stdout.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 2


# =============================================================================
# Inspection Tests
# =============================================================================

class TestDbCount:
    """Tests for db count command."""

    def test_count_shows_stats(self, initialized_db):
        """db count should show record counts."""
        run_db(["delete", "2"], cwd=initialized_db)

        code, stdout, stderr = run_db(["count"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        output = stdout + stderr
        assert "total: 3" in output
        assert "active: 2" in output
        assert "deleted: 1" in output


class TestDbStats:
    """Tests for db stats command."""

    def test_stats_shows_summary(self, initialized_db):
        """db stats should show database summary."""
        code, stdout, stderr = run_db(["stats"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        output = stdout + stderr
        assert "Total" in output or "total" in output
        assert "3" in output


class TestDbCheck:
    """Tests for db check command."""

    def test_check_passes_valid_db(self, initialized_db):
        """db check should pass for valid database."""
        code, stdout, stderr = run_db(["check"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        output = stdout + stderr
        assert "OK" in output or "ok" in output.lower()
        assert "Errors:   0" in output or "errors: 0" in output.lower()


# =============================================================================
# Export Tests
# =============================================================================

class TestDbExport:
    """Tests for db export command."""

    def test_export_ndjson(self, initialized_db):
        """db export ndjson should output NDJSON."""
        code, stdout, stderr = run_db(["export", "ndjson"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = [l for l in stdout.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 3
        for line in lines:
            json.loads(line)  # Should not raise

    def test_export_json(self, initialized_db):
        """db export json should output JSON array."""
        code, stdout, stderr = run_db(["export", "json"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        data = json.loads(stdout.strip())
        assert isinstance(data, list)
        assert len(data) == 3

    def test_export_csv(self, initialized_db):
        """db export csv should output CSV."""
        code, stdout, stderr = run_db(["export", "csv"], cwd=initialized_db)
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        lines = stdout.strip().split("\n")
        assert len(lines) == 4  # header + 3 records
        assert "id" in lines[0]


# =============================================================================
# Schema Tests
# =============================================================================

class TestDbSchema:
    """Tests for --schema option."""

    def test_insert_with_schema(self, db_dir):
        """db insert --schema should set _meta.schema."""
        run_db(["init"], cwd=db_dir)

        code, stdout, stderr = run_db(
            ["--schema", "users", "insert", '{"name":"Alice"}'],
            cwd=db_dir
        )
        assert code == 0, f"Exit code {code}, stderr: {stderr}"

        code, stdout, _ = run_db(["get", "1"], cwd=db_dir)
        record = json.loads(stdout.strip())
        assert record["_meta"]["schema"] == "users"

    def test_list_filters_by_schema(self, db_dir):
        """db list --schema should filter by schema."""
        run_db(["init"], cwd=db_dir)
        run_db(["--schema", "users", "insert", '{"name":"Alice"}'], cwd=db_dir)
        run_db(["--schema", "products", "insert", '{"name":"Widget"}'], cwd=db_dir)
        run_db(["--schema", "users", "insert", '{"name":"Bob"}'], cwd=db_dir)

        code, stdout, _ = run_db(["--schema", "users", "list"], cwd=db_dir)
        lines = [l for l in stdout.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 2

        names = [json.loads(l)["name"] for l in lines]
        assert "Alice" in names
        assert "Bob" in names
        assert "Widget" not in names


# =============================================================================
# Edge Cases
# =============================================================================

class TestDbEdgeCases:
    """Edge case tests."""

    def test_empty_db_list(self, db_dir):
        """db list on empty database should succeed."""
        run_db(["init"], cwd=db_dir)

        code, stdout, stderr = run_db(["list"], cwd=db_dir)
        assert code == 0

    def test_empty_db_count(self, db_dir):
        """db count on empty database should show zeros."""
        run_db(["init"], cwd=db_dir)

        code, stdout, stderr = run_db(["count"], cwd=db_dir)
        assert code == 0
        assert "total: 0" in stdout + stderr

    def test_help_command(self, db_dir):
        """db help should show usage."""
        code, stdout, stderr = run_db(["help"], cwd=db_dir)
        assert code == 0
        output = stdout + stderr
        assert "insert" in output.lower()
        assert "delete" in output.lower()
