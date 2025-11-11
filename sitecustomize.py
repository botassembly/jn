"""Enable coverage.py in subprocesses when COVERAGE_PROCESS_START is set.

Python automatically imports this module on startup if it is importable.
We keep it at project root so that test subprocesses inherit it via CWD.
"""

import os


if os.getenv("COVERAGE_PROCESS_START"):
    try:
        import coverage

        coverage.process_startup()
    except Exception:
        # Fail quietly if coverage isn't available in the subprocess
        pass

