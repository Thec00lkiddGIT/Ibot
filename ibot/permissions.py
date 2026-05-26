"""Detect which app needs Full Disk Access and verify chat.db access."""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = Path.home() / "Library" / "Messages" / "chat.db"

# Well-known host apps → what to add in System Settings
HOST_HINTS: dict[str, str] = {
    "Cursor": "Cursor (/Applications/Cursor.app)",
    "Code": "Visual Studio Code (/Applications/Visual Studio Code.app)",
    "iTerm": "iTerm",
    "Warp": "Warp",
    "Terminal": "Terminal (/Applications/Utilities/Terminal.app)",
    "Ibot": "Ibot (double-click Ibot.app on Desktop)",
    "Python": "Python (see path below - add the interpreter running gui.py)",
}


@dataclass(frozen=True)
class AccessReport:
    db_path: Path
    db_exists: bool
    os_readable: bool
    sqlite_ok: bool
    host_app: str
    python: str
    error: str | None = None


def _parent_host_app() -> str:
    """Walk up the process tree and return the first recognizable host app name."""
    if os.environ.get("IBOT_GUI_LAUNCHED") == "1":
        return "Ibot"

    if os.environ.get("TERM_PROGRAM"):
        return os.environ["TERM_PROGRAM"]

    try:
        import subprocess

        pid = os.getpid()
        seen: set[int] = set()
        chain: list[str] = []
        for _ in range(30):
            if pid in seen or pid <= 0:
                break
            seen.add(pid)
            out = subprocess.run(
                ["ps", "-o", "comm=", "-p", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
            name = (out.stdout or "").strip()
            if name:
                chain.append(name)
            for key in HOST_HINTS:
                if key in name:
                    return name
            ppid = subprocess.run(
                ["ps", "-o", "ppid=", "-p", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
            pid = int((ppid.stdout or "0").strip() or "0")

        for name in chain:
            lower = name.lower()
            if "cursor" in lower:
                return "Cursor"
            if "code helper" in lower or name.endswith("Code"):
                return "Visual Studio Code"
            if "iterm" in lower:
                return "iTerm"
            if "warp" in lower:
                return "Warp"
            if name in ("/bin/zsh", "zsh", "bash"):
                continue
            if "terminal" in lower:
                return "Terminal"
            if "ibot" in lower:
                return "Ibot"
            if "python" in lower:
                return "Python"

        return chain[-1] if chain else "unknown"
    except Exception:
        return os.environ.get("TERM_PROGRAM") or "unknown"


def check_access(db_path: Path | None = None) -> AccessReport:
    path = db_path or DEFAULT_DB
    exists = path.exists()
    readable = os.access(path, os.R_OK) if exists else False
    sqlite_ok = False
    error: str | None = None

    if exists and readable:
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            conn.execute("SELECT 1 FROM message LIMIT 1").fetchone()
            conn.close()
            sqlite_ok = True
        except sqlite3.Error as exc:
            error = str(exc)
    elif exists:
        error = "permission denied (TCC blocks read despite file existing)"
    else:
        error = "database file not found"

    return AccessReport(
        db_path=path,
        db_exists=exists,
        os_readable=readable,
        sqlite_ok=sqlite_ok,
        host_app=_parent_host_app(),
        python=sys.executable,
        error=error,
    )


def fda_target_for_host(host_app: str, *, python: str | None = None) -> str:
    lower = host_app.lower()
    if "ibot" in lower:
        return HOST_HINTS["Ibot"]
    if "python" in lower:
        exe = python or sys.executable
        return f"Python ({exe})"
    if "cursor" in lower:
        return HOST_HINTS["Cursor"]
    if "code" in lower or "vscode" in lower or "visual studio code" in lower:
        return HOST_HINTS["Code"]
    if "iterm" in lower:
        return HOST_HINTS["iTerm"]
    if "warp" in lower:
        return HOST_HINTS["Warp"]
    if "terminal" in lower:
        return HOST_HINTS["Terminal"]
    for key, label in HOST_HINTS.items():
        if key in host_app:
            return label
    return f"the app running this terminal ({host_app})"


def format_check_report(report: AccessReport) -> str:
    lines = [
        "Ibot permission check",
        "─────────────────────",
        f"  Python:     {report.python}",
        f"  Host app:   {report.host_app}",
        f"  Database:   {report.db_path}",
        f"  Exists:     {report.db_exists}",
        f"  Readable:   {report.os_readable}",
        f"  SQLite OK:  {report.sqlite_ok}",
    ]
    if report.error:
        lines.append(f"  Error:      {report.error}")

    if report.sqlite_ok:
        lines.append("")
        lines.append("✓ Full Disk Access looks good. Run: python3 bot.py")
        return "\n".join(lines)

    target = fda_target_for_host(report.host_app, python=report.python)
    lines.extend(
        [
            "",
            "✗ Cannot read chat.db",
            "",
            "Full Disk Access is per-app. If you enabled Terminal but run the bot",
            "inside Cursor (or VS Code), that does NOT count - add the editor instead.",
            "",
            "Fix:",
            f"  1. System Settings → Privacy & Security → Full Disk Access",
            f"  2. Click + and add: {target}",
            "  3. Ensure the toggle is ON",
            "  4. Quit that app completely (Cmd+Q), then reopen it",
            "  5. Run: python3 bot.py --check",
            "",
            "Or run the bot from Terminal.app (after Terminal has FDA):",
            "  open -a Terminal",
            f"  cd {Path(__file__).resolve().parents[1]}",
            "  python3 bot.py",
        ]
    )
    return "\n".join(lines)
