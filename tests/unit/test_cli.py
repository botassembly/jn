"""Tests for CLI commands."""

import json
from pathlib import Path
import tempfile

import pytest
from click.testing import CliRunner

from jn.cli import main


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


def test_cli_help(runner):
    """Test main help command."""
    result = runner.invoke(main, ['--help'])
    assert result.exit_code == 0
    assert 'JN - Agent-native ETL' in result.output
    assert 'discover' in result.output
    assert 'show' in result.output
    assert 'run' in result.output


def test_cli_version(runner):
    """Test version command."""
    result = runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert '4.0.0-alpha1' in result.output


def test_discover_command(runner):
    """Test discover command lists plugins."""
    result = runner.invoke(main, ['discover'])
    assert result.exit_code == 0
    assert 'csv_reader' in result.output
    assert 'csv_writer' in result.output
    assert 'json_reader' in result.output
    assert 'ls' in result.output


def test_discover_with_type_filter(runner):
    """Test discover with type filter."""
    result = runner.invoke(main, ['discover', '--type', 'source'])
    assert result.exit_code == 0
    # Should have source plugins
    assert 'csv_reader' in result.output or 'json_reader' in result.output


def test_discover_with_category_filter(runner):
    """Test discover with category filter."""
    result = runner.invoke(main, ['discover', '--category', 'readers'])
    assert result.exit_code == 0
    assert 'csv_reader' in result.output


def test_discover_verbose(runner):
    """Test discover with verbose output."""
    result = runner.invoke(main, ['discover', '--verbose'])
    assert result.exit_code == 0
    assert 'Type:' in result.output
    assert 'Category:' in result.output
    assert 'Path:' in result.output


def test_discover_json_output(runner):
    """Test discover with JSON output."""
    result = runner.invoke(main, ['discover', '--json'])
    assert result.exit_code == 0

    # Parse JSON
    data = json.loads(result.output)
    assert isinstance(data, dict)
    assert 'csv_reader' in data
    assert 'name' in data['csv_reader']
    assert 'path' in data['csv_reader']
    assert 'type' in data['csv_reader']


def test_show_command(runner):
    """Test show command for a plugin."""
    result = runner.invoke(main, ['show', 'csv_reader'])
    assert result.exit_code == 0
    assert 'csv_reader' in result.output
    assert 'Type:' in result.output
    assert 'Path:' in result.output


def test_show_nonexistent_plugin(runner):
    """Test show command with non-existent plugin."""
    result = runner.invoke(main, ['show', 'nonexistent_plugin'])
    assert result.exit_code == 1
    assert 'not found' in result.output


def test_show_with_examples(runner):
    """Test show command with examples."""
    result = runner.invoke(main, ['show', 'csv_reader', '--examples'])
    assert result.exit_code == 0
    assert 'csv_reader' in result.output


def test_show_json_output(runner):
    """Test show with JSON output."""
    result = runner.invoke(main, ['show', 'csv_reader', '--json'])
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data['name'] == 'csv_reader'
    assert 'type' in data
    assert 'path' in data


def test_show_with_test(runner):
    """Test show command with --test flag."""
    result = runner.invoke(main, ['show', 'csv_reader', '--test'])
    # Exit code depends on test results
    # Just check that it runs
    assert 'csv_reader' in result.output or 'test' in result.output.lower()


def test_run_command_help(runner):
    """Test run command help."""
    result = runner.invoke(main, ['run', '--help'])
    assert result.exit_code == 0
    assert 'Execute a data processing pipeline' in result.output


def test_run_command_no_args(runner):
    """Test run command with no arguments."""
    result = runner.invoke(main, ['run'])
    assert result.exit_code != 0  # Should fail without arguments


def test_run_command_dry_run(runner):
    """Test run command with --dry-run."""
    result = runner.invoke(main, ['run', 'data.csv', '--dry-run'])
    assert result.exit_code == 0
    assert 'Pipeline:' in result.output
    assert 'csv_reader' in result.output


def test_run_command_with_real_file(runner):
    """Test run command with actual file."""
    # Create test CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write('name,age\n')
        f.write('Alice,30\n')
        f.write('Bob,25\n')
        csv_file = Path(f.name)

    try:
        # Run pipeline
        result = runner.invoke(main, ['run', str(csv_file)])

        # Should succeed
        assert result.exit_code == 0

        # Should output NDJSON
        lines = result.output.strip().split('\n')
        assert len(lines) == 2

        # Parse NDJSON
        records = [json.loads(line) for line in lines]
        assert records[0]['name'] == 'Alice'
        assert records[1]['name'] == 'Bob'

    finally:
        csv_file.unlink()


