"""Persist poll watermark and GUI prefs in Application Support."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ibot.paths import (
    app_support_dir,
    ensure_app_support,
    gui_settings_file,
    project_root,
    state_file,
    stats_file,
)

DEFAULT_GUI_SETTINGS = {
    "include_self": True,
    "verbose": True,
    "catch_up": False,
    "autostart": True,
    "afk_enabled": False,
    "afk_message": "I'm AFK right now — I'll reply when I'm back.",
}


def _migrate_legacy_file(name: str, dest: Path) -> None:
    if dest.exists():
        return
    legacy = project_root() / name
    if legacy.is_file():
        ensure_app_support()
        shutil.copy2(legacy, dest)


def _state_path() -> Path:
    path = state_file()
    _migrate_legacy_file(".state.json", path)
    return path


def _stats_path() -> Path:
    path = stats_file()
    _migrate_legacy_file(".gui_stats.json", path)
    return path


def _settings_path() -> Path:
    path = gui_settings_file()
    _migrate_legacy_file(".gui_settings.json", path)
    return path


def get_state_file() -> Path:
    return _state_path()


def load_state() -> int:
    path = _state_path()
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text())
        return int(data.get("last_rowid", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0


def save_state(last_rowid: int) -> None:
    ensure_app_support()
    _state_path().write_text(json.dumps({"last_rowid": last_rowid}, indent=2) + "\n")


def load_stats() -> dict:
    path = _stats_path()
    if not path.exists():
        return {"commands_used": 0, "messages_seen": 0}
    try:
        data = json.loads(path.read_text())
        return {
            "commands_used": int(data.get("commands_used", 0)),
            "messages_seen": int(data.get("messages_seen", 0)),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"commands_used": 0, "messages_seen": 0}


def load_gui_settings() -> dict:
    data = dict(DEFAULT_GUI_SETTINGS)
    path = _settings_path()
    if not path.exists():
        return data
    try:
        raw = json.loads(path.read_text())
        if isinstance(raw, dict):
            for key in DEFAULT_GUI_SETTINGS:
                if key in raw:
                    data[key] = raw[key]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return data


def save_gui_settings(**kwargs: object) -> dict:
    data = load_gui_settings()
    for key, value in kwargs.items():
        if key in DEFAULT_GUI_SETTINGS:
            data[key] = value
    ensure_app_support()
    _settings_path().write_text(json.dumps(data, indent=2) + "\n")
    return data


def save_stats(commands_used: int, messages_seen: int) -> None:
    ensure_app_support()
    _stats_path().write_text(
        json.dumps(
            {"commands_used": commands_used, "messages_seen": messages_seen},
            indent=2,
        )
        + "\n"
    )
