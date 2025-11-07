"""Pipeline execution service."""

import subprocess
from typing import Any, Dict

from ..drivers.exec import spawn_exec
from ..models.project import Converter, Project, Source, Target
from . import JnError


def _run_source(source: Source, params: Dict[str, Any]) -> bytes:
    """Execute a source and return its output bytes."""
    if source.driver == "exec" and source.exec:
        result = spawn_exec(
            source.exec.argv, env=source.exec.env, cwd=source.exec.cwd
        )
        if result.returncode != 0:
            raise JnError(
                "source",
                source.name,
                result.returncode,
                result.stderr.decode("utf-8", "ignore"),
            )
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
                import json

                argv.extend(["--argjson", key, json.dumps(value)])

        result = subprocess.run(
            argv, input=stdin, capture_output=True, check=False
        )
        if result.returncode != 0:
            raise JnError(
                "converter",
                converter.name,
                result.returncode,
                result.stderr.decode("utf-8", "ignore"),
            )
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
        if result.returncode != 0:
            raise JnError(
                "target",
                target.name,
                result.returncode,
                result.stderr.decode("utf-8", "ignore"),
            )
        return result.stdout
    raise NotImplementedError(f"Driver {target.driver} not implemented")


def run_pipeline(
    project: Project, pipeline_name: str, params: Dict[str, Any]
) -> bytes:
    """Execute a pipeline: source → converters → target."""
    pipeline = next(
        (p for p in project.pipelines if p.name == pipeline_name), None
    )
    if not pipeline:
        raise KeyError(f"Pipeline not found: {pipeline_name}")
    if not pipeline.steps:
        raise ValueError(f"Pipeline {pipeline_name} has no steps")

    # Source (first step)
    source_step = pipeline.steps[0]
    if source_step.type != "source":
        raise ValueError(
            f"Pipeline {pipeline_name}: first step must be a source"
        )
    source = next(
        (s for s in project.sources if s.name == source_step.ref), None
    )
    if not source:
        raise KeyError(f"Source not found: {source_step.ref}")
    data = _run_source(source, source_step.args or {})

    # Converters (middle steps)
    for step in pipeline.steps[1:-1]:
        if step.type != "converter":
            raise ValueError(
                f"Pipeline {pipeline_name}: middle steps must be converters"
            )
        converter = next(
            (c for c in project.converters if c.name == step.ref), None
        )
        if not converter:
            raise KeyError(f"Converter not found: {step.ref}")
        data = _run_converter(converter, data)

    # Target (last step)
    target_step = pipeline.steps[-1]
    if target_step.type != "target":
        raise ValueError(
            f"Pipeline {pipeline_name}: last step must be a target"
        )
    target = next(
        (t for t in project.targets if t.name == target_step.ref), None
    )
    if not target:
        raise KeyError(f"Target not found: {target_step.ref}")

    return _run_target(target, data)