def test_run_command_verbose(runner):
    """Test run command with verbose output."""
    result = runner.invoke(main, ['run', 'data.csv', '--dry-run', '--verbose'])
    assert result.exit_code == 0
    assert 'Pipeline:' in result.output
    assert 'Steps:' in result.output


def test_paths_command(runner):
    """Test paths command."""
    result = runner.invoke(main, ['paths'])
    assert result.exit_code == 0
    assert 'Plugin search paths' in result.output
    assert 'plugins' in result.output


def test_paths_user(runner):
    """Test paths --user."""
    result = runner.invoke(main, ['paths', '--user'])
    assert result.exit_code == 0
    assert 'User:' in result.output
    assert '.jn/plugins' in result.output


def test_paths_package(runner):
    """Test paths --package."""
    result = runner.invoke(main, ['paths', '--package'])
    assert result.exit_code == 0
    assert 'Package:' in result.output


def test_which_command(runner):
    """Test which command."""
    result = runner.invoke(main, ['which', '.csv'])
    assert result.exit_code == 0
    assert 'csv_reader' in result.output


def test_which_without_dot(runner):
    """Test which command without leading dot."""
    result = runner.invoke(main, ['which', 'csv'])
    assert result.exit_code == 0
    assert 'csv_reader' in result.output


def test_which_unknown_extension(runner):
    """Test which with unknown extension."""
    result = runner.invoke(main, ['which', '.unknown'])
    assert result.exit_code == 1
    assert 'No plugin found' in result.output


def test_cli_with_debug_flag(runner):
    """Test CLI with --debug flag."""
    result = runner.invoke(main, ['--debug', 'discover'])
    assert result.exit_code == 0
    # Debug flag should be stored in context
    # Actual behavior depends on implementation


def test_run_pipeline_file_to_file(runner):
    """Test run command with input and output files."""
    # Create test CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write('name,age\n')
        f.write('Alice,30\n')
        csv_file = Path(f.name)

    # Create temp output file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        output_file = Path(f.name)

    try:
        # Run pipeline (dry run since json_writer might not exist)
        result = runner.invoke(main, ['run', str(csv_file), str(output_file), '--dry-run'])

        # Should show pipeline
        assert result.exit_code == 0
        assert 'Pipeline:' in result.output

    finally:
        csv_file.unlink()
        if output_file.exists():
            output_file.unlink()


def test_discover_changed_since(runner):
    """Test discover --changed-since."""
    import time
    timestamp = time.time() - 86400  # 24 hours ago

    result = runner.invoke(main, ['discover', '--changed-since', str(timestamp)])
    assert result.exit_code == 0
    # Should show some plugins (depends on when they were modified)


def test_run_with_filter_expression(runner):
    """Test run with jq filter expression."""
    result = runner.invoke(main, ['run', 'data.csv', '.name', '--dry-run'])
    assert result.exit_code == 0
    assert 'Pipeline:' in result.output
    # Should include filter in pipeline


def test_run_with_url_source(runner):
    """Test run with URL source."""
    result = runner.invoke(main, ['run', 'https://example.com/data.json', '--dry-run'])
    assert result.exit_code == 0
    assert 'Pipeline:' in result.output
    assert 'http_get' in result.output


def test_run_with_command_source(runner):
    """Test run with shell command source."""
    result = runner.invoke(main, ['run', 'ls', '/tmp', '--dry-run'])
    assert result.exit_code == 0
    assert 'Pipeline:' in result.output
    assert 'ls' in result.output


def test_cat_csv_file(runner):
    """Test cat command with CSV file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("name,age\nAlice,30\nBob,25\n")
        f.flush()

        result = runner.invoke(main, ['cat', f.name])
        assert result.exit_code == 0

        # Should output NDJSON
        lines = result.output.strip().split('\n')
        assert len(lines) == 2

        record1 = json.loads(lines[0])
        assert record1['name'] == 'Alice'
        assert record1['age'] == '30'

        # Cleanup
        Path(f.name).unlink()


def test_cat_json_file(runner):
    """Test cat command with JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"x": 1}\n{"x": 2}\n')
        f.flush()

        result = runner.invoke(main, ['cat', f.name])
        assert result.exit_code == 0

        # Should output NDJSON
        lines = result.output.strip().split('\n')
        assert len(lines) == 2

        record1 = json.loads(lines[0])
        assert record1['x'] == 1

        # Cleanup
        Path(f.name).unlink()


