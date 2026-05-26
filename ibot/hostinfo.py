"""Mac host / computer name for the GUI profile."""

from __future__ import annotations

import os
import socket
import subprocess


def computer_handle() -> str:
    """Friendly computer name for @handle (not Mac.lan)."""
    env = os.environ.get("IBOT_HANDLE", "").strip()
    if env:
        return env

    if os.uname().sysname == "Darwin":
        for key in ("ComputerName", "LocalHostName"):
            try:
                out = subprocess.run(
                    ["scutil", "--get", key],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=True,
                )
                name = out.stdout.strip()
                if name:
                    return name
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue

    host = socket.gethostname() or "Mac"
    return host.split(".")[0]
