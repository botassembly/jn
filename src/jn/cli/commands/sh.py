"""Sh command - execute shell commands and output NDJSON."""

import subprocess
import sys

import click

from ...addressing import (
    AddressResolutionError,
    AddressResolver,
    parse_address,
)
from ...context import pass_context
from ...process_utils import popen_with_validation
from ...shell.jc_fallback import execute_with_jc, supports_command
from ..helpers import build_subprocess_env_for_coverage, check_uv_available


def _build_command(stage, command_str) -> list:
    """Build command from execution stage."""
    cmd = ["uv", "run", "--script", stage.plugin_path, "--mode", stage.mode]

    # Add full command string (not just URL, so plugin gets full context)
    cmd.append(command_str)

    return cmd


@click.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("command", nargs=-1, required=True)
@pass_context
def sh(ctx, command):
    """Execute shell command and output NDJSON to stdout.

    Takes all remaining arguments as the shell command to execute.
    No quoting needed - arguments are passed as-is.

    Examples:
        jn sh ls -l /tmp
        jn sh find . -name "*.py"
        jn sh ps aux
        jn sh du -h /var/log

    The command will be executed and its output parsed to NDJSON
    using jc if a parser is available for that command.
    """
    try:
        check_uv_available()

        # Join all arguments into command string
        command_str = " ".join(command)

        # Parse as address (first word becomes the command)
        addr = parse_address(command_str)

        # Plan execution
        resolver = AddressResolver(ctx.plugin_dir, ctx.cache_path, ctx.home)

        try:
            stages = resolver.plan_execution(addr, mode="read")
        except AddressResolutionError:
            # No custom plugin found - try jc fallback
            command_name = command[0]
            if supports_command(command_name):
                exit_code = execute_with_jc(command_str)
                sys.exit(exit_code)
            else:
                click.echo(
                    f"Error: No plugin or jc parser found for command: {command_name}",
                    err=True,
                )
                sys.exit(1)

        # Plugin found - use it
        if not stages:
            click.echo(
                f"Error: No stages planned for command: {command[0]}", err=True
            )
            sys.exit(1)

        if len(stages) > 1:
            click.echo(
                "Error: Multi-stage execution not supported for sh command",
                err=True,
            )
            sys.exit(1)

        stage = stages[0]

        # Execute plugin
        cmd = _build_command(stage, command_str)

        proc = popen_with_validation(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=None,  # Let stderr pass through to parent
            text=True,
            env=build_subprocess_env_for_coverage(),
        )

        # Stream output
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()  # Critical for subprocess pipes

        proc.wait()

        # Check for errors
        if proc.returncode != 0:
            click.echo(
                f"Error: Command failed with exit code {proc.returncode}",
                err=True,
            )
            sys.exit(1)

    except ValueError as e:
        click.echo(f"Error: Invalid command syntax: {e}", err=True)
        sys.exit(1)
    except AddressResolutionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
