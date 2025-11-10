"""JN CLI - Agent-native ETL with JSON pipelines.

Command-line interface for discovering, inspecting, and executing plugins.
"""

import sys
import os
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


# Plugin subcommand group
@main.group()
def plugin():
    """Manage and inspect plugins.

    Commands for discovering, testing, and introspecting plugins without importing them.
    All discovery is regex-based to avoid dependency installation overhead.

    Examples:
        jn plugin discover               # List all plugins
        jn plugin search csv             # Search by keyword
        jn plugin show csv_reader        # Show details
        jn plugin schema csv_reader      # Get output schema
        jn plugin test csv_reader        # Run tests
    """
    pass


@plugin.command(name='discover')
@click.option('--type', 'plugin_type', help='Filter by plugin type (source, filter, target)')
@click.option('--category', help='Filter by category (readers, writers, filters, shell)')
@click.option('--keyword', help='Filter by keyword')
@click.option('--json', 'json_output', is_flag=True, help='Output as JSON')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def plugin_discover(plugin_type, category, keyword, json_output, verbose):
    """Discover available plugins (regex-based, no imports)."""
    plugins = discover_plugins()

    # Filter
    if plugin_type:
        plugins = {k: v for k, v in plugins.items() if v.type == plugin_type}
    if category:
        plugins = {k: v for k, v in plugins.items() if v.category == category}
    if keyword:
        keyword_lower = keyword.lower()
        plugins = {k: v for k, v in plugins.items()
                   if keyword_lower in k.lower()
                   or keyword_lower in (v.description or '').lower()
                   or any(keyword_lower in kw.lower() for kw in v.keywords)}

    if json_output:
        data = {name: {
            'name': meta.name,
            'type': meta.type,
            'category': meta.category,
            'description': meta.description,
            'keywords': meta.keywords,
            'handles': meta.handles,
            'dependencies': meta.dependencies
        } for name, meta in plugins.items()}
        click.echo(json.dumps(data, indent=2))
    else:
        if not plugins:
            click.echo("No plugins found")
            return

        for name, meta in sorted(plugins.items()):
            if verbose:
                click.echo(f"\n{name}:")
                click.echo(f"  Type: {meta.type or 'N/A'}")
                click.echo(f"  Category: {meta.category or 'N/A'}")
                if meta.description:
                    click.echo(f"  Description: {meta.description}")
                if meta.keywords:
                    click.echo(f"  Keywords: {', '.join(meta.keywords)}")
                if meta.handles:
                    click.echo(f"  Handles: {', '.join(meta.handles)}")
            else:
                desc = f" - {meta.description}" if meta.description else ""
                click.echo(f"{name}{desc}")


@plugin.command(name='search')
@click.argument('keyword')
@click.option('--json', 'json_output', is_flag=True, help='Output as JSON')
def plugin_search(keyword, json_output):
    """Search plugins by keyword."""
    plugins = discover_plugins()

    keyword_lower = keyword.lower()
    matches = {k: v for k, v in plugins.items()
               if keyword_lower in k.lower()
               or keyword_lower in (v.description or '').lower()
               or any(keyword_lower in kw.lower() for kw in v.keywords)}

    if json_output:
        data = {name: {
            'name': meta.name,
            'description': meta.description,
            'keywords': meta.keywords,
            'type': meta.type,
            'category': meta.category
        } for name, meta in matches.items()}
        click.echo(json.dumps(data, indent=2))
    else:
        if not matches:
            click.echo(f"No plugins found matching '{keyword}'")
            return

        click.echo(f"Found {len(matches)} plugin(s) matching '{keyword}':\n")
        for name, meta in sorted(matches.items()):
            desc = f" - {meta.description}" if meta.description else ""
            keywords = f" [{', '.join(meta.keywords)}]" if meta.keywords else ""
            click.echo(f"{name}{desc}{keywords}")


