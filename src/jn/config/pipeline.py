"""Pipeline execution and explanation helpers bound to the active config."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, TypeVar

# Import JC first
import jc

# Register our custom parsers with JC
# JC's plugin system expects parsers in jc.parsers namespace
from jn.jcparsers import psv_s, tsv_s

sys.modules["jc.parsers.tsv_s"] = tsv_s
sys.modules["jc.parsers.psv_s"] = psv_s

from jn.drivers import (  # noqa: E402
    run_file_write,
    spawn_curl,
    spawn_exec,
    spawn_shell,
)
from jn.exceptions import JnError  # noqa: E402
from jn.models import (  # noqa: E402
    Completed,
    Converter,
    PipelinePlan,
    Source,
    Target,
)

from .core import config_path, ensure  # noqa: E402
from .utils import substitute_template  # noqa: E402

T = TypeVar("T")

__all__ = ["explain_pipeline", "run_pipeline"]


def _detect_parser_from_extension(path: str) -> Optional[str]:
    """Auto-detect JC parser from file extension.

    Returns:
        Parser name (e.g., 'csv_s', 'tsv_s', 'psv_s') or None for non-delimited files
    """
    ext = Path(path).suffix.lower()
    parser_map = {
        ".csv": "csv_s",
        ".tsv": "tsv_s",
        ".psv": "psv_s",
    }
    return parser_map.get(ext)


def _get_config_root() -> str:
    """Get the directory containing the active config file."""
    path = config_path()
    if path is None:
        raise ValueError("No config path set")
    return str(Path(path).parent)


def _validate_file_path(
    path: str,
    *,
    allow_outside_config: bool = False,
    config_root: Optional[str] = None,
) -> Path:
    """Validate and resolve a file path.

    Args:
        path: File path to validate (absolute or relative to config_root)
        allow_outside_config: If False, restrict to config root
        config_root: Root directory for path resolution and confinement

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path escapes config_root when not allowed
        FileNotFoundError: If file doesn't exist
    """
    # Resolve path relative to config_root if it's relative
    path_obj = Path(path)
    if config_root and not path_obj.is_absolute():
        file_path = (Path(config_root) / path_obj).resolve()
    else:
        file_path = path_obj.resolve()

    # Path confinement check
    if not allow_outside_config and config_root:
        root = Path(config_root).resolve()
        try:
            file_path.relative_to(root)
        except ValueError:
            raise ValueError(
                f"Path {path} is outside config root {config_root}. "
                f"Use allow_outside_config=true to bypass."
            )

    # Check existence
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return file_path


def _check_result(item_type: str, name: str, result: Completed) -> None:
    """Check process result and raise JnError if failed."""

    if result.returncode != 0:
        raise JnError(
            item_type,
            name,
            result.returncode,
            result.stderr.decode("utf-8", "ignore"),
        )


def _lookup(items: List[T], name: str, item_type: str) -> T:
    """Look up item by name, raise KeyError if not found."""

    item = next((x for x in items if x.name == name), None)  # type: ignore[attr-defined]
    if not item:
        raise KeyError(f"{item_type.capitalize()} not found: {name}")
    return item


def _run_source(
    source: Source,
    params: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
    unsafe_shell: bool = False,
) -> Iterator[bytes]:
    """Execute a source and return its output as a stream of bytes."""

    if source.driver == "exec" and source.exec:
        # Apply templating to argv
        argv = [
            substitute_template(arg, params=params, env=env)
            for arg in source.exec.argv
        ]
        # Apply templating to cwd if present
        cwd = (
            substitute_template(source.exec.cwd, params=params, env=env)
            if source.exec.cwd
            else None
        )
        # Build final env: start with merged env (os.environ + CLI overrides),
        # then overlay config's env dict (with templating applied)
        # Precedence: config.exec.env > CLI --env > os.environ
        final_env = env.copy() if env else {}
        if source.exec.env:
            templated_config_env = {
                key: substitute_template(value, params=params, env=env)
                for key, value in source.exec.env.items()
            }
            final_env.update(templated_config_env)
        result = spawn_exec(argv, env=final_env or None, cwd=cwd)
        _check_result("source", source.name, result)
        yield result.stdout
    elif source.driver == "shell" and source.shell:
        # Apply templating to shell command
        cmd = substitute_template(source.shell.cmd, params=params, env=env)
        result = spawn_shell(cmd, env=env, unsafe=unsafe_shell)
        _check_result("source", source.name, result)
        yield result.stdout
    elif source.driver == "file" and source.file:
        # Apply templating to path
        path = substitute_template(source.file.path, params=params, env=env)

        # Validate path and check permissions
        file_path = _validate_file_path(
            path,
            allow_outside_config=source.file.allow_outside_config,
            config_root=_get_config_root(),
        )

        # Auto-detect and apply JC parser based on file extension
        parser = _detect_parser_from_extension(path)
        if parser:
            # TRUE STREAMING: open file, let JC stream from it, yield line-by-line
            with open(file_path, encoding="utf-8") as f:
                for item in jc.parse(parser, f):
                    yield json.dumps(item, ensure_ascii=False).encode(
                        "utf-8"
                    ) + b"\n"
        else:
            # Stream raw file in chunks for non-parsed files
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
    elif source.driver == "curl" and source.curl:
        # Apply templating to URL, headers, and body
        url = substitute_template(source.curl.url, params=params, env=env)
        headers = {
            key: substitute_template(value, params=params, env=env)
            for key, value in source.curl.headers.items()
        }
        # Apply templating to body if it's a literal string
        body = None
        if source.curl.body is not None and source.curl.body != "stdin":
            body = substitute_template(
                source.curl.body, params=params, env=env
            )
        # Note: body="stdin" doesn't apply to sources (they don't receive data)

        result = spawn_curl(
            method=source.curl.method,
            url=url,
            headers=headers,
            body=body,
            timeout=source.curl.timeout,
            follow_redirects=source.curl.follow_redirects,
            retry=source.curl.retry,
            retry_delay=source.curl.retry_delay,
            fail_on_error=source.curl.fail_on_error,
        )
        _check_result("source", source.name, result)
        yield result.stdout
    else:
        raise NotImplementedError(f"Driver {source.driver} not implemented")


def _run_converter(
    converter: Converter, stdin: Iterator[bytes]
) -> Iterator[bytes]:
    """Execute a converter and return transformed bytes as a stream.

    Note: Converter.engine is always "jq" (Literal["jq"]), so we only
    need to check that converter.jq is configured.
    """
    import subprocess

    if converter.jq:
        argv = ["jq", "-c"]
        if converter.jq.raw:
            argv.append("-r")
        if converter.jq.expr:
            argv.append(converter.jq.expr)
        elif converter.jq.file:
            argv.extend(["-f", converter.jq.file])
        else:
            raise ValueError(
                f"Converter {converter.name}: jq requires expr or file"
            )

        for key, value in (converter.jq.args or {}).items():
            if isinstance(value, str):
                argv.extend(["--arg", key, value])
            else:
                argv.extend(["--argjson", key, json.dumps(value)])

        # For now, materialize the input to avoid deadlock issues
        # TODO: Implement proper streaming with threading
        stdin_bytes = b"".join(stdin)
        result = spawn_exec(argv, stdin=stdin_bytes)
        _check_result("converter", converter.name, result)
        yield result.stdout

    else:
        raise NotImplementedError(f"Engine {converter.engine} not implemented")


def _run_target(
    target: Target,
    stdin: Iterator[bytes],
    params: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
    unsafe_shell: bool = False,
) -> bytes:
    """Execute a target and return its output bytes."""

    # Materialize the iterator for targets (they need all data)
    stdin_bytes = b"".join(stdin)

    if target.driver == "exec" and target.exec:
        # Apply templating to argv
        argv = [
            substitute_template(arg, params=params, env=env)
            for arg in target.exec.argv
        ]
        # Apply templating to cwd if present
        cwd = (
            substitute_template(target.exec.cwd, params=params, env=env)
            if target.exec.cwd
            else None
        )
        # Build final env: start with merged env (os.environ + CLI overrides),
        # then overlay config's env dict (with templating applied)
        # Precedence: config.exec.env > CLI --env > os.environ
        final_env = env.copy() if env else {}
        if target.exec.env:
            templated_config_env = {
                key: substitute_template(value, params=params, env=env)
                for key, value in target.exec.env.items()
            }
            final_env.update(templated_config_env)
        result = spawn_exec(
            argv, stdin=stdin_bytes, env=final_env or None, cwd=cwd
        )
        _check_result("target", target.name, result)
        return result.stdout
    elif target.driver == "shell" and target.shell:
        # Apply templating to shell command
        cmd = substitute_template(target.shell.cmd, params=params, env=env)
        result = spawn_shell(
            cmd, stdin=stdin_bytes, env=env, unsafe=unsafe_shell
        )
        _check_result("target", target.name, result)
        return result.stdout
    elif target.driver == "file" and target.file:
        # Apply templating to path
        path = substitute_template(target.file.path, params=params, env=env)
        result = run_file_write(
            path,
            stdin_bytes,
            append=target.file.append,
            create_parents=target.file.create_parents,
            allow_outside_config=target.file.allow_outside_config,
            config_root=_get_config_root(),
        )
        _check_result("target", target.name, result)
        return result.stdout
    elif target.driver == "curl" and target.curl:
        # Apply templating to URL and headers
        url = substitute_template(target.curl.url, params=params, env=env)
        headers = {
            key: substitute_template(value, params=params, env=env)
            for key, value in target.curl.headers.items()
        }
        result = spawn_curl(
            method=target.curl.method,
            url=url,
            headers=headers,
            body=target.curl.body,
            stdin=stdin_bytes,
            timeout=target.curl.timeout,
            follow_redirects=target.curl.follow_redirects,
            retry=target.curl.retry,
            retry_delay=target.curl.retry_delay,
            fail_on_error=target.curl.fail_on_error,
        )
        _check_result("target", target.name, result)
        return result.stdout
    raise NotImplementedError(f"Driver {target.driver} not implemented")


def run_pipeline(
    pipeline_name: str,
    path: Optional[Path | str] = None,
    params: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
    unsafe_shell: bool = False,
) -> bytes:
    """Execute a pipeline: source → converters → target."""

    config_obj = ensure(path)
    pipeline = _lookup(config_obj.pipelines, pipeline_name, "pipeline")
    if not pipeline.steps:
        raise ValueError(f"Pipeline {pipeline_name} has no steps")

    # Merge env overrides with os.environ (CLI overrides take precedence)
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    source_step = pipeline.steps[0]
    if source_step.type != "source":
        raise ValueError(
            f"Pipeline {pipeline_name}: first step must be a source"
        )
    source = _lookup(config_obj.sources, source_step.ref, "source")
    data = _run_source(
        source, params=params, env=merged_env, unsafe_shell=unsafe_shell
    )

    for step in pipeline.steps[1:-1]:
        if step.type != "converter":
            raise ValueError(
                f"Pipeline {pipeline_name}: middle steps must be converters"
            )
        converter = _lookup(config_obj.converters, step.ref, "converter")
        data = _run_converter(converter, data)

    target_step = pipeline.steps[-1]
    if target_step.type != "target":
        raise ValueError(
            f"Pipeline {pipeline_name}: last step must be a target"
        )
    target = _lookup(config_obj.targets, target_step.ref, "target")

    return _run_target(
        target, data, params=params, env=merged_env, unsafe_shell=unsafe_shell
    )


def explain_pipeline(
    pipeline_name: str,
    *,
    show_commands: bool = False,
    show_env: bool = False,
    path: Optional[Path | str] = None,
) -> PipelinePlan:
    """Build a resolved plan for a pipeline without executing it."""

    config_obj = ensure(path)
    pipeline = config_obj.get_pipeline(pipeline_name)
    if not pipeline:
        raise ValueError(f"Pipeline '{pipeline_name}' not found")

    steps: list[Dict[str, Any]] = []
    for step in pipeline.steps:
        step_info: Dict[str, Any] = {"type": step.type, "name": step.ref}

        if step.type == "source":
            source = config_obj.get_source(step.ref)
            if source:
                step_info["driver"] = source.driver
                step_info["mode"] = source.mode
                if show_commands:
                    if source.driver == "exec" and source.exec:
                        step_info["argv"] = source.exec.argv
                        if source.exec.cwd:
                            step_info["cwd"] = source.exec.cwd
                    elif source.driver == "shell" and source.shell:
                        step_info["cmd"] = source.shell.cmd
                    elif source.driver == "curl" and source.curl:
                        step_info["method"] = source.curl.method
                        step_info["url"] = source.curl.url
                if show_env and source.driver == "exec" and source.exec:
                    step_info["env"] = source.exec.env or {}

        elif step.type == "converter":
            converter = config_obj.get_converter(step.ref)
            if converter:
                step_info["engine"] = converter.engine
                # Note: engine is always "jq" (Literal["jq"])
                if show_commands and converter.jq:
                    step_info["expr"] = converter.jq.expr
                    step_info["raw"] = converter.jq.raw
                    if converter.jq.file:
                        step_info["file"] = converter.jq.file
                    if converter.jq.modules:
                        step_info["modules"] = converter.jq.modules

        elif step.type == "target":
            target = config_obj.get_target(step.ref)
            if target:
                step_info["driver"] = target.driver
                step_info["mode"] = target.mode
                if show_commands:
                    if target.driver == "exec" and target.exec:
                        step_info["argv"] = target.exec.argv
                        if target.exec.cwd:
                            step_info["cwd"] = target.exec.cwd
                    elif target.driver == "shell" and target.shell:
                        step_info["cmd"] = target.shell.cmd
                    elif target.driver == "curl" and target.curl:
                        step_info["method"] = target.curl.method
                        step_info["url"] = target.curl.url
                if show_env and target.driver == "exec" and target.exec:
                    step_info["env"] = target.exec.env or {}

        steps.append(step_info)

    return PipelinePlan(pipeline=pipeline_name, steps=steps)
