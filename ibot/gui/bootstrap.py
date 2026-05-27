"""Load saved GUI settings and optionally start the bot loop."""

from __future__ import annotations

import os

from ibot.paths import ensure_env_file, ensure_script_hub
from ibot.runtime import get_runtime
from ibot.state import load_gui_settings, save_gui_settings


def prepare_runtime(*, autostart: bool | None = None) -> None:
    """Apply persisted toggles and start polling unless disabled."""
    ensure_env_file()
    ensure_script_hub()
    settings = load_gui_settings()
    rt = get_runtime()
    rt.update_settings(
        include_self=bool(settings["include_self"]),
        verbose=bool(settings["verbose"]),
        catch_up=bool(settings["catch_up"]),
        afk_enabled=bool(settings.get("afk_enabled", False)),
        afk_message=str(settings.get("afk_message", "")),
    )

    should_start = settings["autostart"] if autostart is None else autostart
    if os.environ.get("IBOT_NO_AUTOSTART") == "1":
        should_start = False

    if should_start:
        rt.start()
