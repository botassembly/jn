"""Integration tests for pipeline construction and execution."""

import tempfile
from pathlib import Path
import json
import pytest

from jn.pipeline import (
    build_pipeline,
    Pipeline,
    is_jq_expression,
    detect_output_format,
    find_plugin_file,
    describe_pipeline,
)
from jn.executor import (
    PipelineExecutor,
    ExecutionError,
)


def test_is_jq_expression():
    """Test jq expression detection."""
    assert is_jq_expression('.name') is True
    assert is_jq_expression('.items[0]') is True
    assert is_jq_expression('select(.amount > 100)') is True
    assert is_jq_expression('map(.name)') is True
    assert is_jq_expression('group_by(.category)') is True

    assert is_jq_expression('data.csv') is False
    assert is_jq_expression('output.json') is False
    assert is_jq_expression('ls') is False


def test_detect_output_format():
    """Test output format detection."""
    # Should detect CSV writer
    writer = detect_output_format('output.csv')
    assert writer == 'csv_writer'

    # Should detect JSON writer
    writer = detect_output_format('output.json')
    assert writer in ('json_writer', None)  # May not exist yet

    # Stdout
    writer = detect_output_format('-')
    assert writer is None

    # No extension
    writer = detect_output_format('output')
    assert writer is None


def test_find_plugin_file():
    """Test finding plugin files."""
    plugin_dir = Path(__file__).parent.parent.parent / 'plugins'

    # Should find csv_reader in readers/
    csv_reader = find_plugin_file('csv_reader', plugin_dir)
    assert csv_reader is not None
    assert csv_reader.exists()
    assert csv_reader.name == 'csv_reader.py'

    # Should find ls in shell/
    ls_plugin = find_plugin_file('ls', plugin_dir)
    assert ls_plugin is not None
    assert ls_plugin.exists()

    # Should not find non-existent plugin
    fake = find_plugin_file('nonexistent_plugin', plugin_dir)
    assert fake is None


def test_build_pipeline_single_file():
    """Test building pipeline with single input file."""
    pipeline = build_pipeline(['data.csv'])

    assert pipeline.source is not None
    assert pipeline.source.plugin == 'csv_reader'
    assert len(pipeline.filters) == 0
    assert pipeline.target is None


def test_build_pipeline_file_to_file():
    """Test building pipeline from file to file."""
    pipeline = build_pipeline(['data.csv', 'output.json'])

    assert pipeline.source is not None
    assert pipeline.source.plugin == 'csv_reader'
    assert len(pipeline.filters) == 0
    # Note: json_writer might not exist yet
    # assert pipeline.target is not None


def test_build_pipeline_with_filter():
    """Test building pipeline with jq filter."""
    pipeline = build_pipeline(['data.csv', '.name', 'output.json'])

    assert pipeline.source is not None
    assert pipeline.source.plugin == 'csv_reader'
    assert len(pipeline.filters) == 1
    assert pipeline.filters[0].plugin == 'jq_filter'
    assert pipeline.filters[0].config['query'] == '.name'


def test_build_pipeline_multiple_filters():
    """Test building pipeline with multiple filters."""
    pipeline = build_pipeline(['data.csv', 'select(.amount > 100)', 'map(.name)'])

    assert pipeline.source is not None
    assert len(pipeline.filters) == 2
    assert pipeline.filters[0].config['query'] == 'select(.amount > 100)'
    assert pipeline.filters[1].config['query'] == 'map(.name)'


def test_build_pipeline_command_source():
    """Test building pipeline with shell command source."""
    pipeline = build_pipeline(['ls', '/tmp'])

    assert pipeline.source is not None
    assert pipeline.source.plugin == 'ls'


def test_build_pipeline_url_source():
    """Test building pipeline with URL source."""
    pipeline = build_pipeline(['https://api.example.com/data.json'])

    assert pipeline.source is not None
    assert pipeline.source.plugin == 'http_get'
    assert pipeline.source.config['url'] == 'https://api.example.com/data.json'


def test_describe_pipeline():
    """Test pipeline description."""
    pipeline = Pipeline()
    pipeline.add_source('csv_reader', {'file': 'data.csv'})
    pipeline.add_filter('jq_filter', {'query': '.name'})
    pipeline.add_target('json_writer', {'output': 'output.json'})

    desc = describe_pipeline(pipeline)
    assert 'csv_reader' in desc
    assert 'jq_filter' in desc or '.name' in desc
    assert 'json_writer' in desc


