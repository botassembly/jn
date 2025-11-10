"""Test format plugins in isolation."""

import subprocess
import json
from pathlib import Path

# Test data directory
DATA_DIR = Path(__file__).parent / 'data'
PLUGINS_DIR = Path(__file__).parent.parent / 'src' / 'jn' / 'plugins' / 'formats'


def run_plugin(plugin_name, mode, input_data=None):
    """Run a plugin with given mode and input data."""
    plugin_path = PLUGINS_DIR / plugin_name
    cmd = ['python3', str(plugin_path), '--mode', mode]

    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise AssertionError(f"Plugin failed: {result.stderr}")

    return result.stdout


def test_csv_read():
    """Test CSV reader converts to NDJSON."""
    with open(DATA_DIR / 'people.csv') as f:
        csv_data = f.read()

    output = run_plugin('csv_.py', 'read', csv_data)
    lines = [line for line in output.strip().split('\n') if line]

    # Should have 5 data rows
    assert len(lines) == 5

    # First record should be Alice
    first = json.loads(lines[0])
    assert first['name'] == 'Alice'
    assert first['age'] == '30'
    assert first['city'] == 'NYC'


def test_csv_write():
    """Test CSV writer converts from NDJSON."""
    ndjson = '{"name":"Alice","age":"30"}\n{"name":"Bob","age":"25"}\n'

    output = run_plugin('csv_.py', 'write', ndjson)
    lines = output.strip().split('\n')

    # Should have header + 2 data rows
    assert len(lines) == 3
    assert lines[0] == 'name,age'
    assert 'Alice,30' in lines[1]


def test_json_read_array():
    """Test JSON reader handles arrays."""
    json_data = '[{"name":"Alice"},{"name":"Bob"}]'

    output = run_plugin('json_.py', 'read', json_data)
    lines = [line for line in output.strip().split('\n') if line]

    assert len(lines) == 2
    assert json.loads(lines[0])['name'] == 'Alice'


def test_json_read_ndjson():
    """Test JSON reader handles NDJSON."""
    ndjson = '{"name":"Alice"}\n{"name":"Bob"}\n'

    output = run_plugin('json_.py', 'read', ndjson)
    lines = [line for line in output.strip().split('\n') if line]

    assert len(lines) == 2


def test_json_write():
    """Test JSON writer creates array."""
    ndjson = '{"name":"Alice"}\n{"name":"Bob"}\n'

    output = run_plugin('json_.py', 'write', ndjson)
    data = json.loads(output)

    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]['name'] == 'Alice'


def test_yaml_read():
    """Test YAML reader handles multi-document."""
    yaml_data = "name: Alice\n---\nname: Bob\n"

    output = run_plugin('yaml_.py', 'read', yaml_data)
    lines = [line for line in output.strip().split('\n') if line]

    assert len(lines) == 2
    assert json.loads(lines[0])['name'] == 'Alice'


def test_yaml_write():
    """Test YAML writer creates multi-document."""
    ndjson = '{"name":"Alice"}\n{"name":"Bob"}\n'

    output = run_plugin('yaml_.py', 'write', ndjson)

    # Should contain document separator
    assert '---' in output
    assert 'Alice' in output
    assert 'Bob' in output


def test_csv_roundtrip():
    """Test CSV read → write roundtrip."""
    with open(DATA_DIR / 'people.csv') as f:
        original = f.read()

    # Read to NDJSON
    ndjson = run_plugin('csv_.py', 'read', original)

    # Write back to CSV
    csv_output = run_plugin('csv_.py', 'write', ndjson)

    # Should have same number of lines
    assert len(csv_output.strip().split('\n')) == len(original.strip().split('\n'))

    # Should contain same names
    assert 'Alice' in csv_output
    assert 'Carol' in csv_output