@plugin.command(name='show')
@click.argument('name')
@click.option('--json', 'json_output', is_flag=True, help='Output as JSON')
def plugin_show(name, json_output):
    """Show detailed plugin information (regex-based)."""
    plugins = discover_plugins()

    if name not in plugins:
        click.echo(f"Plugin '{name}' not found", err=True)
        sys.exit(1)

    meta = plugins[name]

    if json_output:
        data = {
            'name': meta.name,
            'path': meta.path,
            'type': meta.type,
            'category': meta.category,
            'description': meta.description,
            'keywords': meta.keywords,
            'handles': meta.handles,
            'command': meta.command,
            'streaming': meta.streaming,
            'dependencies': meta.dependencies
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"\nPlugin: {meta.name}")
        click.echo(f"Path: {meta.path}")
        if meta.type:
            click.echo(f"Type: {meta.type}")
        if meta.category:
            click.echo(f"Category: {meta.category}")
        if meta.description:
            click.echo(f"Description: {meta.description}")
        if meta.keywords:
            click.echo(f"Keywords: {', '.join(meta.keywords)}")
        if meta.handles:
            click.echo(f"Handles: {', '.join(meta.handles)}")
        if meta.command:
            click.echo(f"Command: {meta.command}")
        click.echo(f"Streaming: {meta.streaming}")
        if meta.dependencies:
            click.echo(f"\nDependencies:")
            for dep in meta.dependencies:
                click.echo(f"  - {dep}")


