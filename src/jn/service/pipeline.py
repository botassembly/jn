"""Pipeline execution service."""

import json
from typing import List, TypeVar

from ..drivers import spawn_exec
from ..exceptions import JnError
from ..models import Completed, Converter, Project, Source, Target

T = TypeVar("T")


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
    item = next((x for x in items if x.name == name), None)  # type: ignore
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


def run_pipeline(project: Project, pipeline_name: str) -> bytes:
    """Execute a pipeline: source → converters → target."""
    pipeline = _lookup(project.pipelines, pipeline_name, "pipeline")
    if not pipeline.steps:
        raise ValueError(f"Pipeline {pipeline_name} has no steps")

    # Source (first step)
    source_step = pipeline.steps[0]
    if source_step.type != "source":
        raise ValueError(
            f"Pipeline {pipeline_name}: first step must be a source"
        )
    source = _lookup(project.sources, source_step.ref, "source")
    data = _run_source(source)

    # Converters (middle steps)
    for step in pipeline.steps[1:-1]:
        if step.type != "converter":
            raise ValueError(
                f"Pipeline {pipeline_name}: middle steps must be converters"
            )
        converter = _lookup(project.converters, step.ref, "converter")
        data = _run_converter(converter, data)

    # Target (last step)
    target_step = pipeline.steps[-1]
    if target_step.type != "target":
        raise ValueError(
            f"Pipeline {pipeline_name}: last step must be a target"
        )
    target = _lookup(project.targets, target_step.ref, "target")

    return _run_target(target, data)