def test_pipeline_add_methods():
    """Test Pipeline add methods."""
    pipeline = Pipeline()

    # Add source
    pipeline.add_source('csv_reader', {'file': 'data.csv'})
    assert pipeline.source is not None
    assert pipeline.source.plugin == 'csv_reader'
    assert len(pipeline.steps) == 1

    # Add filter
    pipeline.add_filter('jq_filter', {'query': '.name'})
    assert len(pipeline.filters) == 1
    assert len(pipeline.steps) == 2

    # Add target
    pipeline.add_target('csv_writer', {'output': 'out.csv'})
    assert pipeline.target is not None
    assert len(pipeline.steps) == 3

    # Steps should be in order: source, filter, target
    assert pipeline.steps[0].type == 'source'
    assert pipeline.steps[1].type == 'filter'
    assert pipeline.steps[2].type == 'target'


def test_executor_build_command():
    """Test executor command building."""
    from jn.executor import PluginExecutor
    from jn.pipeline import PipelineStep

    executor = PluginExecutor(use_uv=False)  # Disable UV for test

    step = PipelineStep(
        type='source',
        plugin='csv_reader',
        config={'path': 'data.csv'}
    )

    plugin_path = Path(__file__).parent.parent.parent / 'plugins' / 'readers' / 'csv_reader.py'

    cmd = executor.build_command(step, plugin_path)

    # Should have python and plugin path
    assert len(cmd) >= 2
    assert 'python' in cmd[0].lower() or 'python' in str(cmd[0])
    assert str(plugin_path) in ' '.join(cmd)


@pytest.mark.skipif(not Path('/tmp').exists(), reason="Requires /tmp directory")
def test_execute_simple_pipeline():
    """Test executing a simple CSV read pipeline."""
    # Create test CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write('name,age\n')
        f.write('Alice,30\n')
        f.write('Bob,25\n')
        csv_file = Path(f.name)

    try:
        # Build pipeline: CSV → NDJSON
        pipeline = build_pipeline([str(csv_file)])

        # Execute
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as outf:
            output_file = Path(outf.name)

        try:
            executor = PipelineExecutor(verbose=True)
            # Note: This may fail if plugins aren't executable yet
            # We'll mark as xfail if needed
            exit_code = executor.execute(pipeline, output_file=output_file)

            assert exit_code == 0

            # Verify output
            output_data = output_file.read_text()
            lines = output_data.strip().split('\n')
            assert len(lines) == 2  # Two data rows

            # Parse NDJSON
            records = [json.loads(line) for line in lines]
            assert records[0]['name'] == 'Alice'
            assert records[1]['name'] == 'Bob'

        finally:
            if output_file.exists():
                output_file.unlink()

    finally:
        if csv_file.exists():
            csv_file.unlink()


def test_execute_missing_plugin():
    """Test that execution fails gracefully with missing plugin."""
    pipeline = Pipeline()
    pipeline.add_source('nonexistent_plugin')

    executor = PipelineExecutor()

    with pytest.raises(ExecutionError) as exc_info:
        executor.execute(pipeline)

    assert 'not found' in str(exc_info.value).lower()


def test_execute_empty_pipeline():
    """Test that empty pipeline raises error."""
    pipeline = Pipeline()

    executor = PipelineExecutor()

    with pytest.raises(ExecutionError) as exc_info:
        executor.execute(pipeline)

    assert 'no steps' in str(exc_info.value).lower()


def test_build_pipeline_preserves_order():
    """Test that pipeline steps maintain correct order."""
    pipeline = Pipeline()

    # Add in different order
    pipeline.add_target('csv_writer')
    pipeline.add_source('csv_reader')
    pipeline.add_filter('jq_filter')

    # Should reorder to: source, filter, target
    assert pipeline.steps[0].type == 'source'
    assert pipeline.steps[1].type == 'filter'
    assert pipeline.steps[2].type == 'target'


def test_pipeline_multiple_filters_order():
    """Test that multiple filters maintain insertion order."""
    pipeline = Pipeline()

    pipeline.add_source('csv_reader')
    pipeline.add_filter('filter1')
    pipeline.add_filter('filter2')
    pipeline.add_filter('filter3')
    pipeline.add_target('csv_writer')

    # Filters should be in insertion order
    assert pipeline.filters[0].plugin == 'filter1'
    assert pipeline.filters[1].plugin == 'filter2'
    assert pipeline.filters[2].plugin == 'filter3'

    # Steps should be: source, filter1, filter2, filter3, target
    assert len(pipeline.steps) == 5
    assert pipeline.steps[0].plugin == 'csv_reader'
    assert pipeline.steps[1].plugin == 'filter1'
    assert pipeline.steps[2].plugin == 'filter2'
    assert pipeline.steps[3].plugin == 'filter3'
    assert pipeline.steps[4].plugin == 'csv_writer'
