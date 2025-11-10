"""Pipeline execution engine.

Executes pipelines by running plugins as subprocesses and chaining with Unix pipes.
Supports UV for isolated dependency management per plugin.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, IO
import shutil

from .pipeline import Pipeline, PipelineStep, find_plugin_file
from .discovery import parse_plugin_metadata


class ExecutionError(Exception):
    """Error during pipeline execution."""

    pass


class PluginExecutor:
    """Executes individual plugin steps."""

    def __init__(self, use_uv: bool = True):
        """Initialize executor.

        Args:
            use_uv: Use UV for running plugins with PEP 723 dependencies
        """
        self.use_uv = use_uv and self._has_uv()

    def _has_uv(self) -> bool:
        """Check if uv is available."""
        return shutil.which('uv') is not None

    def build_command(self, step: PipelineStep, plugin_path: Path) -> List[str]:
        """Build command to execute a plugin step.

        Args:
            step: Pipeline step to execute
            plugin_path: Path to plugin file

        Returns:
            Command as list of strings (argv)
        """
        # Check if plugin has dependencies
        metadata = parse_plugin_metadata(plugin_path)
        has_deps = metadata and len(metadata.dependencies) > 0

        # Build base command
        if self.use_uv and has_deps:
            # Use UV to run with dependencies
            cmd = ['uv', 'run', str(plugin_path)]
        else:
            # Run directly with python
            cmd = [sys.executable, str(plugin_path)]

        # Add config as CLI arguments
        # Convert config dict to CLI flags (e.g., {'output': 'file.json'} -> ['--output', 'file.json'])
        for key, value in step.config.items():
            flag = f'--{key.replace("_", "-")}'
            if isinstance(value, bool):
                # Boolean flags: only add if True
                if value:
                    cmd.append(flag)
            elif isinstance(value, list):
                # List values: repeat flag for each item
                for item in value:
                    cmd.extend([flag, str(item)])
            else:
                # Regular value: add flag and value
                cmd.extend([flag, str(value)])

        # Add any custom args
        cmd.extend(step.args)

        return cmd

    def execute_step(
        self,
        step: PipelineStep,
        plugin_path: Path,
        stdin: Optional[IO] = None,
        stdout: Optional[IO] = None,
        stderr: Optional[IO] = None,
    ) -> subprocess.Popen:
        """Execute a single pipeline step.

        Args:
            step: Pipeline step to execute
            plugin_path: Path to plugin file
            stdin: Input stream (default: pipe)
            stdout: Output stream (default: pipe)
            stderr: Error stream (default: pipe)

        Returns:
            Popen object for the running process
        """
        cmd = self.build_command(step, plugin_path)

        # Execute subprocess
        process = subprocess.Popen(
            cmd,
            stdin=stdin or subprocess.PIPE,
            stdout=stdout or subprocess.PIPE,
            stderr=stderr or subprocess.PIPE,
            text=True,
        )

        return process


class PipelineExecutor:
    """Executes complete pipelines."""

    def __init__(
        self,
        plugin_dir: Optional[Path] = None,
        use_uv: bool = True,
        verbose: bool = False,
    ):
        """Initialize pipeline executor.

        Args:
            plugin_dir: Directory containing plugins (default: package plugins)
            use_uv: Use UV for plugin dependency management
            verbose: Print execution details
        """
        if plugin_dir is None:
            plugin_dir = Path(__file__).parent.parent.parent / 'plugins'

        self.plugin_dir = plugin_dir
        self.plugin_executor = PluginExecutor(use_uv=use_uv)
        self.verbose = verbose

    def execute(
        self,
        pipeline: Pipeline,
        input_file: Optional[Path] = None,
        output_file: Optional[Path] = None,
    ) -> int:
        """Execute a pipeline.

        Args:
            pipeline: Pipeline to execute
            input_file: Input file for source (overrides pipeline config)
            output_file: Output file for target (overrides pipeline config)

        Returns:
            Exit code (0 for success)

        Raises:
            ExecutionError: If execution fails
        """
        if not pipeline.steps:
            raise ExecutionError("Pipeline has no steps")

        if self.verbose:
            from .pipeline import describe_pipeline
            print(f"Executing pipeline: {describe_pipeline(pipeline)}", file=sys.stderr)

        # Find all plugin files
        plugin_paths = []
        for step in pipeline.steps:
            plugin_path = find_plugin_file(step.plugin, self.plugin_dir)
            if not plugin_path:
                raise ExecutionError(f"Plugin not found: {step.plugin}")
            plugin_paths.append(plugin_path)

        # Execute pipeline with Unix pipes
        processes: List[subprocess.Popen] = []

        try:
            # Start all processes, chaining stdin/stdout
            for i, (step, plugin_path) in enumerate(zip(pipeline.steps, plugin_paths)):
                is_first = i == 0
                is_last = i == len(pipeline.steps) - 1

                # Determine stdin
                if is_first and input_file:
                    stdin = open(input_file, 'r')
                elif is_first and 'file' in step.config:
                    # Source plugin with file in config - redirect file to stdin
                    stdin = open(step.config['file'], 'r')
                elif is_first:
                    stdin = None  # Use plugin's default stdin
                else:
                    # Chain from previous process
                    stdin = processes[-1].stdout

                # Determine stdout
                if is_last and output_file:
                    stdout = open(output_file, 'w')
                elif is_last and step.config.get('output'):
                    # Target plugin with output file in config
                    stdout = subprocess.PIPE
                elif is_last:
                    # Last step, no output file - capture so we can print
                    stdout = subprocess.PIPE
                else:
                    stdout = subprocess.PIPE

                if self.verbose:
                    cmd = self.plugin_executor.build_command(step, plugin_path)
                    print(f"  Running: {' '.join(cmd)}", file=sys.stderr)

                # Execute step
                process = self.plugin_executor.execute_step(
                    step,
                    plugin_path,
                    stdin=stdin,
                    stdout=stdout,
                    stderr=subprocess.PIPE,
                )

                processes.append(process)

                # Allow previous process to receive SIGPIPE
                if i > 0 and processes[-2].stdout:
                    processes[-2].stdout.close()

            # Wait for all processes to complete
            exit_codes = []
            errors = []

            for i, process in enumerate(processes):
                stdout_data, stderr_data = process.communicate()

                # Print stdout from last process if captured and no output file
                is_last = i == len(processes) - 1
                if is_last and stdout_data and not output_file:
                    print(stdout_data, end='')

                if process.returncode != 0:
                    step_name = pipeline.steps[i].plugin
                    errors.append(f"{step_name} failed with exit code {process.returncode}")
                    if stderr_data:
                        errors.append(f"  {stderr_data.strip()}")

                exit_codes.append(process.returncode)

            # Check for errors
            if any(code != 0 for code in exit_codes):
                error_msg = "\n".join(errors)
                raise ExecutionError(f"Pipeline execution failed:\n{error_msg}")

            return 0

        except Exception as e:
            # Kill any running processes
            for process in processes:
                try:
                    process.kill()
                except:
                    pass

            if isinstance(e, ExecutionError):
                raise
            else:
                raise ExecutionError(f"Pipeline execution error: {e}")
