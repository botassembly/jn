"""Service layer: create new project items."""

from pathlib import Path
from typing import Dict, List, Literal, Optional

from ..home.io import load_json, save_json
from ..models.project import (
    CurlSpec,
    ExecSpec,
    FileSpec,
    Project,
    ShellSpec,
    Source,
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
