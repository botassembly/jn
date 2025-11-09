"""JN CLI - Agent-native ETL with JSON pipelines.

Command-line interface for discovering, inspecting, and executing plugins.
"""

import sys
import json
from pathlib import Path
from typing import Optional, List

import click

from .discovery import discover_plugins, parse_plugin_metadata, get_plugin_paths
from .registry import get_registry
from .pipeline import build_pipeline, describe_pipeline
from .executor import PipelineExecutor, ExecutionError


# Version info
__version__ = "4.0.0-alpha1"


@click.group()
@click.version_option(version=__version__, prog_name="jn")
@click.option('--debug', is_flag=True, help='Enable debug output')
@click.pass_context
def main(ctx, debug):
    """JN - Agent-native ETL with JSON pipelines.

    A lightweight ETL framework where JSON Lines is the universal data format.
    Compose plugins via Unix pipes to build data processing pipelines.

    Examples:
        jn discover                      # List all plugins
        jn show csv_reader               # Show plugin details
        jn run data.csv output.json      # Execute pipeline
    """
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug


@main.command()
@click.option('--type', 'plugin_type', help='Filter by plugin type (source, filter, target)')
@click.option('--category', help='Filter by category (readers, writers, filters, shell)')
@click.option('--changed-since', type=float, help='Show plugins modified after timestamp')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def discover(plugin_type, category, changed_since, output_json, verbose):
    """Discover available plugins.

    Lists all plugins found in the search paths, with optional filtering.

    Examples:
        jn discover                      # List all plugins
        jn discover --type source        # Only source plugins
        jn discover --category readers   # Only reader plugins
        jn discover --json               # Machine-readable output
    """
    # Discover plugins
    if plugin_type:
        plugins = discover_plugins(plugin_types={plugin_type})
    else:
        plugins = discover_plugins()

    # Filter by category
    if category:
        plugins = {
            name: meta for name, meta in plugins.items()
            if meta.category == category
        }

    # Filter by modification time
    if changed_since:
        plugins = {
            name: meta for name, meta in plugins.items()
            if meta.mtime > changed_since
        }

    if output_json:
        # JSON output
        result = {
            name: {
                'name': meta.name,
                'path': meta.path,
                'type': meta.type,
                'handles': meta.handles,
                'command': meta.command,
                'streaming': meta.streaming,
                'dependencies': meta.dependencies,
                'category': meta.category,
                'mtime': meta.mtime,
            }
            for name, meta in plugins.items()
        }
        click.echo(json.dumps(result, indent=2))
    else:
        # Human-readable output
        if not plugins:
            click.echo("No plugins found.")
            return

        click.echo(f"Found {len(plugins)} plugin(s):\n")

        for name, meta in sorted(plugins.items()):
            if verbose:
                click.echo(f"  {name}")
                click.echo(f"    Type: {meta.type or 'unknown'}")
                click.echo(f"    Category: {meta.category or 'unknown'}")
                if meta.handles:
                    click.echo(f"    Handles: {', '.join(meta.handles)}")
                if meta.command:
                    click.echo(f"    Command: {meta.command}")
                if meta.dependencies:
                    click.echo(f"    Dependencies: {', '.join(meta.dependencies)}")
                click.echo(f"    Path: {meta.path}")
                click.echo()
            else:
                # Compact output
                info_parts = []
                if meta.type:
                    info_parts.append(meta.type)
                if meta.category:
                    info_parts.append(f"category={meta.category}")
                if meta.handles:
                    info_parts.append(f"handles={','.join(meta.handles)}")
                if meta.command:
                    info_parts.append(f"cmd={meta.command}")

                info_str = f" ({', '.join(info_parts)})" if info_parts else ""
                click.echo(f"  {name}{info_str}")


