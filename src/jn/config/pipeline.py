"""Pipeline execution and explanation helpers bound to the active config."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar

from jn.drivers import run_file_read, run_file_write, spawn_exec
from jn.exceptions import JnError
from jn.models import Completed, Converter, PipelinePlan, Source, Target

from .core import config_path, ensure
from .utils import substitute_template

T = TypeVar("T")

__all__ = ["explain_pipeline", "run_pipeline"]


def _get_config_root() -> str:
    """Get the directory containing the active config file."""
    path = config_path()
    if path is None:
        raise ValueError("No config path set")
    return str(Path(path).parent)


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
) -> bytes:
    """Execute a source and return its output bytes."""

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
        # Apply templating to env dict values
        templated_env = (
            {
                key: substitute_template(value, params=params, env=env)
                for key, value in source.exec.env.items()
            }
            if source.exec.env
            else {}
        )
        result = spawn_exec(argv, env=templated_env, cwd=cwd)
        _check_result("source", source.name, result)
        return result.stdout
    elif source.driver == "file" and source.file:
        # Apply templating to path
        path = substitute_template(source.file.path, params=params, env=env)
        result = run_file_read(
            path,
            allow_outside_config=source.file.allow_outside_config,
            config_root=_get_config_root(),
        )
        _check_result("source", source.name, result)
        return result.stdout
    raise NotImplementedError(f"Driver {source.driver} not implemented")


def _run_converter(converter: Converter, stdin: bytes) -> bytes:
    """Execute a converter and return transformed bytes."""

    if converter.engine == "jq" and converter.jq:
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

        result = spawn_exec(argv, stdin=stdin)
        _check_result("converter", converter.name, result)
        return result.stdout

    raise NotImplementedError(f"Engine {converter.engine} not implemented")


def _run_target(
    target: Target,
    stdin: bytes,
    params: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
) -> bytes:
    """Execute a target and return its output bytes."""

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
        # Apply templating to env dict values
        templated_env = (
            {
                key: substitute_template(value, params=params, env=env)
                for key, value in target.exec.env.items()
            }
            if target.exec.env
            else {}
        )
        result = spawn_exec(argv, stdin=stdin, env=templated_env, cwd=cwd)
        _check_result("target", target.name, result)
        return result.stdout
    elif target.driver == "file" and target.file:
        # Apply templating to path
        path = substitute_template(target.file.path, params=params, env=env)
        result = run_file_write(
            path,
            stdin,
            append=target.file.append,
            create_parents=target.file.create_parents,
            allow_outside_config=target.file.allow_outside_config,
            config_root=_get_config_root(),
        )
        _check_result("target", target.name, result)
        return result.stdout
    raise NotImplementedError(f"Driver {target.driver} not implemented")


def run_pipeline(
    pipeline_name: str,
    path: Optional[Path | str] = None,
    params: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
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
    data = _run_source(source, params=params, env=merged_env)

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

    return _run_target(target, data, params=params, env=merged_env)


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
                if show_commands and converter.engine == "jq" and converter.jq:
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
