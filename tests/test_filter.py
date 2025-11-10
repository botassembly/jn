"""Test jq filter plugin."""

import subprocess
import json
from pathlib import Path

FILTER_PLUGIN = Path(__file__).parent.parent / 'src' / 'jn' / 'plugins' / 'filters' / 'jq_.py'


def test_jq_field_select():
    """Test jq can select a field."""
    ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'

    result = subprocess.run(
        ['python3', str(FILTER_PLUGIN), '--query', '.name'],
        input=ndjson,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split('\n') if line]

    # jq returns primitives, which we wrap in {value: ...}
    assert len(lines) == 2
    assert json.loads(lines[0])['value'] == 'Alice'
    assert json.loads(lines[1])['value'] == 'Bob'


def test_jq_filter_condition():
    """Test jq can filter by condition."""
    ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'

    result = subprocess.run(
        ['python3', str(FILTER_PLUGIN), '--query', 'select(.age > 25)'],
        input=ndjson,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.strip().split('\n') if line]

    # Should only return Alice
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record['name'] == 'Alice'
    assert record['age'] == 30


def test_jq_transform():
    """Test jq can transform objects."""
    ndjson = '{"name":"Alice","age":30}\n'

    result = subprocess.run(
        ['python3', str(FILTER_PLUGIN), '--query', '{user: .name, years: .age}'],
        input=ndjson,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    record = json.loads(result.stdout.strip())

    assert record['user'] == 'Alice'
    assert record['years'] == 30