@plugin.command(name='schema')
@click.argument('name')
def plugin_schema(name):
    """Get plugin output schema (invokes plugin --schema)."""
    import subprocess

    plugins = discover_plugins()

    if name not in plugins:
        click.echo(f"Plugin '{name}' not found", err=True)
        sys.exit(1)

    meta = plugins[name]
    plugin_path = Path(meta.path)

    # Invoke plugin with --schema flag
    try:
        result = subprocess.run(
            [sys.executable, str(plugin_path), '--schema'],
            capture_output=True,
            text=True,
            check=True
        )
        click.echo(result.stdout)
    except subprocess.CalledProcessError as e:
        click.echo(f"Error getting schema: {e.stderr}", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(f"Plugin file not found: {plugin_path}", err=True)
        sys.exit(1)


@plugin.command(name='test')
@click.argument('name')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def plugin_test(name, verbose):
    """Test plugin (invokes tools/jn-test-plugin)."""
    import subprocess

    plugins = discover_plugins()

    if name not in plugins:
        click.echo(f"Plugin '{name}' not found", err=True)
        sys.exit(1)

    meta = plugins[name]
    plugin_path = Path(meta.path)

    # Find jn-test-plugin tool
    # Look in: ./tools/, ../tools/, package root
    tool_paths = [
        Path.cwd() / 'tools' / 'jn-test-plugin',
        Path(__file__).parent.parent.parent / 'tools' / 'jn-test-plugin',
    ]

    test_tool = None
    for path in tool_paths:
        if path.exists():
            test_tool = path
            break

    if not test_tool:
        click.echo("Error: jn-test-plugin tool not found", err=True)
        click.echo("Expected at: tools/jn-test-plugin", err=True)
        sys.exit(1)

    # Invoke test tool
    cmd = [str(test_tool), str(plugin_path)]
    if verbose:
        cmd.append('--verbose')

    try:
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
    except FileNotFoundError:
        click.echo(f"Error: Could not execute test tool: {test_tool}", err=True)
        sys.exit(1)


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
@click.argument('plugin_type', type=click.Choice(['source', 'filter', 'target']))
@click.argument('name')
@click.option('--output-dir', '-o', default='plugins', help='Output directory (default: plugins)')
@click.option('--description', '-d', default='', help='Short description')
@click.option('--handles', help='File extensions to handle (comma-separated, e.g., .txt,.log)')
@click.option('--streaming/--no-streaming', default=True, help='Enable streaming mode')
@click.option('--force', '-f', is_flag=True, help='Overwrite existing file')
def create(plugin_type, name, output_dir, description, handles, streaming, force):
    """Create a new plugin from a template.

    Creates a plugin file from built-in templates with proper structure.

    Examples:
        jn create source my_reader --handles .txt
        jn create filter my_transform
        jn create target my_writer --handles .out
    """
    import os
    import stat
    from pathlib import Path

    # Determine template and output paths
    template_map = {
        'source': 'source_basic.py',
        'filter': 'filter_basic.py',
        'target': 'target_basic.py'
    }

    category_map = {
        'source': 'readers',
        'filter': 'filters',
        'target': 'writers'
    }

    template_name = template_map[plugin_type]
    category = category_map[plugin_type]

    # Find template file
    # Try package templates first, then project templates
    template_search_paths = [
        Path(__file__).parent.parent.parent / 'templates' / template_name,  # Project root
        Path.home() / '.jn' / 'templates' / template_name,  # User directory
    ]

    template_path = None
    for path in template_search_paths:
        if path.exists():
            template_path = path
            break

    if not template_path:
        click.echo(f"Error: Template '{template_name}' not found", err=True)
        click.echo(f"Searched paths:", err=True)
        for path in template_search_paths:
            click.echo(f"  {path}", err=True)
        sys.exit(1)

    # Determine output path
    output_base = Path(output_dir)
    if plugin_type in ['source', 'target']:
        output_path = output_base / category / f'{name}.py'
    else:
        output_path = output_base / category / f'{name}.py'

    # Check if file exists
    if output_path.exists() and not force:
        click.echo(f"Error: File already exists: {output_path}", err=True)
        click.echo(f"Use --force to overwrite", err=True)
        sys.exit(1)

    # Read template
    with open(template_path, 'r') as f:
        template_content = f.read()

    # Prepare replacements
    replacements = {
        '{{DESCRIPTION}}': description or f'{name} plugin',
        '{{LONG_DESCRIPTION}}': f'Processes data for {name}.',
        '{{DEPENDENCIES}}': '',
        '{{HANDLES}}': f'"{handles}"' if handles else '".ext"',
        '{{STREAMING}}': 'true' if streaming else 'false',
        '{{RUN_DESCRIPTION}}': f'Process data for {name}',
        '{{CONFIG_KEYS}}': 'None',
        '{{YIELDS_DESCRIPTION}}': 'Dict per record',
    }

    # Apply replacements
    output_content = template_content
    for placeholder, value in replacements.items():
        output_content = output_content.replace(placeholder, value)

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    with open(output_path, 'w') as f:
        f.write(output_content)

    # Make executable
    current_perms = output_path.stat().st_mode
    output_path.chmod(current_perms | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    click.echo(f"Created plugin: {output_path}")
    click.echo(f"\nNext steps:")
    click.echo(f"  1. Edit the plugin: {output_path}")
    click.echo(f"  2. Implement the run() function")
    click.echo(f"  3. Add test cases to examples()")
    click.echo(f"  4. Run tests: jn test {name}")


@main.command()
@click.argument('plugin_name')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def test(plugin_name, verbose):
    """Run tests for a specific plugin.

    Executes the built-in tests for a plugin by calling its test() function.

    Examples:
        jn test csv_reader
        jn test my_filter --verbose
    """
    import subprocess

    # Discover plugins
    all_plugins = discover_plugins()

    if plugin_name not in all_plugins:
        click.echo(f"Error: Plugin '{plugin_name}' not found.", err=True)
        click.echo(f"\nAvailable plugins:", err=True)
        for name in sorted(all_plugins.keys()):
            click.echo(f"  {name}", err=True)
        sys.exit(1)

    plugin_meta = all_plugins[plugin_name]
    plugin_path = Path(plugin_meta.path)

    if verbose:
        click.echo(f"Testing plugin: {plugin_name}", err=True)
        click.echo(f"Path: {plugin_path}", err=True)
        click.echo()

    # Run plugin tests
    result = subprocess.run(
        [sys.executable, str(plugin_path), '--test'],
        capture_output=True,
        text=True
    )

    # Show output
    if result.stderr:
        click.echo(result.stderr, nl=False)
    if result.stdout:
        click.echo(result.stdout, nl=False)

    sys.exit(result.returncode)


@main.command()
@click.argument('plugin_path', type=click.Path(exists=True))
@click.option('--strict', is_flag=True, help='Strict validation (fail on warnings)')
def validate(plugin_path, strict):
    """Validate a plugin file.

    Checks plugin structure, metadata, and runs basic validation.

    Examples:
        jn validate plugins/readers/my_reader.py
        jn validate my_plugin.py --strict
    """
    from pathlib import Path

    plugin_file = Path(plugin_path)

    if not plugin_file.exists():
        click.echo(f"Error: File not found: {plugin_path}", err=True)
        sys.exit(1)

    click.echo(f"Validating plugin: {plugin_file.name}")
    click.echo()

    issues = []
    warnings = []

    # Check file is executable
    if not os.access(plugin_file, os.X_OK):
        warnings.append("File is not executable (chmod +x recommended)")

    # Try to parse metadata
    try:
        meta = parse_plugin_metadata(plugin_file)
        if meta:
            click.echo(f"✓ Metadata found:")
            click.echo(f"  Type: {meta.type}")
            click.echo(f"  Category: {meta.category}")
            if meta.handles:
                click.echo(f"  Handles: {', '.join(meta.handles)}")
            if meta.command:
                click.echo(f"  Command: {meta.command}")
            click.echo(f"  Streaming: {meta.streaming}")
        else:
            issues.append("No META header found")
    except Exception as e:
        issues.append(f"Error parsing metadata: {e}")

    # Check for required functions (basic check without importing)
    content = plugin_file.read_text()

    if 'def run(' not in content:
        issues.append("Missing run() function")
    else:
        click.echo("✓ Has run() function")

    if 'def examples(' not in content:
        warnings.append("Missing examples() function (recommended)")
    else:
        click.echo("✓ Has examples() function")

    if 'def test(' not in content:
        warnings.append("Missing test() function (recommended)")
    else:
        click.echo("✓ Has test() function")

    # Check shebang
    first_line = content.split('\n')[0]
    if not first_line.startswith('#!'):
        warnings.append("Missing shebang line (#!/usr/bin/env python3)")

    # Check PEP 723 dependencies
    if '# /// script' in content and '# dependencies' in content:
        click.echo("✓ Has PEP 723 dependencies block")
    elif '# dependencies' not in content:
        warnings.append("No PEP 723 dependencies block (add if needed)")

    # Summary
    click.echo()
    if warnings:
        click.echo(f"Warnings ({len(warnings)}):")
        for warning in warnings:
            click.echo(f"  ⚠ {warning}")

    if issues:
        click.echo()
        click.echo(f"Issues ({len(issues)}):")
        for issue in issues:
            click.echo(f"  ✗ {issue}")
        sys.exit(1)
    elif strict and warnings:
        click.echo()
        click.echo("Validation failed (strict mode with warnings)")
        sys.exit(1)
    else:
        click.echo()
        click.echo("✓ Validation passed")


@main.command()
@click.argument('source')
@click.option('--limit', '-n', type=int, help='Limit output to N records')
@click.option('--verbose', '-v', is_flag=True, help='Show processing details')
def cat(source, limit, verbose):
    """Read a source and output NDJSON to stdout.

    Auto-detects the source type and uses the appropriate plugin:
    - Files: Uses extension-based reader (e.g., .csv → csv_reader, .xlsx → xlsx_reader)
    - URLs with extensions: Fetches file and parses (e.g., https://example.com/data.xlsx)
    - URLs without extensions: Uses http_get plugin (JSON APIs)
    - Commands: Executes as shell command plugin

    Examples:
        jn cat data.csv                      # Read local CSV file
        jn cat data.xlsx                     # Read local XLSX file
        jn cat https://api.com/data          # Fetch from JSON API
        jn cat https://s3.../file.xlsx       # Fetch and parse XLSX from S3
        jn cat s3://bucket/data.xlsx         # Private S3 bucket (requires AWS CLI)
        jn cat ftp://ftp.../file.xlsx        # Fetch and parse XLSX from FTP
        jn cat data.json | head -5           # Pipe to other commands
    """
    from pathlib import Path
    import subprocess

    # Determine source type
    is_url = source.startswith(('http://', 'https://', 'ftp://', 'ftps://', 's3://'))
    is_file = Path(source).exists()

    if verbose:
        click.echo(f"Processing source: {source}", err=True)

    # Build a simple pipeline for the source
    executor = PipelineExecutor()

    if is_url:
        # Check if URL has a file extension (e.g., .xlsx, .csv)
        from urllib.parse import urlparse
        parsed_url = urlparse(source)
        url_path = parsed_url.path
        extension = Path(url_path).suffix if url_path else None

        all_plugins = discover_plugins()
        registry = get_registry()

        # If URL has a file extension, fetch + parse pipeline
        if extension and extension in ['.xlsx', '.xlsm', '.csv', '.json', '.xml', '.yaml', '.toml']:
            # Step 1: Determine transport plugin
            if source.startswith('s3://'):
                transport_plugin = 's3_get'
            elif source.startswith(('ftp://', 'ftps://')):
                transport_plugin = 'ftp_get'
            else:  # http:// or https://
                # For HTTP(S), we can use curl directly
                transport_plugin = None  # Will use curl below

            # Step 2: Get reader plugin for the file extension
            reader_plugin = registry.get_plugin_for_extension(extension)

            if not reader_plugin:
                click.echo(f"Error: No reader plugin found for extension: {extension}", err=True)
                sys.exit(1)

            if reader_plugin not in all_plugins:
                click.echo(f"Error: Reader plugin '{reader_plugin}' not found", err=True)
                sys.exit(1)

            reader_path = Path(all_plugins[reader_plugin].path)

            if verbose:
                if transport_plugin:
                    click.echo(f"Transport: {transport_plugin} → Reader: {reader_plugin}", err=True)
                else:
                    click.echo(f"Transport: curl → Reader: {reader_plugin}", err=True)

            # Step 3: Fetch file via transport
            if transport_plugin and transport_plugin in all_plugins:
                # Use transport plugin (s3_get or ftp_get)
                transport_path = Path(all_plugins[transport_plugin].path)
                fetch_cmd = [sys.executable, str(transport_path), source]
            else:
                # Use curl for HTTP(S)
                fetch_cmd = ['curl', '-sL', source]

            # Step 4: Stream through pipeline with backpressure
            # Use Popen + pipes for true streaming (no memory buffering)
            # This provides automatic backpressure via OS pipe buffers (~64KB)

            reader_cmd = [sys.executable, str(reader_path)]

            # Create fetch process
            fetch_process = subprocess.Popen(
                fetch_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Create reader process, connected via pipe
            # stdin comes from fetch stdout (OS pipe provides backpressure)
            reader_process = subprocess.Popen(
                reader_cmd,
                stdin=fetch_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # CRITICAL: Close fetch stdout in parent process
            # This enables proper SIGPIPE propagation for clean shutdown
            # Without this, if reader exits early, fetch can deadlock
            fetch_process.stdout.close()

            # Stream output line by line (pull-based with backpressure)
            # Reader only pulls data as fast as it can process
            # If reader is slow, pipe fills → fetch blocks → curl pauses
            output_buffer = []
            for line in reader_process.stdout:
                output_buffer.append(line.decode('utf-8'))

            # Wait for processes to complete
            reader_returncode = reader_process.wait()
            fetch_returncode = fetch_process.wait()

            # Check for errors after completion
            if fetch_returncode != 0:
                fetch_stderr = fetch_process.stderr.read().decode('utf-8', errors='replace')
                click.echo(f"Error fetching URL: {fetch_stderr}", err=True)
                sys.exit(fetch_returncode)

            if reader_returncode != 0:
                reader_stderr = reader_process.stderr.read().decode('utf-8', errors='replace')
                click.echo(f"Error parsing file: {reader_stderr}", err=True)
                sys.exit(reader_returncode)

            output = ''.join(output_buffer)

        else:
            # No file extension or unknown type - use http_get (JSON API)
            plugin_name = 'http_get'

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
                '.yaml': 'yaml',
                '.yml': 'yaml',
                '.xml': 'xml',
                '.toml': 'toml',
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
        'yaml': 'yaml_writer',
        'yml': 'yaml_writer',
        'xml': 'xml_writer',
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
    elif output_format in ['yaml', 'yml']:
        # YAML writer writes to stdout
        cmd.extend(['--indent', str(indent)])
    elif output_format == 'xml':
        # XML writer writes to stdout
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
    elif output_format in ['csv', 'tsv', 'ndjson', 'yaml', 'yml', 'xml']:
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
