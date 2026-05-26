"""Detect which app needs Full Disk Access and verify chat.db access."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = Path.home() / "Library" / "Messages" / "chat.db"

HOST_HINTS: dict[str, str] = {
    "Cursor": "Cursor (/Applications/Cursor.app)",
    "Code": "Visual Studio Code (/Applications/Visual Studio Code.app)",
    "iTerm": "iTerm",
    "Warp": "Warp",
    "Terminal": "Terminal (/Applications/Utilities/Terminal.app)",
}


@dataclass(frozen=True)
class AccessReport:
    db_path: Path
    db_exists: bool
    os_readable: bool
    sqlite_ok: bool
    host_app: str
    python: str
    app_bundle: str | None = None
    error: str | None = None


def is_app_bundle() -> bool:
    if os.environ.get("IBOT_APP_BUNDLE") == "1":
        return True
    return "Ibot.app" in str(Path(sys.executable).resolve())


def app_bundle_path() -> Path | None:
    env = os.environ.get("IBOT_APP_PATH")
    if env:
        p = Path(env)
        if p.is_dir():
            return p
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.name.endswith(".app"):
            return parent
    return None


def open_fda_settings() -> bool:
    """Open macOS Full Disk Access settings (best-effort)."""
    urls = (
        "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_AllFiles",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",
    )
    for url in urls:
        try:
            result = subprocess.run(["open", url], check=False, capture_output=True)
            if result.returncode == 0:
                return True
        except OSError:
            continue
    return False


def _parent_host_app() -> str:
    if is_app_bundle():
        app = app_bundle_path()
        return str(app) if app else "Ibot.app"

    if os.environ.get("TERM_PROGRAM"):
        return os.environ["TERM_PROGRAM"]

    try:
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
            if "python" in lower:
                return "Python"

        return chain[-1] if chain else "unknown"
    except Exception:
        return os.environ.get("TERM_PROGRAM") or "unknown"


def fda_target_for_host(host_app: str, *, python: str | None = None) -> str:
    if is_app_bundle():
        return f"Python ({python or sys.executable})"
    lower = host_app.lower()
    if "python" in lower:
        return f"Python ({python or sys.executable})"
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


def bundle_fda_python_path() -> str | None:
    """Absolute Python path users should add in Full Disk Access for Ibot.app."""
    if not is_app_bundle():
        return None
    return str(Path(sys.executable).resolve())


def fda_fix_steps(*, python: str | None = None, host: str | None = None) -> list[str]:
    py = python or sys.executable
    host = host or _parent_host_app()

    if is_app_bundle():
        py = bundle_fda_python_path() or py
        steps = [
            "Open System Settings → Privacy & Security → Full Disk Access",
            "Click +, then press Cmd+Shift+G (Go to Folder)",
            "Paste the FULL path below (must start with /Applications) and press Go:",
            py,
            "Select python3 and click Open, then turn the toggle ON",
            "Quit Ibot completely (Cmd+Q), then reopen it",
        ]
        return steps

    target = fda_target_for_host(host, python=py)
    return [
        "Open System Settings → Privacy & Security → Full Disk Access",
        f"Click + and add: {target}",
        "Turn the toggle ON",
        "Quit that app completely (Cmd+Q), then reopen it",
        "Run: python3 bot.py --check",
    ]


def fda_fix_message(*, python: str | None = None, host: str | None = None) -> str:
    steps = fda_fix_steps(python=python, host=host)
    intro = (
        "macOS blocks chat.db until Full Disk Access is granted to the Python "
        "process inside Ibot.app (adding only the app icon often is not enough)."
        if is_app_bundle()
        else "Full Disk Access is per-app. The app that runs Python needs access."
    )
    body = "\n".join(f"  {i + 1}. {step}" for i, step in enumerate(steps))
    return f"{intro}\n\n{body}"


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

    bundle = app_bundle_path()
    return AccessReport(
        db_path=path,
        db_exists=exists,
        os_readable=readable,
        sqlite_ok=sqlite_ok,
        host_app=_parent_host_app(),
        python=sys.executable,
        app_bundle=str(bundle) if bundle else None,
        error=error,
    )


def format_check_report(report: AccessReport) -> str:
    lines = [
        "Ibot permission check",
        "─────────────────────",
        f"  Python:     {report.python}",
        f"  Host app:   {report.host_app}",
    ]
    if report.app_bundle:
        lines.append(f"  App bundle: {report.app_bundle}")
    lines.extend(
        [
            f"  Database:   {report.db_path}",
            f"  Exists:     {report.db_exists}",
            f"  Readable:   {report.os_readable}",
            f"  SQLite OK:  {report.sqlite_ok}",
        ]
    )
    if report.error:
        lines.append(f"  Error:      {report.error}")

    if report.sqlite_ok:
        lines.append("")
        lines.append("✓ Full Disk Access looks good. Run: python3 bot.py")
        return "\n".join(lines)

    lines.extend(["", "✗ Cannot read chat.db", "", fda_fix_message(python=report.python, host=report.host_app)])
    if is_app_bundle():
        lines.extend(["", "Tip: run `python3 bot.py --open-fda` inside the app folder to open System Settings."])
    return "\n".join(lines)
