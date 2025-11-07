"""File driver: read and write files with safety checks."""

from pathlib import Path
from typing import Optional

from jn.models import Completed


def run_file_read(
    path: str,
    *,
    allow_outside_config: bool = False,
    config_root: Optional[str] = None,
) -> Completed:
    """Read a file and return its contents as bytes.

    Args:
        path: File path to read
        allow_outside_config: If False, restrict reads to config root
        config_root: Root directory for confinement (default: cwd)

    Returns:
        Completed with file contents in stdout

    Raises:
        ValueError: If path escapes config_root when not allowed
        FileNotFoundError: If file doesn't exist
    """
    file_path = Path(path).resolve()

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

    try:
        data = file_path.read_bytes()
        return Completed(returncode=0, stdout=data, stderr=b"")
    except FileNotFoundError:
        return Completed(
            returncode=1,
            stdout=b"",
            stderr=f"File not found: {path}".encode(),
        )
    except Exception as e:
        return Completed(returncode=1, stdout=b"", stderr=str(e).encode())


def run_file_write(
    path: str,
    data: bytes,
    *,
    append: bool = False,
    create_parents: bool = False,
    allow_outside_config: bool = False,
    config_root: Optional[str] = None,
) -> Completed:
    """Write bytes to a file.

    Args:
        path: File path to write
        data: Bytes to write
        append: If True, append to file; otherwise overwrite
        create_parents: If True, create parent directories
        allow_outside_config: If False, restrict writes to config root
        config_root: Root directory for confinement (default: cwd)

    Returns:
        Completed with success/failure status

    Raises:
        ValueError: If path escapes config_root when not allowed
    """
    file_path = Path(path).resolve()

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

    try:
        # Create parent directories if requested
        if create_parents:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write or append
        mode = "ab" if append else "wb"
        with file_path.open(mode) as f:
            f.write(data)

        return Completed(returncode=0, stdout=data, stderr=b"")
    except Exception as e:
        return Completed(returncode=1, stdout=b"", stderr=str(e).encode())


__all__ = ["run_file_read", "run_file_write"]