def test_cat_with_limit(runner):
    """Test cat command with limit option."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("name,age\nAlice,30\nBob,25\nCharlie,35\n")
        f.flush()

        result = runner.invoke(main, ['cat', f.name, '--limit', '2'])
        assert result.exit_code == 0

        # Should only output 2 records
        lines = result.output.strip().split('\n')
        assert len(lines) == 2

        # Cleanup
        Path(f.name).unlink()


def test_cat_nonexistent_file(runner):
    """Test cat with nonexistent file."""
    result = runner.invoke(main, ['cat', '/nonexistent/file.csv'])
    assert result.exit_code != 0
    assert 'Error' in result.output


def test_cat_file_no_extension(runner):
    """Test cat with file without extension."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='', delete=False) as f:
        f.write("data")
        f.flush()

        result = runner.invoke(main, ['cat', f.name])
        assert result.exit_code != 0
        assert 'Cannot determine file type' in result.output

        # Cleanup
        Path(f.name).unlink()


def test_put_to_json(runner):
    """Test put command to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'output.json'

        # Create NDJSON input
        ndjson_input = '{"name": "Alice", "age": 30}\n{"name": "Bob", "age": 25}\n'

        result = runner.invoke(main, ['put', str(output_path)], input=ndjson_input)
        assert result.exit_code == 0

        # Verify output file
        assert output_path.exists()
        with open(output_path, 'r') as f:
            data = json.load(f)

        assert len(data) == 2
        assert data[0]['name'] == 'Alice'
        assert data[1]['name'] == 'Bob'


def test_put_to_csv(runner):
    """Test put command to CSV file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'output.csv'

        # Create NDJSON input
        ndjson_input = '{"name": "Alice", "age": 30}\n{"name": "Bob", "age": 25}\n'

        result = runner.invoke(main, ['put', str(output_path)], input=ndjson_input)
        assert result.exit_code == 0

        # Verify output file
        assert output_path.exists()
        content = output_path.read_text()

        assert 'name,age' in content
        assert 'Alice,30' in content
        assert 'Bob,25' in content


def test_put_to_stdout(runner):
    """Test put command to stdout."""
    ndjson_input = '{"x": 1}\n{"x": 2}\n'

    result = runner.invoke(main, ['put', '-', '--format', 'json'], input=ndjson_input)
    assert result.exit_code == 0

    # Should output JSON array
    output_data = json.loads(result.output)
    assert len(output_data) == 2
    assert output_data[0]['x'] == 1


def test_put_with_format_override(runner):
    """Test put with explicit format override."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use .txt extension but specify JSON format
        output_path = Path(tmpdir) / 'output.txt'

        ndjson_input = '{"x": 1}\n'

        result = runner.invoke(main, ['put', str(output_path), '--format', 'json'], input=ndjson_input)
        assert result.exit_code == 0

        # Should create JSON despite .txt extension
        assert output_path.exists()
        with open(output_path, 'r') as f:
            data = json.load(f)
        assert data[0]['x'] == 1


def test_put_with_csv_options(runner):
    """Test put with CSV delimiter option."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'output.tsv'

        ndjson_input = '{"name": "Alice", "age": 30}\n'

        result = runner.invoke(main, ['put', str(output_path), '--delimiter', '\t'], input=ndjson_input)
        assert result.exit_code == 0

        # Verify TSV format
        content = output_path.read_text()
        assert '\t' in content


def test_put_invalid_json_input(runner):
    """Test put with invalid JSON input."""
    invalid_input = 'not json\n'

    result = runner.invoke(main, ['put', '-'], input=invalid_input)
    assert result.exit_code != 0
    assert 'Invalid JSON' in result.output


def test_cat_verbose(runner):
    """Test cat command with verbose flag."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("name,age\nAlice,30\n")
        f.flush()

        result = runner.invoke(main, ['cat', f.name, '--verbose'])
        assert result.exit_code == 0
        assert 'Processing source' in result.output
        assert 'Using plugin' in result.output

        # Cleanup
        Path(f.name).unlink()


def test_put_verbose(runner):
    """Test put command with verbose flag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'output.json'

        ndjson_input = '{"x": 1}\n'

        result = runner.invoke(main, ['put', str(output_path), '--verbose'], input=ndjson_input)
        assert result.exit_code == 0
        assert 'Read 1 records' in result.output
        assert 'Wrote 1 records' in result.output
