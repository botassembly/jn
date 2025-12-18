"""Build Zig binaries for CI.

CI uses this module to compile `zq` and Zig plugins on demand without relying on
prebuilt artifacts in the repo workspace.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

_CACHE_DIR = Path.home() / ".local" / "jn" / "bin"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _exe_suffix() -> str:
    return ".exe" if platform.system() == "Windows" else ""


def _zig_cmd() -> list[str]:
    zig = shutil.which("zig")
    if zig:
        return [zig]
    return [sys.executable, "-m", "ziglang"]


def _hash_files(paths: list[Path]) -> str:
    hasher = hashlib.sha256()
    for path in sorted({p.resolve() for p in paths}):
        hasher.update(path.read_bytes())
    return hasher.hexdigest()[:12]


def _zig_files_under(dir_path: Path) -> list[Path]:
    return [p for p in dir_path.rglob("*.zig") if p.is_file()]


def _build_zig_binary(
    *,
    output_stem: str,
    cwd: Path,
    source_file: Path | None,
    extra_args: list[str],
    hash_inputs: list[Path],
) -> Path:
    digest = _hash_files(hash_inputs)
    output_path = _CACHE_DIR / f"{output_stem}-{digest}{_exe_suffix()}"

    if output_path.exists() and (platform.system() == "Windows" or os.access(output_path, os.X_OK)):
        return output_path

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [*_zig_cmd(), "build-exe"]
    if source_file is not None:
        cmd.append(str(source_file))
    cmd.extend(["-fllvm", "-O", "ReleaseFast"])
    cmd.extend(extra_args)
    cmd.append(f"-femit-bin={output_path}")

    result = subprocess.run(  # noqa: S603  # CI build output is small and captured for errors
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0 or not output_path.exists():
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"zig build failed for {output_stem}: {stderr}")

    if platform.system() != "Windows":
        output_path.chmod(0o755)

    return output_path


def build_zq() -> str:
    """Build ZQ and return the path to the compiled binary."""
    repo_root = _repo_root()
    source_file = repo_root / "zq" / "src" / "main.zig"
    if not source_file.exists():
        raise FileNotFoundError(source_file)

    output_path = _build_zig_binary(
        output_stem="zq",
        cwd=source_file.parent,
        source_file=source_file,
        extra_args=[],
        hash_inputs=[source_file],
    )
    return str(output_path)


def build_zig_plugin(plugin_name: str, plugin_dir: Path) -> str:
    """Build a Zig plugin and return the path to the compiled binary."""
    source_file = plugin_dir / "main.zig"
    if not source_file.exists():
        raise FileNotFoundError(source_file)

    libs_root = _repo_root() / "libs" / "zig"
    jn_core = libs_root / "jn-core" / "src"
    jn_cli = libs_root / "jn-cli" / "src"
    jn_plugin = libs_root / "jn-plugin" / "src"

    module_flags = [
        "--dep",
        "jn-core",
        "--dep",
        "jn-cli",
        "--dep",
        "jn-plugin",
        "-Mroot=main.zig",
        f"-Mjn-core={jn_core / 'root.zig'}",
        f"-Mjn-cli={jn_cli / 'root.zig'}",
        f"-Mjn-plugin={jn_plugin / 'root.zig'}",
    ]

    hash_inputs = [
        *_zig_files_under(plugin_dir),
        *_zig_files_under(jn_core),
        *_zig_files_under(jn_cli),
        *_zig_files_under(jn_plugin),
    ]

    output_path = _build_zig_binary(
        output_stem=plugin_name,
        cwd=plugin_dir,
        source_file=None,
        extra_args=module_flags,
        hash_inputs=hash_inputs,
    )
    return str(output_path)