@main.command()
@click.argument('plugin_name')
@click.option('--examples', is_flag=True, help='Show plugin examples')
@click.option('--test', is_flag=True, help='Run plugin tests')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def show(plugin_name, examples, test, output_json):
    """Show details about a specific plugin.

    Displays plugin metadata, documentation, and optionally examples or test results.

    Examples:
        jn show csv_reader               # Show plugin details
        jn show csv_reader --examples    # Show usage examples
        jn show csv_reader --test        # Run plugin tests
    """
    # Find plugin
    all_plugins = discover_plugins()

    if plugin_name not in all_plugins:
        click.echo(f"Error: Plugin '{plugin_name}' not found.", err=True)
        click.echo(f"\nAvailable plugins:", err=True)
        for name in sorted(all_plugins.keys()):
            click.echo(f"  {name}", err=True)
        sys.exit(1)

    plugin_meta = all_plugins[plugin_name]

    if test:
        # Run plugin tests
        click.echo(f"Running tests for {plugin_name}...\n")
        plugin_path = Path(plugin_meta.path)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(plugin_path), '--test'],
            capture_output=True,
            text=True
        )

        click.echo(result.stderr)
        if result.stdout:
            click.echo(result.stdout)

        sys.exit(result.returncode)

    if output_json:
        # JSON output
        result = {
            'name': plugin_meta.name,
            'path': plugin_meta.path,
            'type': plugin_meta.type,
            'handles': plugin_meta.handles,
            'command': plugin_meta.command,
            'streaming': plugin_meta.streaming,
            'dependencies': plugin_meta.dependencies,
            'category': plugin_meta.category,
            'mtime': plugin_meta.mtime,
        }

        if examples:
            # Try to get examples by running plugin
            plugin_path = Path(plugin_meta.path)
            import subprocess
            proc_result = subprocess.run(
                [sys.executable, str(plugin_path), '--examples'],
                capture_output=True,
                text=True
            )
            if proc_result.returncode == 0:
                try:
                    result['examples'] = json.loads(proc_result.stdout)
                except json.JSONDecodeError:
                    result['examples'] = proc_result.stdout

        click.echo(json.dumps(result, indent=2))
    else:
        # Human-readable output
        click.echo(f"Plugin: {plugin_meta.name}")
        click.echo(f"Type: {plugin_meta.type or 'unknown'}")
        click.echo(f"Category: {plugin_meta.category or 'unknown'}")
        click.echo(f"Path: {plugin_meta.path}")

        if plugin_meta.handles:
            click.echo(f"Handles: {', '.join(plugin_meta.handles)}")

        if plugin_meta.command:
            click.echo(f"Command: {plugin_meta.command}")

        if plugin_meta.streaming:
            click.echo(f"Streaming: Yes")

        if plugin_meta.dependencies:
            click.echo(f"\nDependencies:")
            for dep in plugin_meta.dependencies:
                click.echo(f"  - {dep}")

        if examples:
            click.echo(f"\nExamples:")
            plugin_path = Path(plugin_meta.path)
            import subprocess
            result = subprocess.run(
                [sys.executable, str(plugin_path), '--examples'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                try:
                    examples_data = json.loads(result.stdout)
                    for i, example in enumerate(examples_data, 1):
                        click.echo(f"\n  Example {i}: {example.get('description', 'N/A')}")
                        if 'input' in example:
                            click.echo(f"    Input: {example['input'][:60]}...")
                        if 'expected' in example:
                            click.echo(f"    Expected: {example['expected']}")
                except json.JSONDecodeError:
                    click.echo(result.stdout)


@main.command()
@click.argument('args', nargs=-1, required=True)
@click.option('--verbose', '-v', is_flag=True, help='Show execution details')
@click.option('--dry-run', is_flag=True, help='Show pipeline without executing')
def run(args, verbose, dry_run):
    """Execute a data processing pipeline.

    Automatically builds and executes a pipeline from the given arguments.
    Arguments are interpreted as: source [filters...] [target]

    Examples:
        jn run data.csv                          # CSV to NDJSON (stdout)
        jn run data.csv output.json              # CSV to JSON file
        jn run data.csv '.name' output.json      # CSV → filter → JSON
        jn run ls /tmp output.csv                # Shell command → CSV
        jn run https://api.com/data output.csv   # HTTP → CSV
    """
    try:
        # Build pipeline
        pipeline = build_pipeline(list(args))

        if not pipeline.steps:
            click.echo("Error: Could not build pipeline from arguments.", err=True)
            click.echo(f"Arguments: {args}", err=True)
            sys.exit(1)

        # Show pipeline description
        desc = describe_pipeline(pipeline)
        if verbose or dry_run:
            click.echo(f"Pipeline: {desc}", err=True)
            click.echo(f"Steps: {len(pipeline.steps)}", err=True)
            for i, step in enumerate(pipeline.steps, 1):
                click.echo(f"  {i}. {step.plugin} ({step.type})", err=True)
            click.echo(err=True)

        if dry_run:
            # Just show pipeline, don't execute
            return

        # Execute pipeline
        executor = PipelineExecutor(verbose=verbose)
        exit_code = executor.execute(pipeline)

        sys.exit(exit_code)

    except ExecutionError as e:
        click.echo(f"Execution error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.option('--user', is_flag=True, help='Show user plugin path')
@click.option('--project', is_flag=True, help='Show project plugin path')
@click.option('--package', is_flag=True, help='Show package plugin path')
@click.option('--all', 'show_all', is_flag=True, help='Show all paths')
def paths(user, project, package, show_all):
    """Show plugin search paths.

    Displays the directories searched for plugins, in priority order.
    """
    plugin_paths = get_plugin_paths()

    if not any([user, project, package, show_all]):
        # Default: show all
        show_all = True

    if show_all:
        click.echo("Plugin search paths (in priority order):")
        for i, path in enumerate(plugin_paths, 1):
            exists = "✓" if path.exists() else "✗"
            click.echo(f"  {i}. {exists} {path}")
    else:
        # Show specific paths
        if user:
            user_path = Path.home() / '.jn' / 'plugins'
            exists = "exists" if user_path.exists() else "not found"
            click.echo(f"User: {user_path} ({exists})")

        if project:
            project_path = Path.cwd() / '.jn' / 'plugins'
            exists = "exists" if project_path.exists() else "not found"
            click.echo(f"Project: {project_path} ({exists})")

        if package:
            package_path = Path(__file__).parent.parent.parent / 'plugins'
            exists = "exists" if package_path.exists() else "not found"
            click.echo(f"Package: {package_path} ({exists})")


@main.command()
@click.argument('extension')
def which(extension):
    """Show which plugin handles a file extension.

    Examples:
        jn which .csv      # Show CSV reader plugin
        jn which .json     # Show JSON reader plugin
    """
    registry = get_registry()

    if not extension.startswith('.'):
        extension = f'.{extension}'

    plugin = registry.get_plugin_for_extension(extension)

    if plugin:
        click.echo(f"{extension} → {plugin}")

        # Show plugin details
        all_plugins = discover_plugins()
        if plugin in all_plugins:
            meta = all_plugins[plugin]
            click.echo(f"  Type: {meta.type}")
            click.echo(f"  Path: {meta.path}")
    else:
        click.echo(f"No plugin found for extension: {extension}", err=True)
        sys.exit(1)


@main.command()
@click.argument('source')
@click.option('--limit', '-n', type=int, help='Limit output to N records')
@click.option('--verbose', '-v', is_flag=True, help='Show processing details')
def cat(source, limit, verbose):
    """Read a source and output NDJSON to stdout.

    Auto-detects the source type and uses the appropriate plugin:
    - Files: Uses extension-based reader (e.g., .csv → csv_reader)
    - URLs: Uses http_get plugin
    - Commands: Executes as shell command plugin

    Examples:
        jn cat data.csv              # Read CSV file
        jn cat https://api.com/data  # Fetch from URL
        jn cat data.json | head -5   # Pipe to other commands
    """
    from pathlib import Path
    import subprocess

    # Determine source type
    is_url = source.startswith(('http://', 'https://', 'ftp://', 'ftps://'))
    is_file = Path(source).exists()

    if verbose:
        click.echo(f"Processing source: {source}", err=True)

    # Build a simple pipeline for the source
    executor = PipelineExecutor()

    if is_url:
        # Use http_get plugin
        plugin_name = 'http_get'
        all_plugins = discover_plugins()

        if plugin_name not in all_plugins:
            click.echo(f"Error: http_get plugin not found", err=True)
            sys.exit(1)

        plugin_path = Path(all_plugins[plugin_name].path)

        if verbose:
            click.echo(f"Using plugin: {plugin_name}", err=True)

        # Execute plugin with URL as argument
        cmd = [sys.executable, str(plugin_path), source]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            click.echo(f"Error: {result.stderr}", err=True)
            sys.exit(result.returncode)

        output = result.stdout

    elif is_file:
        # Use extension-based reader
        path = Path(source)
        extension = path.suffix

        if not extension:
            click.echo(f"Error: Cannot determine file type (no extension)", err=True)
            sys.exit(1)

        registry = get_registry()
        plugin_name = registry.get_plugin_for_extension(extension)

        if not plugin_name:
            click.echo(f"Error: No plugin found for extension: {extension}", err=True)
            click.echo(f"Supported extensions: {', '.join(sorted(registry.extension_map.keys()))}", err=True)
            sys.exit(1)

        all_plugins = discover_plugins()
        if plugin_name not in all_plugins:
            click.echo(f"Error: Plugin '{plugin_name}' not found", err=True)
            sys.exit(1)

        plugin_path = Path(all_plugins[plugin_name].path)

        if verbose:
            click.echo(f"Using plugin: {plugin_name}", err=True)

        # Execute plugin with file content on stdin
        with open(path, 'r') as f:
            file_content = f.read()

        cmd = [sys.executable, str(plugin_path)]
        result = subprocess.run(cmd, input=file_content, capture_output=True, text=True)

        if result.returncode != 0:
            click.echo(f"Error: {result.stderr}", err=True)
            sys.exit(result.returncode)

        output = result.stdout

    else:
        # Treat as command - check if we have a matching shell plugin
        all_plugins = discover_plugins(plugin_types={'source'})

        # Look for shell plugins that match the command
        cmd_name = source.split()[0] if ' ' in source else source
        matching_plugin = None

        for name, meta in all_plugins.items():
            if meta.command == cmd_name:
                matching_plugin = name
                break

        if matching_plugin:
            plugin_path = Path(all_plugins[matching_plugin].path)

            if verbose:
                click.echo(f"Using plugin: {matching_plugin}", err=True)

            # Execute plugin with command arguments
            cmd_args = source.split()[1:] if ' ' in source else []
            cmd = [sys.executable, str(plugin_path)] + cmd_args
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                click.echo(f"Error: {result.stderr}", err=True)
                sys.exit(result.returncode)

            output = result.stdout
        else:
            click.echo(f"Error: No plugin found for command '{cmd_name}'", err=True)
            click.echo(f"\nAvailable shell commands:", err=True)
            for name, meta in all_plugins.items():
                if meta.category == 'shell':
                    click.echo(f"  {meta.command}", err=True)
            sys.exit(1)

    # Output results (with optional limit)
    if limit:
        lines = output.strip().split('\n')
        for i, line in enumerate(lines):
            if i >= limit:
                break
            click.echo(line)
    else:
        click.echo(output, nl=False)


@main.command()
@click.argument('output', required=False, default='-')
@click.option('--format', '-f', help='Output format (csv, json, etc). Auto-detected from extension.')
@click.option('--indent', type=int, default=2, help='JSON indent level (default: 2)')
@click.option('--delimiter', default=',', help='CSV delimiter (default: ,)')
@click.option('--no-header', is_flag=True, help='Skip CSV header row')
@click.option('--verbose', '-v', is_flag=True, help='Show processing details')
def put(output, format, indent, delimiter, no_header, verbose):
    """Write NDJSON from stdin to a file.

    Reads NDJSON records from stdin and writes to the specified output format.
    Format is auto-detected from file extension or can be specified explicitly.

    Examples:
        jn cat data.csv | jn put output.json    # CSV to JSON
        jn cat api | jn put data.csv             # API to CSV
        echo '{"a":1}' | jn put -                # Format to stdout
    """
    from pathlib import Path
    import subprocess
    import json

    # Read NDJSON from stdin
    records = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            click.echo(f"Error: Invalid JSON on line: {line[:50]}...", err=True)
            click.echo(f"  {e}", err=True)
            sys.exit(1)

    if verbose:
        click.echo(f"Read {len(records)} records", err=True)

    # Determine output format
    if output == '-':
        # Output to stdout - default to JSON
        output_format = format or 'json'
        use_stdout = True
    else:
        path = Path(output)
        extension = path.suffix

        if format:
            output_format = format
        elif extension:
            # Map extension to format
            ext_format_map = {
                '.csv': 'csv',
                '.tsv': 'tsv',
                '.json': 'json',
                '.jsonl': 'ndjson',
                '.ndjson': 'ndjson',
            }
            output_format = ext_format_map.get(extension, 'json')
        else:
            output_format = 'json'

        use_stdout = False

    if verbose:
        click.echo(f"Output format: {output_format}", err=True)

    # Find appropriate writer plugin
    # Map format to writer plugin name
    format_writer_map = {
        'csv': 'csv_writer',
        'tsv': 'csv_writer',
        'json': 'json_writer',
        'ndjson': 'json_writer',
    }

    plugin_name = format_writer_map.get(output_format)

    if not plugin_name:
        click.echo(f"Error: No writer plugin found for format: {output_format}", err=True)
        click.echo(f"Supported formats: {', '.join(format_writer_map.keys())}", err=True)
        sys.exit(1)

    all_plugins = discover_plugins(plugin_types={'target'})
    if plugin_name not in all_plugins:
        click.echo(f"Error: Plugin '{plugin_name}' not found", err=True)
        sys.exit(1)

    plugin_path = Path(all_plugins[plugin_name].path)

    if verbose:
        click.echo(f"Using plugin: {plugin_name}", err=True)

    # Prepare plugin arguments based on format
    cmd = [sys.executable, str(plugin_path)]

    # CSV/TSV writer writes to stdout, we redirect to file
    if output_format in ['csv', 'tsv']:
        if delimiter != ',':
            cmd.extend(['--delimiter', delimiter])
        if no_header:
            cmd.append('--no-header')
    # JSON writer supports --output flag
    elif output_format == 'json':
        cmd.extend(['--indent', str(indent)])
        if not use_stdout:
            cmd.extend(['--output', output])
    elif output_format == 'ndjson':
        # NDJSON just passes through
        pass

    # Convert records back to NDJSON for plugin input
    ndjson_input = '\n'.join(json.dumps(record) for record in records)

    # Execute writer plugin
    result = subprocess.run(
        cmd,
        input=ndjson_input,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        click.echo(f"Error: {result.stderr}", err=True)
        sys.exit(result.returncode)

    # Handle output
    if use_stdout:
        click.echo(result.stdout, nl=False)
    elif output_format in ['csv', 'tsv', 'ndjson']:
        # These writers output to stdout, write to file ourselves
        with open(output, 'w') as f:
            f.write(result.stdout)
        if verbose:
            click.echo(f"Wrote {len(records)} records to {output}", err=True)
    else:
        # JSON writer handles file output itself
        if verbose:
            click.echo(f"Wrote {len(records)} records to {output}", err=True)


if __name__ == '__main__':
    main()
