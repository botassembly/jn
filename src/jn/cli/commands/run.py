"""Run command - convenience for source to dest conversion."""

import io
import json
import subprocess
import sys
from contextlib import ExitStack

import click

from ...addressing import (
    AddressResolutionError,
    AddressResolver,
    ExecutionStage,
    parse_address,
)
from ...context import pass_context
from ...process_utils import popen_with_validation
from ..helpers import build_subprocess_env_for_coverage, check_uv_available


def _build_command(stage: ExecutionStage) -> list:
    """Build command from execution stage."""
    cmd = ["uv", "run", "--script", stage.plugin_path, "--mode", stage.mode]

    # Add configuration parameters
    for key, value in stage.config.items():
        cmd.extend([f"--{key}", str(value)])

    # Add URL if present
    if stage.url:
        if stage.headers:
            cmd.extend(["--headers", json.dumps(stage.headers)])
        cmd.append(stage.url)

    return cmd


@click.command()
@click.argument("input_file")
@click.argument("output_file")
@pass_context
def run(ctx, input_file, output_file):
    """Run pipeline from input to output.

    Convenience command that chains read → write with automatic backpressure.
    Equivalent to: jn cat input | jn put output

    Supports universal addressing syntax: address[~format][?parameters]

    Examples:
        # Basic conversion
        jn run data.csv output.json                    # CSV → JSON

        # Format override
        jn run data.txt~csv output.json                # Force CSV input

        # With parameters
        jn run "data.csv~csv?delimiter=;" output.json  # Semicolon delimiter
        jn run data.json "output.json?indent=4"        # Pretty JSON output

    Note:
        When passing addresses that start with '-', use '--' to stop
        option parsing before the argument, e.g.:
          jn run -- "-~csv" out.json
    """
    try:
        check_uv_available()

        # Parse addresses
        input_addr = parse_address(input_file)
        output_addr = parse_address(output_file)

        # Plan execution stages
        resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path, ctx.home)
        input_stages = resolver.plan_execution(input_addr, mode="read")
        output_resolved = resolver.resolve(output_addr, mode="write")

        writer_cmd = _build_command(
            ExecutionStage(
                plugin_path=output_resolved.plugin_path,
                mode="write",
                config=output_resolved.config,
                url=output_resolved.url,
                headers=output_resolved.headers,
            )
        )

        with ExitStack() as stack:
            if len(input_stages) == 2:
                protocol_cmd = _build_command(input_stages[0])
                format_cmd = _build_command(input_stages[1])

                protocol_proc = popen_with_validation(
                    protocol_cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=False,
                    env=build_subprocess_env_for_coverage(),
                )

                reader_proc = popen_with_validation(
                    format_cmd,
                    stdin=protocol_proc.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=False,
                    env=build_subprocess_env_for_coverage(),
                )

                protocol_proc.stdout.close()
                protocol_error_proc = protocol_proc
            elif len(input_stages) == 1:
                reader_cmd = _build_command(input_stages[0])

                if input_stages[0].url:
                    reader_stdin = subprocess.DEVNULL
                elif input_addr.type == "stdio":
                    reader_stdin = sys.stdin
                else:
                    reader_stdin = stack.enter_context(open(input_addr.base))

                reader_proc = popen_with_validation(
                    reader_cmd,
                    stdin=reader_stdin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=build_subprocess_env_for_coverage(),
                )
                protocol_error_proc = None
            else:
                reader_proc = None
                protocol_error_proc = None

            if output_resolved.url:
                writer_stdout = subprocess.PIPE
            elif output_addr.type == "stdio":
                writer_stdout = sys.stdout
            else:
                writer_stdout = stack.enter_context(
                    open(output_addr.base, "w")
                )

            if reader_proc is not None:
                writer = popen_with_validation(
                    writer_cmd,
                    stdin=reader_proc.stdout,
                    stdout=writer_stdout,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=build_subprocess_env_for_coverage(),
                )
                reader_proc.stdout.close()
            else:
                try:
                    sys.stdin.fileno()  # type: ignore[attr-defined]
                    stdin_source = sys.stdin
                    use_pipe = False
                except (AttributeError, OSError, io.UnsupportedOperation):
                    stdin_source = subprocess.PIPE
                    use_pipe = True

                writer = popen_with_validation(
                    writer_cmd,
                    stdin=stdin_source,
                    stdout=writer_stdout,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=build_subprocess_env_for_coverage(),
                )

                if use_pipe:
                    while True:
                        chunk = sys.stdin.read(8192)
                        if not chunk:
                            break
                        writer.stdin.write(chunk)  # type: ignore[union-attr]
                    writer.stdin.close()  # type: ignore[union-attr]

            writer.wait()
            if reader_proc is not None:
                reader_proc.wait()
            if protocol_error_proc:
                protocol_error_proc.wait()

            if writer.returncode != 0:
                error_msg = writer.stderr.read()
                click.echo(f"Error: Writer error: {error_msg}", err=True)
                sys.exit(1)

            if reader_proc is not None and reader_proc.returncode != 0:
                error_msg = reader_proc.stderr.read()
                click.echo(f"Error: Reader error: {error_msg}", err=True)
                sys.exit(1)

            if protocol_error_proc and protocol_error_proc.returncode != 0:
                error_msg = protocol_error_proc.stderr.read()
                click.echo(f"Error: Protocol error: {error_msg}", err=True)
                sys.exit(1)

    except ValueError as e:
        click.echo(f"Error: Invalid address syntax: {e}", err=True)
        sys.exit(1)
    except AddressResolutionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
