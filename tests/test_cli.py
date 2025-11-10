"""Test JN CLI end-to-end with real subprocess execution."""

import subprocess
import json
import tempfile
from pathlib import Path

# Test data directory
DATA_DIR = Path(__file__).parent / 'data'


def run_jn(*args, input_data=None):
    """Run jn CLI command with given args."""
    cmd = ['uv', 'run', 'jn'] + list(args)

    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent  # Run from project root
    )

    if result.returncode != 0:
        raise AssertionError(f"jn command failed: {result.stderr}")

    return result.stdout


def test_cat_csv_to_stdout():
    """Test: jn cat file.csv → NDJSON to stdout."""
    output = run_jn('cat', str(DATA_DIR / 'people.csv'))
    lines = [line for line in output.strip().split('\n') if line]

    # Should output 5 NDJSON records
    assert len(lines) == 5

    # First record should be Alice
    first = json.loads(lines[0])
    assert first['name'] == 'Alice'
    assert first['salary'] == '80000'


def test_cat_csv_to_json():
    """Test: jn cat file.csv file.json → JSON array."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / 'output.json'

        run_jn('cat', str(DATA_DIR / 'people.csv'), str(output_file))

        # Read output file
        with open(output_file) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 5
        assert data[0]['name'] == 'Alice'


def test_cat_csv_to_yaml():
    """Test: jn cat file.csv file.yaml → multi-doc YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / 'output.yaml'

        run_jn('cat', str(DATA_DIR / 'people.csv'), str(output_file))

        # Read output file
        with open(output_file) as f:
            content = f.read()

        # Should contain document separators
        assert content.count('---') == 4  # 5 docs = 4 separators
        assert 'Alice' in content
        assert 'Carol' in content


def test_pipeline_with_filter():
    """Test: jn cat | jq filter | jn put."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / 'filtered.json'

        # Get NDJSON from CSV
        ndjson = run_jn('cat', str(DATA_DIR / 'people.csv'))

        # Filter with jq: salary > 80000
        filtered = run_jn('filter', 'select(.salary == "95000" or .salary == "90000")', input_data=ndjson)

        # Write to JSON file
        run_jn('put', str(output_file), input_data=filtered)

        # Read result
        with open(output_file) as f:
            data = json.load(f)

        # Should only have Bob (95000) and Eve (90000)
        assert len(data) == 2
        names = {r['name'] for r in data}
        assert names == {'Bob', 'Eve'}


def test_head_command():
    """Test: jn cat | jn head N."""
    # Get first 2 records
    output = run_jn('cat', str(DATA_DIR / 'people.csv'))
    result = subprocess.run(
        ['uv', 'run', 'jn', 'head', '2'],
        input=output,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    lines = [line for line in result.stdout.strip().split('\n') if line]
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first['name'] == 'Alice'


def test_tail_command():
    """Test: jn cat | jn tail N."""
    # Get last 2 records
    output = run_jn('cat', str(DATA_DIR / 'people.csv'))
    result = subprocess.run(
        ['uv', 'run', 'jn', 'tail', '2'],
        input=output,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    lines = [line for line in result.stdout.strip().split('\n') if line]
    assert len(lines) == 2

    last = json.loads(lines[-1])
    assert last['name'] == 'Eve'


def test_run_command():
    """Test: jn run input.csv output.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / 'output.json'

        run_jn('run', str(DATA_DIR / 'people.csv'), str(output_file))

        # Read output
        with open(output_file) as f:
            data = json.load(f)

        assert len(data) == 5
        assert data[0]['name'] == 'Alice'
