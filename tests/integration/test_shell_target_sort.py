"""Integration test for shell target using sort utility.

This demonstrates using simple shell utilities like 'sort' as targets
in JN pipelines.
"""

import json

from jn.cli import app
from tests.helpers import add_converter, add_pipeline, init_config


def test_shell_target_sort_json_lines(runner, tmp_path):
    """Test using 'sort' as a shell target to sort JSON lines."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create a source that outputs unsorted JSON lines
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "unsorted_data",
                "--argv",
                "python",
                "--argv",
                "-c",
                "--argv",
                "import json\n"
                'for item in [{"name":"zebra","id":3}, {"name":"apple","id":1}, {"name":"mango","id":2}]:\n'
                "    print(json.dumps(item))",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create a converter to extract the name field for sorting
        # This creates a simple text output: one name per line
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "extract_name",
                "--expr",
                ".name",
                "--raw",  # Output raw strings, not JSON
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create a shell target that uses 'sort' utility
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "shell",
                "sort_target",
                "--cmd",
                "sort",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "sort_pipeline",
            [
                "source:unsorted_data",
                "converter:extract_name",
                "target:sort_target",
            ],
        )

        # Run the pipeline with --unsafe-shell
        result = runner.invoke(
            app,
            ["run", "sort_pipeline", "--unsafe-shell", "--jn", str(jn_path)],
        )

    assert result.exit_code == 0, f"Pipeline failed: {result.output}"
    output_lines = result.output.strip().split("\n")
    # Sort should have alphabetically sorted the names
    assert output_lines == ["apple", "mango", "zebra"]


def test_shell_target_sort_reverse(runner, tmp_path):
    """Test using 'sort -r' to reverse sort."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create source with numbers
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "numbers",
                "--argv",
                "python",
                "--argv",
                "-c",
                "--argv",
                "import json\n"
                "for n in [5, 2, 8, 1, 9]:\n"
                '    print(json.dumps({"value": n}))',
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Extract just the value
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "get_value",
                "--expr",
                ".value",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create shell target with reverse sort
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "shell",
                "reverse_sort",
                "--cmd",
                "sort -rn",  # -r for reverse, -n for numeric sort
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "reverse_sort_pipeline",
            ["source:numbers", "converter:get_value", "target:reverse_sort"],
        )

        # Run the pipeline
        result = runner.invoke(
            app,
            [
                "run",
                "reverse_sort_pipeline",
                "--unsafe-shell",
                "--jn",
                str(jn_path),
            ],
        )

    assert result.exit_code == 0, f"Pipeline failed: {result.output}"
    output_lines = result.output.strip().split("\n")
    # Should be reverse sorted numerically
    assert output_lines == ["9", "8", "5", "2", "1"]


def test_shell_target_sort_with_jq_and_uniq(runner, tmp_path):
    """Test pipeline: source → jq → sort | uniq (dedup)."""

    with runner.isolated_filesystem(temp_dir=tmp_path):
        jn_path = tmp_path / "jn.json"
        init_config(runner, jn_path)

        # Create source with duplicate data
        result = runner.invoke(
            app,
            [
                "new",
                "source",
                "exec",
                "duplicates",
                "--argv",
                "python",
                "--argv",
                "-c",
                "--argv",
                "import json\n"
                'for item in ["apple", "banana", "apple", "cherry", "banana", "apple"]:\n'
                '    print(json.dumps({"fruit": item}))',
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Extract fruit names
        result = runner.invoke(
            app,
            [
                "new",
                "converter",
                "extract_fruit",
                "--expr",
                ".fruit",
                "--raw",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create shell target that sorts and deduplicates
        result = runner.invoke(
            app,
            [
                "new",
                "target",
                "shell",
                "sort_uniq",
                "--cmd",
                "sort | uniq",
                "--jn",
                str(jn_path),
            ],
        )
        assert result.exit_code == 0

        # Create pipeline
        add_pipeline(
            runner,
            jn_path,
            "dedup_pipeline",
            [
                "source:duplicates",
                "converter:extract_fruit",
                "target:sort_uniq",
            ],
        )

        # Run the pipeline
        result = runner.invoke(
            app,
            ["run", "dedup_pipeline", "--unsafe-shell", "--jn", str(jn_path)],
        )

    assert result.exit_code == 0, f"Pipeline failed: {result.output}"
    output_lines = result.output.strip().split("\n")
    # Should have unique, sorted fruits
    assert output_lines == ["apple", "banana", "cherry"]
