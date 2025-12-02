"""On-demand Zig binary compilation for cross-platform support.

This module compiles Zig binaries (ZQ, format plugins) on first use,
using the ziglang PyPI package for cross-platform Zig compiler access.

Binaries are cached in ~/.local/jn/bin/ to avoid recompilation.
"""

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Cache directory for compiled binaries
_CACHE_DIR = Path.home() / ".local" / "jn" / "bin"

# Minimum Zig version required for JN's Zig plugins
MIN_ZIG_VERSION = "0.15.1"


def _check_zig_version(cmd: list[str]) -> bool:
    """Check if Zig command meets minimum version requirement.

    Args:
        cmd: Command list to invoke Zig (e.g., ['zig'])

    Returns:
        True if version >= MIN_ZIG_VERSION, False otherwise
    """
    try:
        result = subprocess.run(
            [*cmd, "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False

        version = result.stdout.strip()
        # Parse version (e.g., "0.15.2" or "0.15.2-dev.1234")
        parts = version.split("-")[0].split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        min_parts = MIN_ZIG_VERSION.split(".")
        min_major, min_minor, min_patch = (
            int(min_parts[0]),
            int(min_parts[1]),
            int(min_parts[2]),
        )

        if major != min_major:
            return major > min_major
        if minor != min_minor:
            return minor > min_minor
        return patch >= min_patch
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    except (ValueError, IndexError):
        return False


def get_zig_command() -> list[str]:
    """Get the command to run Zig compiler.

    Resolution order (skips versions below MIN_ZIG_VERSION):
    1. System 'zig' in PATH (preferred if version compatible)
    2. 'python-zig' from ziglang package
    3. 'python -m ziglang' fallback

    Returns:
        Command list to invoke Zig (e.g., ['zig'] or ['python', '-m', 'ziglang'])
    """
    import shutil

    # 1. System zig (preferred if version is compatible)
    if shutil.which("zig") and _check_zig_version(["zig"]):
        return ["zig"]

    # 2. python-zig from ziglang package (if version compatible)
    if shutil.which("python-zig") and _check_zig_version(["python-zig"]):
        return ["python-zig"]

    # 3. python -m ziglang fallback (always return - it's our dependency)
    return [sys.executable, "-m", "ziglang"]


def get_zig_version() -> Optional[str]:
    """Get the Zig compiler version.

    Returns:
        Version string (e.g., '0.15.2') or None if not available
    """
    try:
        cmd = get_zig_command()
        result = subprocess.run(
            [*cmd, "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def is_zig_version_compatible() -> bool:
    """Check if installed Zig version is compatible.

    JN's Zig plugins require Zig 0.15.1+ (ziglang PyPI package compatible).

    Returns:
        True if Zig version is >= MIN_ZIG_VERSION
    """
    version = get_zig_version()
    if not version:
        return False

    try:
        # Parse version (e.g., "0.15.2" or "0.15.2-dev.1234")
        parts = version.split("-")[0].split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        min_parts = MIN_ZIG_VERSION.split(".")
        min_major, min_minor, min_patch = (
            int(min_parts[0]),
            int(min_parts[1]),
            int(min_parts[2]),
        )

        if major > min_major:
            return True
        if major < min_major:
            return False
        if minor > min_minor:
            return True
        if minor < min_minor:
            return False
        return patch >= min_patch
    except (ValueError, IndexError):
        return False


def get_source_hash(source_path: Path) -> str:
    """Get hash of source file(s) for cache invalidation.

    Args:
        source_path: Path to main source file

    Returns:
        SHA256 hash of source content (first 12 chars)
    """
    hasher = hashlib.sha256()

    if source_path.is_file():
        hasher.update(source_path.read_bytes())
    elif source_path.is_dir():
        # Hash all .zig files in directory
        for zig_file in sorted(source_path.glob("**/*.zig")):
            hasher.update(zig_file.read_bytes())

    return hasher.hexdigest()[:12]


def get_binary_name(name: str) -> str:
    """Get platform-appropriate binary name.

    Args:
        name: Base binary name (e.g., 'zq')

    Returns:
        Platform-specific name (e.g., 'zq.exe' on Windows)
    """
    if platform.system() == "Windows":
        return f"{name}.exe"
    return name


def get_cached_binary_path(name: str, source_hash: str) -> Path:
    """Get path to cached binary.

    Args:
        name: Binary name (e.g., 'zq')
        source_hash: Hash of source for versioning

    Returns:
        Path to cached binary (e.g., ~/.local/jn/bin/zq-abc123)
    """
    binary_name = get_binary_name(f"{name}-{source_hash}")
    return _CACHE_DIR / binary_name


def is_zig_available() -> bool:
    """Check if Zig compiler is available.

    Returns:
        True if Zig can be invoked, False otherwise
    """
    try:
        cmd = get_zig_command()
        result = subprocess.run(
            [*cmd, "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


_VERSION_WARNING_SHOWN = False


def build_zig_binary(
    source_path: Path,
    output_name: str,
    *,
    use_llvm: bool = True,
    optimize: str = "ReleaseFast",
    quiet: bool = False,
) -> Optional[Path]:
    """Build a Zig binary from source.

    Args:
        source_path: Path to main.zig source file
        output_name: Name for output binary (e.g., 'zq')
        use_llvm: Use LLVM backend (more stable, required for some targets)
        optimize: Optimization level (Debug, ReleaseSafe, ReleaseFast, ReleaseSmall)
        quiet: Suppress warning messages

    Returns:
        Path to compiled binary, or None if compilation failed
    """
    global _VERSION_WARNING_SHOWN

    if not source_path.exists():
        return None

    # Get source hash for cache key
    source_hash = get_source_hash(source_path)
    cached_path = get_cached_binary_path(output_name, source_hash)

    # Return cached binary if it exists and is executable
    if cached_path.exists() and os.access(cached_path, os.X_OK):
        return cached_path

    # Check Zig version compatibility before building
    if not is_zig_version_compatible():
        if not quiet and not _VERSION_WARNING_SHOWN:
            version = get_zig_version() or "not found"
            print(
                f"Note: Zig {version} found, but {MIN_ZIG_VERSION}+ required "
                f"for native plugins.",
                file=sys.stderr,
            )
            print(
                "  Native plugins will be skipped. Python fallbacks will be used.",
                file=sys.stderr,
            )
            print(
                f"  To enable native plugins, install Zig {MIN_ZIG_VERSION}+: "
                "https://ziglang.org/download/",
                file=sys.stderr,
            )
            _VERSION_WARNING_SHOWN = True
        return None

    # Ensure cache directory exists
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Build command
    zig_cmd = get_zig_command()
    cmd = [
        *zig_cmd,
        "build-exe",
        str(source_path),
        f"-O{optimize}",
        f"-femit-bin={cached_path}",
    ]

    if use_llvm:
        cmd.append("-fllvm")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            cwd=source_path.parent,  # Build from source directory
        )

        if result.returncode == 0 and cached_path.exists():
            # Make executable on Unix
            if platform.system() != "Windows":
                cached_path.chmod(0o755)
            return cached_path

        # Log error for debugging (only in verbose mode)
        if result.stderr and os.environ.get("JN_DEBUG"):
            print(f"Zig build error: {result.stderr}", file=sys.stderr)

    except subprocess.TimeoutExpired:
        if not quiet:
            print("Zig build timed out", file=sys.stderr)
    except FileNotFoundError:
        if not quiet:
            print("Zig compiler not found", file=sys.stderr)
    except OSError as e:
        if not quiet:
            print(f"Zig build failed: {e}", file=sys.stderr)

    return None


def _find_bundled_zig_src() -> Optional[Path]:
    """Find the bundled Zig sources directory.

    Returns:
        Path to jn_home/zig_src if it exists, None otherwise
    """
    try:
        from importlib import resources

        pkg = resources.files("jn_home").joinpath("zig_src")
        with resources.as_file(pkg) as p:
            if p.exists():
                return Path(p)
    except (ModuleNotFoundError, TypeError, FileNotFoundError):
        pass
    return None


def get_or_build_zq() -> Optional[Path]:
    """Get ZQ binary, building from source if needed.

    Resolution order:
    1. Cached binary in ~/.local/jn/bin/
    2. Build from bundled source (jn_home/zig_src/zq/)
    3. Development build in repo (zq/src/)

    Returns:
        Path to ZQ binary, or None if not available
    """
    # Find ZQ source - try multiple locations
    source_locations = []

    # Bundled with package (installed via wheel)
    bundled = _find_bundled_zig_src()
    if bundled:
        source_locations.append(bundled / "zq" / "main.zig")

    # Development locations (repo root)
    module_dir = Path(__file__).parent
    source_locations.extend([
        module_dir.parent.parent / "zq" / "src" / "main.zig",  # from src/jn/
        module_dir.parent.parent.parent / "zq" / "src" / "main.zig",  # deeper
    ])

    for source_path in source_locations:
        if source_path.exists():
            binary = build_zig_binary(source_path, "zq")
            if binary:
                return binary

    return None


def get_or_build_plugin(plugin_name: str) -> Optional[Path]:
    """Get Zig plugin binary, building from source if needed.

    Args:
        plugin_name: Plugin name (e.g., 'csv', 'json', 'jsonl')

    Returns:
        Path to plugin binary, or None if not available
    """
    # Find plugin source - try multiple locations
    source_locations = []

    # Bundled with package (installed via wheel)
    bundled = _find_bundled_zig_src()
    if bundled:
        source_locations.append(bundled / "plugins" / plugin_name / "main.zig")

    # Development locations (repo root)
    module_dir = Path(__file__).parent
    source_locations.extend([
        module_dir.parent.parent / "plugins" / "zig" / plugin_name / "main.zig",
        module_dir.parent.parent.parent / "plugins" / "zig" / plugin_name / "main.zig",
    ])

    for source_path in source_locations:
        if source_path.exists():
            binary = build_zig_binary(source_path, f"jn-{plugin_name}")
            if binary:
                return binary

    return None


def list_available_zig_plugins() -> list[str]:
    """List available Zig plugins that can be built.

    Returns:
        List of plugin names (e.g., ['csv', 'json', 'jsonl'])
    """
    plugins = set()

    # Check bundled location
    bundled = _find_bundled_zig_src()
    if bundled:
        plugins_dir = bundled / "plugins"
        if plugins_dir.exists():
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "main.zig").exists():
                    plugins.add(plugin_dir.name)

    # Check development locations
    module_dir = Path(__file__).parent
    for base in [module_dir.parent.parent, module_dir.parent.parent.parent]:
        dev_plugins = base / "plugins" / "zig"
        if dev_plugins.exists():
            for plugin_dir in dev_plugins.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "main.zig").exists():
                    plugins.add(plugin_dir.name)

    return sorted(plugins)


def ensure_all_binaries() -> dict[str, Optional[Path]]:
    """Build all Zig binaries if not already cached.

    This can be called during installation or first run to ensure
    all binaries are available.

    Returns:
        Dictionary mapping binary name to path (or None if build failed)
    """
    results = {}

    # Build ZQ
    results["zq"] = get_or_build_zq()

    # Build all Zig plugins
    for plugin_name in list_available_zig_plugins():
        results[plugin_name] = get_or_build_plugin(plugin_name)

    return results
