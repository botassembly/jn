"""Mutation helpers for config objects (add/update operations)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from jn.models import (
    Converter,
    CsvConfig,
    CurlSpec,
    Error,
    ExecSpec,
    FileSpec,
    JqConfig,
    Pipeline,
    ShellSpec,
    Source,
    Step,
    Target,
)

from .core import persist, require

__all__ = ["add_converter", "add_pipeline", "add_source", "add_target"]


def add_source(
    name: str,
    driver: Literal["exec", "shell", "curl", "file"],
    argv: Optional[List[str]] = None,
    cmd: Optional[str] = None,
    url: Optional[str] = None,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    timeout: int = 30,
    follow_redirects: bool = True,
    retry: int = 0,
    retry_delay: int = 2,
    fail_on_error: bool = True,
    path: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    allow_outside_config: bool = False,
    adapter: Optional[str] = None,
    csv: Optional[Dict[str, Any]] = None,
) -> Source | Error:
    """Add a new source to the cached config and persist it."""

    config_obj = require().model_copy(deep=True)

    if config_obj.has_source(name):
        return Error(message=f"Source '{name}' already exists")

    if driver == "exec":
        source = Source(
            name=name,
            driver="exec",
            adapter=adapter,
            exec=ExecSpec(argv=argv or [], cwd=cwd, env=env or {}),
        )
    elif driver == "shell":
        source = Source(
            name=name,
            driver="shell",
            adapter=adapter,
            shell=ShellSpec(cmd=cmd or ""),
        )
    elif driver == "curl":
        source = Source(
            name=name,
            driver="curl",
            adapter=adapter,
            curl=CurlSpec(
                method=method,
                url=url or "",
                headers=headers or {},
                body=body,
                timeout=timeout,
                follow_redirects=follow_redirects,
                retry=retry,
                retry_delay=retry_delay,
                fail_on_error=fail_on_error,
            ),
        )
    elif driver == "file":
        # Build CSV config if provided
        csv_config = CsvConfig(**csv) if csv else None
        source = Source(
            name=name,
            driver="file",
            adapter=adapter,
            file=FileSpec(
                path=path or "",
                mode="read",
                allow_outside_config=allow_outside_config,
            ),
            csv=csv_config,
        )
    else:
        return Error(message=f"Unknown driver: {driver}")

    config_obj.sources.append(source)
    persist(config_obj)
    return source


def add_target(
    name: str,
    driver: Literal["exec", "shell", "curl", "file"],
    argv: Optional[List[str]] = None,
    cmd: Optional[str] = None,
    url: Optional[str] = None,
    method: str = "POST",
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    timeout: int = 30,
    follow_redirects: bool = True,
    retry: int = 0,
    retry_delay: int = 2,
    fail_on_error: bool = True,
    path: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    append: bool = False,
    create_parents: bool = False,
    allow_outside_config: bool = False,
) -> Target | Error:
    """Add a new target to the cached config and persist it."""

    config_obj = require().model_copy(deep=True)

    if config_obj.has_target(name):
        return Error(message=f"Target '{name}' already exists")

    if driver == "exec":
        target = Target(
            name=name,
            driver="exec",
            exec=ExecSpec(argv=argv or [], cwd=cwd, env=env or {}),
        )
    elif driver == "shell":
        target = Target(
            name=name, driver="shell", shell=ShellSpec(cmd=cmd or "")
        )
    elif driver == "curl":
        target = Target(
            name=name,
            driver="curl",
            curl=CurlSpec(
                method=method,
                url=url or "",
                headers=headers or {},
                body=body,
                timeout=timeout,
                follow_redirects=follow_redirects,
                retry=retry,
                retry_delay=retry_delay,
                fail_on_error=fail_on_error,
            ),
        )
    elif driver == "file":
        target = Target(
            name=name,
            driver="file",
            file=FileSpec(
                path=path or "",
                mode="write",
                append=append,
                create_parents=create_parents,
                allow_outside_config=allow_outside_config,
            ),
        )
    else:
        return Error(message=f"Unknown driver: {driver}")

    config_obj.targets.append(target)
    persist(config_obj)
    return target


def add_converter(
    name: str,
    expr: Optional[str] = None,
    file: Optional[str] = None,
    raw: bool = False,
    modules: Optional[str] = None,
) -> Converter | Error:
    """Add a new jq converter to the cached config and persist it."""

    config_obj = require().model_copy(deep=True)

    if config_obj.has_converter(name):
        return Error(message=f"Converter '{name}' already exists")

    if not expr and not file:
        return Error(
            message="Either --expr or --file is required for jq converter"
        )

    converter = Converter(
        name=name,
        engine="jq",
        jq=JqConfig(expr=expr, file=file, raw=raw, modules=modules),
    )

    config_obj.converters.append(converter)
    persist(config_obj)
    return converter


def add_pipeline(name: str, steps: List[str]) -> Pipeline | Error:
    """Add a new pipeline to the cached config and persist it."""

    config_obj = require().model_copy(deep=True)

    if config_obj.has_pipeline(name):
        return Error(message=f"Pipeline '{name}' already exists")

    if not steps:
        return Error(message="Pipeline requires at least one step (--steps)")

    parsed_steps: list[Step] = []
    for step_spec in steps:
        if ":" not in step_spec:
            return Error(
                message=(
                    f"Invalid step format: '{step_spec}'. Expected 'type:ref' (e.g., 'source:echo')"
                )
            )

        step_type, step_ref = step_spec.split(":", 1)
        if step_type not in {"source", "converter", "target"}:
            return Error(
                message=(
                    f"Invalid step type: '{step_type}'. Must be 'source', 'converter', or 'target'"
                )
            )

        parsed_steps.append(Step(type=step_type, ref=step_ref))

    pipeline = Pipeline(name=name, steps=parsed_steps)
    config_obj.pipelines.append(pipeline)
    persist(config_obj)
    return pipeline
