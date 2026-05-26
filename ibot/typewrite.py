"""Typewriter effect: edit the same iMessage bubble in place (Messages -> Edit)."""

from __future__ import annotations

import subprocess
import time

from ibot.messages_ui import edit_last_outgoing_message as _edit_message

STEP_DELAY_SECONDS = 1.0
UI_DELAY_SECONDS = 0.6

_OPEN_CHAT_SCRIPT = r'''
on run argv
    set targetKey to item 1 of argv
    tell application "Messages"
        activate
        try
            set targetChat to chat id targetKey
            return "ok-id"
        end try
        repeat with c in chats
            try
                if (id of c as text) is targetKey then
                    return "ok"
                end if
            end try
            try
                if (guid of c as text) is targetKey then
                    return "ok"
                end if
            end try
        end repeat
    end tell
    return "not-found"
end run
'''


def progressive_prefixes(text: str) -> list[str]:
    text = text.replace("\n", " ")
    if not text:
        return []
    return [text[:i] for i in range(1, len(text) + 1)]


def _run_script(script: str, *args: str) -> str:
    result = subprocess.run(
        ["/usr/bin/osascript", "-", *args],
        input=script,
        capture_output=True,
        text=True,
    )
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0:
        raise RuntimeError(err or out or "osascript failed")
    return out


def open_chat(chat_guid: str | None, chat_identifier: str | None) -> None:
    key = chat_guid or chat_identifier
    if not key:
        raise RuntimeError("No chat to open for typewrite")
    status = _run_script(_OPEN_CHAT_SCRIPT, key)
    if status.startswith("not-found"):
        raise RuntimeError(f"Could not open chat: {key}")


def edit_last_outgoing_message(new_text: str) -> None:
    status = _edit_message(new_text)
    if status.startswith("ok"):
        return
    hint = (
        "System Settings → Privacy & Security → Accessibility: enable "
        "Visual Studio Code (and try adding /usr/bin/osascript). "
        "Open the chat in Messages, click the window once, then retry."
    )
    if status == "fail:no-edit-menu":
        raise RuntimeError(
            f"Could not open Edit menu. Right-click your last message - if Edit is missing, "
            f"iMessage won't allow edits. {hint}"
        )
    if status == "fail:no-process":
        raise RuntimeError(f"Messages is not running. {hint}")
    raise RuntimeError(f"{status}. {hint}")


def run_typewrite(
    chat_guid: str | None,
    chat_identifier: str | None,
    handle_id: str | None,  # noqa: ARG001
    text: str,
    *,
    step_delay: float = STEP_DELAY_SECONDS,
) -> None:
    prefixes = progressive_prefixes(text)
    if not prefixes:
        raise ValueError("Nothing to typewrite")

    open_chat(chat_guid, chat_identifier)
    time.sleep(UI_DELAY_SECONDS)

    for i, prefix in enumerate(prefixes, start=1):
        if i > 1:
            time.sleep(step_delay)
        edit_last_outgoing_message(prefix)
        print(f"  typewrite: [{i}/{len(prefixes)}] edited → {prefix!r}")
