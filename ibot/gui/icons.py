"""Load app icon images for tkinter (system Tk only supports GIF/PPM)."""

from __future__ import annotations

import subprocess
import tkinter as tk
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
ICON_PNG = ASSETS / "icon.png"
ICON_GIF = ASSETS / "icon.gif"


def _ensure_gif() -> Path | None:
    if ICON_GIF.is_file():
        return ICON_GIF
    if not ICON_PNG.is_file():
        return None
    try:
        subprocess.run(
            ["sips", "-s", "format", "gif", str(ICON_PNG), "--out", str(ICON_GIF)],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return ICON_GIF if ICON_GIF.is_file() else None


def load_tk_icons() -> dict[str, tk.PhotoImage]:
    path = _ensure_gif()
    if not path:
        return {}
    try:
        full = tk.PhotoImage(file=str(path))
    except tk.TclError:
        return {}
    return {
        "full": full,
        "win": full.subsample(4, 4),
        "avatar": full.subsample(16, 16),
        "title": full.subsample(28, 28),
    }
