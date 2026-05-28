"""Push log lines to the GUI event feed, stderr, and activity.log."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from ibot.paths import app_support_dir, ensure_app_support

_emit: Callable[[str, str, str, str], None] | None = None
_line_no = 0


def set_emitter(fn: Callable[[str, str, str, str], None] | None) -> None:
    global _emit
    _emit = fn


def clear_activity_log() -> None:
    """Remove persisted activity log (fresh GUI session / release build)."""
    global _line_no
    ensure_app_support()
    path = app_support_dir() / "activity.log"
    path.write_text("", encoding="utf-8")
    _line_no = 0


def _append_file(kind: str, title: str, body: str, source: str) -> int:
    global _line_no
    ensure_app_support()
    path = app_support_dir() / "activity.log"
    _line_no += 1
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"[{ts}] [{kind}] [{source}] {title}"
    if body:
        line += f" — {body}"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return _line_no


def _push_runtime(kind: str, title: str, body: str, source: str) -> None:
    if _emit is not None:
        _emit(kind, title, body, source)
        return
    try:
        from ibot.runtime import get_runtime

        rt = get_runtime()
        if getattr(rt, "_push_event", None):
            rt._push_event(kind, title, body, source)
            set_emitter(rt._push_event)
    except Exception:
        pass


def emit(kind: str, title: str, body: str = "", source: str = "Ibot") -> None:
    line = f"{title}: {body}" if body else title
    print(f"[{kind}] [{source}] {line}", file=sys.stderr, flush=True)
    _append_file(kind, title, body, source)
    _push_runtime(kind, title, body, source)


def info(title: str, body: str = "", source: str = "Ibot") -> None:
    emit("info", title, body, source)


def success(title: str, body: str = "", source: str = "Ibot") -> None:
    emit("success", title, body, source)


def error(title: str, body: str = "", source: str = "Ibot") -> None:
    emit("error", title, body, source)


def read_activity_log(after_line: int = 0, limit: int = 80) -> list[dict]:
    path = app_support_dir() / "activity.log"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[dict] = []
    for idx, raw in enumerate(lines, start=1):
        if idx <= after_line:
            continue
        kind = "info"
        if "] [error]" in raw.lower() or "[error]" in raw.lower():
            kind = "error"
        elif "] [success]" in raw.lower() or "[success]" in raw.lower():
            kind = "success"
        out.append({"line": idx, "kind": kind, "text": raw})
        if len(out) >= limit:
            break
    return out
