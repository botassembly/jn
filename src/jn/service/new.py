"""Service layer: create new project items."""

from pathlib import Path
from typing import Dict, List, Literal, Optional

from ..home.io import save_json
from ..models.project import (
    Converter,
    CurlSpec,
    Error,
    ExecSpec,
    FileSpec,
    JqConfig,
    Pipeline,
    Project,
    ShellSpec,
    Source,
    Step,
    Target,
)


def add_source(
    config: Project,
    name: str,
    driver: Literal["exec", "shell", "curl", "file"],
    argv: Optional[List[str]] = None,
    cmd: Optional[str] = None,
    url: Optional[str] = None,
    method: str = "GET",
    path: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> Source | Error:
    """
    Add a new source to the project.

    Args:
        config: Current project configuration (must have config_path set)
        name: Source name
        driver: Driver type
        argv: Command argv (for exec driver)
        cmd: Shell command (for shell driver)
        url: URL (for curl driver)
        method: HTTP method (for curl driver)
        path: File path (for file driver)
        env: Environment variables (for exec driver)
        cwd: Working directory (for exec driver)

    Returns:
        Created Source or Error
    """
    # Check for duplicate name
    if config.has_source(name):
        return Error(message=f"Source '{name}' already exists")

    # Build the source based on driver
    if driver == "exec":
        source = Source(
            name=name,
            driver="exec",
            exec=ExecSpec(
                argv=argv,
                cwd=cwd,
                env=env or {},
            ),
        )
    elif driver == "shell":
        source = Source(
            name=name,
            driver="shell",
            shell=ShellSpec(cmd=cmd),
        )
    elif driver == "curl":
        source = Source(
            name=name,
            driver="curl",
            curl=CurlSpec(
                method=method,
                url=url,
            ),
        )
    elif driver == "file":
        source = Source(
            name=name,
            driver="file",
            file=FileSpec(
                path=path,
                mode="read",
            ),
        )
    else:
        return Error(message=f"Unknown driver: {driver}")

    # Add source to config
    config.sources.append(source)

    # Validate the updated config (Pydantic will check uniqueness)
    saved_path = config.config_path
    config = Project.model_validate(config.model_dump())
    config.config_path = saved_path

    # Write back to file
    if config.config_path is None:
        return Error(message="Config path not set")
    save_json(config.config_path, config.model_dump(exclude_none=True))

    return source


def add_target(
    config: Project,
    name: str,
    driver: Literal["exec", "shell", "curl", "file"],
    argv: Optional[List[str]] = None,
    cmd: Optional[str] = None,
    url: Optional[str] = None,
    method: str = "POST",
    path: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> Target | Error:
    """
    Add a new target to the project.

    Args:
        config: Current project configuration (must have config_path set)
        name: Target name
        driver: Driver type
        argv: Command argv (for exec driver)
        cmd: Shell command (for shell driver)
        url: URL (for curl driver)
        method: HTTP method (for curl driver)
        path: File path (for file driver)
        env: Environment variables (for exec driver)
        cwd: Working directory (for exec driver)

    Returns:
        Created Target or Error
    """
    # Check for duplicate name
    if config.has_target(name):
        return Error(message=f"Target '{name}' already exists")

    # Build the target based on driver
    if driver == "exec":
        target = Target(
            name=name,
            driver="exec",
            exec=ExecSpec(
                argv=argv,
                cwd=cwd,
                env=env or {},
            ),
        )
    elif driver == "shell":
        target = Target(
            name=name,
            driver="shell",
            shell=ShellSpec(cmd=cmd),
        )
    elif driver == "curl":
        target = Target(
            name=name,
            driver="curl",
            curl=CurlSpec(
                method=method,
                url=url,
            ),
        )
    elif driver == "file":
        target = Target(
            name=name,
            driver="file",
            file=FileSpec(
                path=path,
                mode="write",
            ),
        )
    else:
        return Error(message=f"Unknown driver: {driver}")

    # Add target to config
    config.targets.append(target)

    # Validate the updated config
    saved_path = config.config_path
    config = Project.model_validate(config.model_dump())
    config.config_path = saved_path

    # Write back to file
    if config.config_path is None:
        return Error(message="Config path not set")
    save_json(config.config_path, config.model_dump(exclude_none=True))

    return target


def add_converter(
    config: Project,
    name: str,
    expr: Optional[str] = None,
    file: Optional[str] = None,
    raw: bool = False,
    modules: Optional[str] = None,
) -> Converter | Error:
    """
    Add a new converter to the project.

    Args:
        config: Current project configuration (must have config_path set)
        name: Converter name
        expr: jq expression (inline)
        file: Path to jq filter file
        raw: Whether to output raw strings
        modules: Path to jq modules directory

    Returns:
        Created Converter or Error
    """
    # Check for duplicate name
    if config.has_converter(name):
        return Error(message=f"Converter '{name}' already exists")

    # Require either expr or file
    if not expr and not file:
        return Error(
            message="Either --expr or --file is required for jq converter"
        )

    # Build the converter
    converter = Converter(
        name=name,
        engine="jq",
        jq=JqConfig(
            expr=expr,
            file=file,
            raw=raw,
            modules=modules,
        ),
    )

    # Add converter to config
    config.converters.append(converter)

    # Validate the updated config
    saved_path = config.config_path
    config = Project.model_validate(config.model_dump())
    config.config_path = saved_path

    # Write back to file
    if config.config_path is None:
        return Error(message="Config path not set")
    save_json(config.config_path, config.model_dump(exclude_none=True))

    return converter


def add_pipeline(
    config: Project,
    name: str,
    steps: List[str],
) -> Pipeline | Error:
    """
    Add a new pipeline to the project.

    Args:
        config: Current project configuration (must have config_path set)
        name: Pipeline name
        steps: List of step specifications in format "type:ref" (e.g., "source:echo")

    Returns:
        Created Pipeline or Error
    """
    # Check for duplicate name
    if config.has_pipeline(name):
        return Error(message=f"Pipeline '{name}' already exists")

    # Require at least one step
    if not steps:
        return Error(message="Pipeline requires at least one step (--steps)")

    # Parse steps
    parsed_steps = []
    for step_spec in steps:
        if ":" not in step_spec:
            return Error(
                message=f"Invalid step format: '{step_spec}'. Expected 'type:ref' (e.g., 'source:echo')"
            )

        step_type, step_ref = step_spec.split(":", 1)

        if step_type not in ["source", "converter", "target"]:
            return Error(
                message=f"Invalid step type: '{step_type}'. Must be 'source', 'converter', or 'target'"
            )

        parsed_steps.append(Step(type=step_type, ref=step_ref))

    # Build the pipeline
    pipeline = Pipeline(
        name=name,
        steps=parsed_steps,
    )

    # Add pipeline to config
    config.pipelines.append(pipeline)

    # Validate the updated config
    saved_path = config.config_path
    config = Project.model_validate(config.model_dump())
    config.config_path = saved_path

    # Write back to file
    if config.config_path is None:
        return Error(message="Config path not set")
    save_json(config.config_path, config.model_dump(exclude_none=True))

    return pipeline
