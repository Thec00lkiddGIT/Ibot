"""Persist poll watermark for the bot."""

from __future__ import annotations

import json
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parents[1] / ".state.json"
STATS_FILE = Path(__file__).resolve().parents[1] / ".gui_stats.json"
GUI_SETTINGS_FILE = Path(__file__).resolve().parents[1] / ".gui_settings.json"

DEFAULT_GUI_SETTINGS = {
    "include_self": True,
    "verbose": True,
    "catch_up": False,
    "autostart": True,
}


def load_state() -> int:
    if not STATE_FILE.exists():
        return 0
    try:
        data = json.loads(STATE_FILE.read_text())
        return int(data.get("last_rowid", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0


def save_state(last_rowid: int) -> None:
    STATE_FILE.write_text(json.dumps({"last_rowid": last_rowid}, indent=2) + "\n")


def load_stats() -> dict:
    if not STATS_FILE.exists():
        return {"commands_used": 0, "messages_seen": 0}
    try:
        data = json.loads(STATS_FILE.read_text())
        return {
            "commands_used": int(data.get("commands_used", 0)),
            "messages_seen": int(data.get("messages_seen", 0)),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"commands_used": 0, "messages_seen": 0}


def load_gui_settings() -> dict:
    data = dict(DEFAULT_GUI_SETTINGS)
    if not GUI_SETTINGS_FILE.exists():
        return data
    try:
        raw = json.loads(GUI_SETTINGS_FILE.read_text())
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
    GUI_SETTINGS_FILE.write_text(json.dumps(data, indent=2) + "\n")
    return data


def save_stats(commands_used: int, messages_seen: int) -> None:
    STATS_FILE.write_text(
        json.dumps(
            {"commands_used": commands_used, "messages_seen": messages_seen},
            indent=2,
        )
        + "\n"
    )
