"""Automatic pipeline construction.

Analyzes command-line arguments to build a pipeline of source → filters → target.
Uses registry to automatically select appropriate plugins.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from .registry import get_registry, resolve_plugin


def is_url(source: str) -> bool:
    """Check if source is a URL pattern."""
    return source.startswith(
        ("http://", "https://", "ftp://", "ftps://", "s3://")
    )


@dataclass
class PipelineStep:
    """A single step in the pipeline."""

    type: str  # 'source', 'filter', 'target'
    plugin: str  # Plugin name
    config: Dict[str, Any] = field(default_factory=dict)
    args: List[str] = field(default_factory=list)


@dataclass
class Pipeline:
    """A complete pipeline from source to target."""

    steps: List[PipelineStep] = field(default_factory=list)
    source: Optional[PipelineStep] = None
    filters: List[PipelineStep] = field(default_factory=list)
    target: Optional[PipelineStep] = None

    def add_source(self, plugin: str, config: Optional[Dict] = None, args: Optional[List[str]] = None) -> None:
        """Add source step to pipeline."""
        step = PipelineStep(
            type='source',
            plugin=plugin,
            config=config or {},
            args=args or []
        )
        self.source = step
        if step not in self.steps:
            self.steps.insert(0, step)

    def add_filter(self, plugin: str, config: Optional[Dict] = None, args: Optional[List[str]] = None) -> None:
        """Add filter step to pipeline."""
        step = PipelineStep(
            type='filter',
            plugin=plugin,
            config=config or {},
            args=args or []
        )
        self.filters.append(step)
        # Insert before target if it exists, otherwise append
        if self.target and self.target in self.steps:
            target_idx = self.steps.index(self.target)
            self.steps.insert(target_idx, step)
        else:
            self.steps.append(step)

    def add_target(self, plugin: str, config: Optional[Dict] = None, args: Optional[List[str]] = None) -> None:
        """Add target step to pipeline."""
        step = PipelineStep(
            type='target',
            plugin=plugin,
            config=config or {},
            args=args or []
        )
        self.target = step
        if step not in self.steps:
            self.steps.append(step)


def is_jq_expression(arg: str) -> bool:
    """Check if argument looks like a jq expression.

    Simple heuristic: starts with . or contains jq-like syntax.
    """
    if not arg:
        return False

    # Starts with dot (field access)
    if arg.startswith('.'):
        return True

    # Contains jq operators
    jq_keywords = ['select(', 'map(', 'group_by(', 'sort_by(', '|', '[', '{']
    return any(kw in arg for kw in jq_keywords)


def detect_output_format(output: str) -> Optional[str]:
    """Detect output format from file path or extension.

    Args:
        output: Output file path or format specifier

    Returns:
        Writer plugin name or None
    """
    if not output or output == '-':
        return None  # stdout, no conversion

    # Get extension
    path = Path(output)
    extension = path.suffix

    if not extension:
        return None

    # Use registry to map extension to writer plugin
    registry = get_registry()

    # Writers are registered with 'write' prefix
    writer_plugin = registry.get_plugin_for_extension(f'write{extension}')
    if writer_plugin:
        return writer_plugin

    # Fallback: try to construct plugin name
    # .csv → csv_writer, .json → json_writer
    plugin_name = f'{extension[1:]}_writer'  # Remove leading dot
    return plugin_name


def build_pipeline(args: List[str]) -> Pipeline:
    """Build pipeline from command-line arguments.

    Analyzes arguments to detect:
        1. Source (file, URL, command)
        2. Filters (jq expressions, plugin names)
        3. Target (output file/format)

    Args:
        args: Command-line arguments (e.g., ['data.csv', 'select(.amount > 100)', 'output.json'])

    Returns:
        Pipeline object ready for execution

    Examples:
        >>> build_pipeline(['data.csv'])  # Read CSV, output NDJSON
        >>> build_pipeline(['data.csv', '.name'])  # Read CSV, filter with jq
        >>> build_pipeline(['data.csv', 'output.json'])  # CSV → JSON
        >>> build_pipeline(['ls', '/tmp', 'output.csv'])  # ls → CSV
    """
    pipeline = Pipeline()

    if not args:
        return pipeline

    # First argument is usually the source
    source_arg = args[0]
    remaining_args = args[1:]

    # Check if source looks like a file path (has extension)
    # or is a URL or command
    path = Path(source_arg)
    has_extension = '.' in source_arg and path.suffix

    if is_url(source_arg):
        # URL source
        pipeline.add_source(
            plugin='http_get',
            config={'url': source_arg}
        )
    elif has_extension:
        # File source - use registry to find reader
        # (even if file doesn't exist yet, we can detect by extension)
        reader_plugin = resolve_plugin(source_arg)
        if reader_plugin:
            pipeline.add_source(
                plugin=reader_plugin,
                config={'file': source_arg}
            )
        else:
            # Unknown file type, treat as raw data
            pipeline.add_source(
                plugin='raw_reader',
                config={'file': source_arg}
            )
    else:
        # Looks like a command
        # Check if we have a plugin for this command
        cmd_plugin = resolve_plugin(source_arg)
        if cmd_plugin:
            # Known command with parser (e.g., ls, ps)
            # Collect command args from remaining_args if they don't look like filters/outputs
            cmd_args = []
            filters_start = 0
            for i, arg in enumerate(remaining_args):
                if is_jq_expression(arg) or ('.' in arg and Path(arg).suffix):
                    # This looks like a filter or output file
                    filters_start = i
                    break
                else:
                    # Command argument
                    cmd_args.append(arg)
                    filters_start = i + 1

            pipeline.add_source(
                plugin=cmd_plugin,
                config={'args': cmd_args}
            )

            # Update remaining_args to skip command args
            remaining_args = remaining_args[filters_start:]
        else:
            # Unknown command, use generic exec
            pipeline.add_source(
                plugin='generic_exec',
                config={'command': source_arg, 'args': remaining_args}
            )
            remaining_args = []  # All consumed by generic_exec

    # Process remaining arguments
    # Last argument might be target/output
    # Middle arguments are filters
    if remaining_args:
        # Check if last argument is an output file
        last_arg = remaining_args[-1]
        is_output = False

        # Heuristics for output file:
        # - Has file extension (.json, .csv, etc.)
        # - Doesn't look like a filter expression
        # - File doesn't exist yet (or we're okay overwriting)
        if '.' in last_arg and not is_jq_expression(last_arg):
            # Likely an output file
            writer_plugin = detect_output_format(last_arg)
            if writer_plugin:
                pipeline.add_target(
                    plugin=writer_plugin,
                    config={'output': last_arg}
                )
                is_output = True
                remaining_args = remaining_args[:-1]

        # Remaining args are filters
        for arg in remaining_args:
            if is_jq_expression(arg):
                # jq filter expression
                pipeline.add_filter(
                    plugin='jq_filter',
                    config={'query': arg}
                )
            else:
                # Plugin name or other filter
                # Try to resolve as plugin
                filter_plugin = resolve_plugin(arg)
                if filter_plugin:
                    pipeline.add_filter(plugin=filter_plugin)
                else:
                    # Assume it's a plugin name
                    pipeline.add_filter(plugin=arg)

    return pipeline


def pipeline_to_command(pipeline: Pipeline, plugin_dir: Optional[Path] = None) -> List[str]:
    """Convert pipeline to shell command for execution.

    Args:
        pipeline: Pipeline to convert
        plugin_dir: Directory containing plugins (default: package plugins)

    Returns:
        List of command parts that can be joined with pipes

    Example:
        >>> cmd_parts = pipeline_to_command(pipeline)
        >>> shell_cmd = ' | '.join(cmd_parts)
    """
    if plugin_dir is None:
        # Use package plugins directory
        plugin_dir = Path(__file__).parent.parent.parent / 'plugins'

    command_parts = []

    for step in pipeline.steps:
        # Find plugin file
        plugin_path = find_plugin_file(step.plugin, plugin_dir)

        if not plugin_path:
            raise ValueError(f"Plugin not found: {step.plugin}")

        # Build command for this step
        cmd_args = ['python3', str(plugin_path)]

        # Add plugin-specific arguments
        if step.type == 'source':
            # Source plugins read from file or execute command
            if 'file' in step.config:
                cmd_args.append(f"< {step.config['file']}")
            elif 'url' in step.config:
                cmd_args.extend(['--url', step.config['url']])
            elif 'command' in step.config:
                cmd_args.extend(['--command', step.config['command']])

        elif step.type == 'filter':
            # Filter plugins transform stdin → stdout
            if 'query' in step.config:
                cmd_args.extend(['--query', step.config['query']])

        elif step.type == 'target':
            # Target plugins write to file
            if 'output' in step.config:
                cmd_args.append(f"> {step.config['output']}")

        # Add custom args
        cmd_args.extend(step.args)

        command_parts.append(' '.join(cmd_args))

    return command_parts


def find_plugin_file(plugin_name: str, plugin_dir: Path) -> Optional[Path]:
    """Find plugin file by name.

    Searches in category subdirectories:
        - readers/
        - writers/
        - filters/
        - shell/
        - http/

    Args:
        plugin_name: Plugin name (e.g., 'csv_reader', 'ls')
        plugin_dir: Base plugin directory

    Returns:
        Path to plugin file or None if not found
    """
    categories = ['readers', 'writers', 'filters', 'shell', 'http']

    for category in categories:
        category_dir = plugin_dir / category
        if not category_dir.exists():
            continue

        plugin_path = category_dir / f'{plugin_name}.py'
        if plugin_path.exists():
            return plugin_path

    # Try direct path in plugin_dir
    plugin_path = plugin_dir / f'{plugin_name}.py'
    if plugin_path.exists():
        return plugin_path

    return None


def describe_pipeline(pipeline: Pipeline) -> str:
    """Generate human-readable description of pipeline.

    Args:
        pipeline: Pipeline to describe

    Returns:
        String description of pipeline flow
    """
    parts = []

    if pipeline.source:
        parts.append(f"Read from {pipeline.source.plugin}")

    for filter_step in pipeline.filters:
        if filter_step.plugin == 'jq_filter' and 'query' in filter_step.config:
            parts.append(f"Filter: {filter_step.config['query']}")
        else:
            parts.append(f"Transform with {filter_step.plugin}")

    if pipeline.target:
        parts.append(f"Write to {pipeline.target.plugin}")
    else:
        parts.append("Output NDJSON to stdout")

    return " → ".join(parts)
