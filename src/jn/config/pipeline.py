"""Pipeline execution and explanation helpers bound to the active config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar

from jn.drivers import spawn_exec
from jn.exceptions import JnError
from jn.models import Completed, Converter, PipelinePlan, Source, Target

from .core import ensure

T = TypeVar("T")

__all__ = ["explain_pipeline", "run_pipeline"]


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


def _run_source(source: Source) -> bytes:
    """Execute a source and return its output bytes."""

    if source.driver == "exec" and source.exec:
        result = spawn_exec(
            source.exec.argv, env=source.exec.env, cwd=source.exec.cwd
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


def _run_target(target: Target, stdin: bytes) -> bytes:
    """Execute a target and return its output bytes."""

    if target.driver == "exec" and target.exec:
        result = spawn_exec(
            target.exec.argv,
            stdin=stdin,
            env=target.exec.env,
            cwd=target.exec.cwd,
        )
        _check_result("target", target.name, result)
        return result.stdout
    raise NotImplementedError(f"Driver {target.driver} not implemented")


def run_pipeline(
    pipeline_name: str,
    path: Optional[Path | str] = None,
) -> bytes:
    """Execute a pipeline: source → converters → target."""

    config_obj = ensure(path)
    pipeline = _lookup(config_obj.pipelines, pipeline_name, "pipeline")
    if not pipeline.steps:
        raise ValueError(f"Pipeline {pipeline_name} has no steps")

    source_step = pipeline.steps[0]
    if source_step.type != "source":
        raise ValueError(
            f"Pipeline {pipeline_name}: first step must be a source"
        )
    source = _lookup(config_obj.sources, source_step.ref, "source")
    data = _run_source(source)

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

    return _run_target(target, data)


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
