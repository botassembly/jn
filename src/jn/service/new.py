"""Service layer: create new project items."""

from pathlib import Path
from typing import Dict, List, Literal, Optional

from ..home.io import load_json, save_json
from ..models.project import (
    Converter,
    CurlSpec,
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
    jn_path: Path,
    name: str,
    driver: Literal["exec", "shell", "curl", "file"],
    argv: Optional[List[str]] = None,
    cmd: Optional[str] = None,
    url: Optional[str] = None,
    method: str = "GET",
    path: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> Project:
    """
    Add a new source to the project.

    Args:
        jn_path: Path to jn.json
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
        Updated Project instance

    Raises:
        ValueError: If source name already exists
        ValueError: If required driver-specific args missing
    """
    # Load existing project
    data = load_json(jn_path)
    project = Project.model_validate(data)

    # Check for duplicate name
    if any(s.name == name for s in project.sources):
        raise ValueError(f"Source '{name}' already exists")

    # Build the source based on driver
    if driver == "exec":
        if not argv:
            raise ValueError("--argv required for exec driver")
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
        if not cmd:
            raise ValueError("--cmd required for shell driver")
        source = Source(
            name=name,
            driver="shell",
            shell=ShellSpec(cmd=cmd),
        )
    elif driver == "curl":
        if not url:
            raise ValueError("--url required for curl driver")
        source = Source(
            name=name,
            driver="curl",
            curl=CurlSpec(
                method=method,
                url=url,
            ),
        )
    elif driver == "file":
        if not path:
            raise ValueError("--path required for file driver")
        source = Source(
            name=name,
            driver="file",
            file=FileSpec(
                path=path,
                mode="read",
            ),
        )
    else:
        raise ValueError(f"Unknown driver: {driver}")

    # Add source to project
    project.sources.append(source)

    # Validate the updated project (Pydantic will check uniqueness)
    project = Project.model_validate(project.model_dump())

    # Write back to file
    save_json(jn_path, project.model_dump(exclude_none=True))

    return project


def add_target(
    jn_path: Path,
    name: str,
    driver: Literal["exec", "shell", "curl", "file"],
    argv: Optional[List[str]] = None,
    cmd: Optional[str] = None,
    url: Optional[str] = None,
    method: str = "POST",
    path: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> Project:
    """
    Add a new target to the project.

    Similar to add_source but for targets.
    """
    # Load existing project
    data = load_json(jn_path)
    project = Project.model_validate(data)

    # Check for duplicate name
    if any(t.name == name for t in project.targets):
        raise ValueError(f"Target '{name}' already exists")

    # Build the target based on driver
    if driver == "exec":
        if not argv:
            raise ValueError("--argv required for exec driver")
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
        if not cmd:
            raise ValueError("--cmd required for shell driver")
        target = Target(
            name=name,
            driver="shell",
            shell=ShellSpec(cmd=cmd),
        )
    elif driver == "curl":
        if not url:
            raise ValueError("--url required for curl driver")
        target = Target(
            name=name,
            driver="curl",
            curl=CurlSpec(
                method=method,
                url=url,
            ),
        )
    elif driver == "file":
        if not path:
            raise ValueError("--path required for file driver")
        target = Target(
            name=name,
            driver="file",
            file=FileSpec(
                path=path,
                mode="write",
            ),
        )
    else:
        raise ValueError(f"Unknown driver: {driver}")

    # Add target to project
    project.targets.append(target)

    # Validate the updated project
    project = Project.model_validate(project.model_dump())

    # Write back to file
    save_json(jn_path, project.model_dump(exclude_none=True))

    return project


def add_converter(
    jn_path: Path,
    name: str,
    expr: Optional[str] = None,
    file: Optional[str] = None,
    raw: bool = False,
    modules: Optional[str] = None,
) -> Project:
    """
    Add a new converter to the project.

    Args:
        jn_path: Path to jn.json
        name: Converter name
        expr: jq expression (inline)
        file: Path to jq filter file
        raw: Whether to output raw strings
        modules: Path to jq modules directory

    Returns:
        Updated Project instance

    Raises:
        ValueError: If converter name already exists
        ValueError: If neither expr nor file is provided
    """
    # Load existing project
    data = load_json(jn_path)
    project = Project.model_validate(data)

    # Check for duplicate name
    if any(c.name == name for c in project.converters):
        raise ValueError(f"Converter '{name}' already exists")

    # Require either expr or file
    if not expr and not file:
        raise ValueError(
            "Either --expr or --file is required for jq converter"
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

    # Add converter to project
    project.converters.append(converter)

    # Validate the updated project
    project = Project.model_validate(project.model_dump())

    # Write back to file
    save_json(jn_path, project.model_dump(exclude_none=True))

    return project


def add_pipeline(
    jn_path: Path,
    name: str,
    steps: List[str],
    params: Optional[Dict[str, any]] = None,
) -> Project:
    """
    Add a new pipeline to the project.

    Args:
        jn_path: Path to jn.json
        name: Pipeline name
        steps: List of step specifications in format "type:ref" (e.g., "source:echo")
        params: Optional pipeline parameters

    Returns:
        Updated Project instance

    Raises:
        ValueError: If pipeline name already exists
        ValueError: If steps is empty
        ValueError: If step format is invalid
    """
    # Load existing project
    data = load_json(jn_path)
    project = Project.model_validate(data)

    # Check for duplicate name
    if any(p.name == name for p in project.pipelines):
        raise ValueError(f"Pipeline '{name}' already exists")

    # Require at least one step
    if not steps:
        raise ValueError("Pipeline requires at least one step (--steps)")

    # Parse steps
    parsed_steps = []
    for step_spec in steps:
        if ":" not in step_spec:
            raise ValueError(
                f"Invalid step format: '{step_spec}'. Expected 'type:ref' (e.g., 'source:echo')"
            )

        step_type, step_ref = step_spec.split(":", 1)

        if step_type not in ["source", "converter", "target"]:
            raise ValueError(
                f"Invalid step type: '{step_type}'. Must be 'source', 'converter', or 'target'"
            )

        parsed_steps.append(Step(type=step_type, ref=step_ref))

    # Build the pipeline
    pipeline = Pipeline(
        name=name,
        steps=parsed_steps,
        params=params or {},
    )

    # Add pipeline to project
    project.pipelines.append(pipeline)

    # Validate the updated project
    project = Project.model_validate(project.model_dump())

    # Write back to file
    save_json(jn_path, project.model_dump(exclude_none=True))

    return project
