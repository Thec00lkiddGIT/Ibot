"""Pick a Python interpreter that can run the native GUI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def python_with_tk() -> str:
    """Return path to a Python that imports tkinter, or sys.executable."""
    candidates: list[str] = []

    env = __import__("os").environ.get("IBOT_PYTHON", "").strip()
    if env:
        candidates.append(env)

    # Prefer macOS system / python.org builds before Homebrew (no tkinter).
    for path in (
        "/usr/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
    ):
        if Path(path).is_file() and path not in candidates:
            candidates.append(path)

    if sys.executable not in candidates:
        candidates.append(sys.executable)

    for exe in candidates:
        try:
            subprocess.run(
                [exe, "-c", "import tkinter"],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return exe
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
            continue
    return sys.executable
