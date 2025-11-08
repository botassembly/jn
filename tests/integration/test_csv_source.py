"""End-to-end tests for CSV source adapter."""

import json

from jn.cli import app
from tests.helpers import (
    add_converter,
    add_exec_target,
    add_pipeline,
    init_config,
)


def test_csv_source_basic(runner, tmp_path):
    """Test basic CSV source with default settings."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create test CSV file
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,age\nAlice,30\nBob,25\n")

        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create CSV source
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "file",
                "users",
                "--path",
                str(csv_file),
                "--adapter",
                "csv",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pass-through converter
        add_converter(runner, jn_path, "pass", ".")

        # Create cat target
        add_exec_target(runner, jn_path, "cat", ["cat"])

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "csv_to_json",
            ["source:users", "converter:pass", "target:cat"],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "csv_to_json", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}
        assert json.loads(lines[1]) == {"name": "Bob", "age": "25"}


def test_csv_source_with_jq_filter(runner, tmp_path):
    """Test CSV source with jq filtering."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create test CSV file
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(
            "product,revenue,quantity\nWidget A,1500.50,15\nWidget B,2300.75,23\nWidget C,800.25,8\n"
        )

        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create CSV source
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "file",
                "sales",
                "--path",
                str(csv_file),
                "--adapter",
                "csv",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create converter to extract product names
        add_converter(runner, jn_path, "get_products", ".product")

        # Create cat target
        add_exec_target(runner, jn_path, "cat", ["cat"])

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "list_products",
            ["source:sales", "converter:get_products", "target:cat"],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "list_products", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0]) == "Widget A"
        assert json.loads(lines[1]) == "Widget B"
        assert json.loads(lines[2]) == "Widget C"


def test_csv_source_tsv(runner, tmp_path):
    """Test TSV (tab-separated) source."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create test TSV file
        tsv_file = tmp_path / "test.tsv"
        tsv_file.write_text("name\tage\nAlice\t30\nBob\t25\n")

        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create TSV source with tab delimiter
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "file",
                "users",
                "--path",
                str(tsv_file),
                "--adapter",
                "csv",
                "--csv-delimiter",
                "\t",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pass-through converter
        add_converter(runner, jn_path, "pass", ".")

        # Create cat target
        add_exec_target(runner, jn_path, "cat", ["cat"])

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "tsv_pipeline",
            ["source:users", "converter:pass", "target:cat"],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "tsv_pipeline", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}
        assert json.loads(lines[1]) == {"name": "Bob", "age": "25"}


def test_csv_source_pipe_separated(runner, tmp_path):
    """Test pipe-separated values."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create test PSV file
        psv_file = tmp_path / "test.psv"
        psv_file.write_text("name|age\nAlice|30\nBob|25\n")

        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create PSV source with pipe delimiter
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "file",
                "users",
                "--path",
                str(psv_file),
                "--adapter",
                "csv",
                "--csv-delimiter",
                "|",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pass-through converter
        add_converter(runner, jn_path, "pass", ".")

        # Create cat target
        add_exec_target(runner, jn_path, "cat", ["cat"])

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "psv_pipeline",
            ["source:users", "converter:pass", "target:cat"],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "psv_pipeline", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"name": "Alice", "age": "30"}


def test_csv_source_with_quoted_fields(runner, tmp_path):
    """Test CSV with quoted fields containing delimiters."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create CSV with quoted fields
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            'name,city\n"Smith, John","New York, NY"\n"Doe, Jane","Los Angeles, CA"\n'
        )

        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create CSV source
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "file",
                "users",
                "--path",
                str(csv_file),
                "--adapter",
                "csv",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pass-through converter
        add_converter(runner, jn_path, "pass", ".")

        # Create cat target
        add_exec_target(runner, jn_path, "cat", ["cat"])

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "csv_pipeline",
            ["source:users", "converter:pass", "target:cat"],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "csv_pipeline", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {
            "name": "Smith, John",
            "city": "New York, NY",
        }
        assert json.loads(lines[1]) == {
            "name": "Doe, Jane",
            "city": "Los Angeles, CA",
        }


def test_csv_source_aggregation(runner, tmp_path):
    """Test CSV source with aggregation using jq."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create test CSV file
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(
            "product,revenue\nWidget A,1500\nWidget B,2300\nWidget C,800\n"
        )

        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create CSV source
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "file",
                "sales",
                "--path",
                str(csv_file),
                "--adapter",
                "csv",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create converter to sum revenue
        # Note: jq slurp mode collects all inputs into array
        add_converter(
            runner, jn_path, "sum_revenue", "[.revenue | tonumber] | add"
        )

        # Create cat target
        add_exec_target(runner, jn_path, "cat", ["cat"])

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "total_revenue",
            ["source:sales", "converter:sum_revenue", "target:cat"],
        )

        # Run pipeline
        result = runner.invoke(
            app, ["run", "total_revenue", "--jn", str(jn_path)]
        )

        assert result.exit_code == 0
        # Each row produces a sum, so we get 3 lines with the revenue value
        lines = result.output.strip().split("\n")
        # The converter extracts revenue and converts to number for each row
        assert len(lines) == 3
        assert json.loads(lines[0]) == 1500
        assert json.loads(lines[1]) == 2300
        assert json.loads(lines[2]) == 800
