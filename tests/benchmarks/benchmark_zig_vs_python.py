#!/usr/bin/env python3
"""Performance benchmarks comparing Python CLI vs Zig tools.

This script measures:
1. Startup time (running with --help)
2. Throughput (processing NDJSON data)
3. Memory usage (peak RSS)

Usage:
    python tests/benchmarks/benchmark_zig_vs_python.py [--records N]
"""

import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path


# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
ZIG_TOOLS_DIR = PROJECT_ROOT / "tools" / "zig"
JN_HOME = PROJECT_ROOT / "jn_home"


def get_zig_tool_path(name: str) -> Path:
    """Get path to a Zig tool binary."""
    return ZIG_TOOLS_DIR / name / "bin" / name


def generate_test_data(num_records: int) -> str:
    """Generate NDJSON test data."""
    lines = []
    for i in range(num_records):
        record = {
            "id": i,
            "name": f"User_{i}",
            "email": f"user{i}@example.com",
            "age": 20 + (i % 60),
            "score": (i * 17) % 100,
            "active": i % 2 == 0,
        }
        lines.append(json.dumps(record))
    return "\n".join(lines) + "\n"


def measure_startup_time(cmd: list, iterations: int = 10) -> float:
    """Measure average startup time (running --help)."""
    env = os.environ.copy()
    env["JN_HOME"] = str(JN_HOME)

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        result = subprocess.run(
            cmd + ["--help"],
            capture_output=True,
            env=env,
        )
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return sum(times) / len(times) * 1000  # ms


def measure_throughput(cmd: list, input_data: str) -> tuple:
    """Measure throughput and return (records/sec, elapsed_ms)."""
    env = os.environ.copy()
    env["JN_HOME"] = str(JN_HOME)

    start = time.perf_counter()
    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        env=env,
    )
    elapsed = time.perf_counter() - start

    num_records = input_data.count("\n")
    records_per_sec = num_records / elapsed if elapsed > 0 else 0

    return records_per_sec, elapsed * 1000


def measure_memory(cmd: list, input_data: str) -> int:
    """Measure peak memory usage in KB."""
    env = os.environ.copy()
    env["JN_HOME"] = str(JN_HOME)

    # Use /usr/bin/time for memory measurement if available
    time_cmd = ["/usr/bin/time", "-v"] + cmd

    try:
        result = subprocess.run(
            time_cmd,
            input=input_data,
            capture_output=True,
            text=True,
            env=env,
        )
        # Parse memory from stderr (GNU time format)
        for line in result.stderr.split("\n"):
            if "Maximum resident set size" in line:
                return int(line.split(":")[-1].strip())
    except FileNotFoundError:
        pass

    return 0  # Could not measure


def run_benchmarks(num_records: int = 10000):
    """Run all benchmarks."""
    print(f"\n{'=' * 60}")
    print(f"JN Performance Benchmarks: Python CLI vs Zig Tools")
    print(f"{'=' * 60}")
    print(f"Test data: {num_records:,} NDJSON records")
    print()

    # Generate test data
    print("Generating test data...", end=" ", flush=True)
    test_data = generate_test_data(num_records)
    data_size = len(test_data) / 1024 / 1024  # MB
    print(f"({data_size:.1f} MB)")
    print()

    # Define tools to benchmark
    benchmarks = [
        ("Startup Time (--help)", lambda cmd: f"{measure_startup_time(cmd):.2f} ms"),
        ("Head (first 100)", lambda cmd: f"{measure_throughput(cmd + ['--lines=100'] if 'jn-head' in str(cmd) else cmd + ['head', '-n', '100'], test_data)[1]:.1f} ms"),
    ]

    # Startup time comparison
    print("-" * 60)
    print("STARTUP TIME (--help, 10 iterations)")
    print("-" * 60)

    tools = [
        ("Python CLI (jn)", ["uv", "run", "jn"]),
        ("Zig jn-cat", [str(get_zig_tool_path("jn-cat"))]),
        ("Zig jn-head", [str(get_zig_tool_path("jn-head"))]),
        ("Zig jn-tail", [str(get_zig_tool_path("jn-tail"))]),
        ("Zig jn-filter", [str(get_zig_tool_path("jn-filter"))]),
        ("Zig jn (orchestrator)", [str(get_zig_tool_path("jn"))]),
    ]

    results = []
    for name, cmd in tools:
        if not Path(cmd[0] if cmd[0] != "uv" else "/usr/bin/true").exists() and cmd[0] != "uv":
            continue
        try:
            startup_ms = measure_startup_time(cmd)
            results.append((name, startup_ms))
            print(f"  {name:30} {startup_ms:8.2f} ms")
        except Exception as e:
            print(f"  {name:30} ERROR: {e}")

    # Find baseline (Python) and calculate speedups
    python_startup = next((t for n, t in results if "Python" in n), None)
    if python_startup:
        print()
        print("  Speedup vs Python:")
        for name, startup_ms in results:
            if "Python" not in name:
                speedup = python_startup / startup_ms
                print(f"    {name:28} {speedup:.1f}x faster")

    # Throughput comparison
    print()
    print("-" * 60)
    print(f"THROUGHPUT ({num_records:,} records)")
    print("-" * 60)

    throughput_tests = [
        ("Python jn head -n 100", ["uv", "run", "jn", "head", "-n", "100"]),
        ("Zig jn-head --lines=100", [str(get_zig_tool_path("jn-head")), "--lines=100"]),
        ("Python jn tail -n 100", ["uv", "run", "jn", "tail", "-n", "100"]),
        ("Zig jn-tail --lines=100", [str(get_zig_tool_path("jn-tail")), "--lines=100"]),
    ]

    for name, cmd in throughput_tests:
        if cmd[0] != "uv" and not Path(cmd[0]).exists():
            continue
        try:
            records_per_sec, elapsed_ms = measure_throughput(cmd, test_data)
            print(f"  {name:30} {elapsed_ms:8.1f} ms  ({records_per_sec:,.0f} rec/s)")
        except Exception as e:
            print(f"  {name:30} ERROR: {e}")

    # Memory usage
    print()
    print("-" * 60)
    print("PEAK MEMORY USAGE")
    print("-" * 60)

    memory_tests = [
        ("Zig jn-head", [str(get_zig_tool_path("jn-head")), "--lines=100"]),
        ("Zig jn-tail", [str(get_zig_tool_path("jn-tail")), "--lines=100"]),
    ]

    for name, cmd in memory_tests:
        if not Path(cmd[0]).exists():
            continue
        try:
            mem_kb = measure_memory(cmd, test_data)
            if mem_kb > 0:
                print(f"  {name:30} {mem_kb:,} KB ({mem_kb/1024:.1f} MB)")
            else:
                print(f"  {name:30} (could not measure)")
        except Exception as e:
            print(f"  {name:30} ERROR: {e}")

    print()
    print("=" * 60)
    print("Benchmark complete")
    print("=" * 60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Benchmark Python vs Zig performance")
    parser.add_argument("--records", type=int, default=10000, help="Number of test records")
    args = parser.parse_args()

    # Check Zig tools are built
    jn_cat = get_zig_tool_path("jn-cat")
    if not jn_cat.exists():
        print("ERROR: Zig tools not built. Run 'make zig-tools' first.")
        sys.exit(1)

    run_benchmarks(args.records)


if __name__ == "__main__":
    main()
