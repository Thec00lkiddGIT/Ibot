"""Send iMessages via the Messages app (AppleScript)."""

from __future__ import annotations

import subprocess

# argv: targetKey, messageText, mode
# modes: find_chat | participant | buddy | chat_id
_SEND_SCRIPT = r'''
on run argv
    set targetKey to item 1 of argv
    set messageText to item 2 of argv
    set sendMode to item 3 of argv

    tell application "Messages"
        activate

        if sendMode is "find_chat" then
            repeat with c in chats
                try
                    if (id of c as text) is targetKey then
                        send messageText to c
                        return "ok:id"
                    end if
                end try
                try
                    if (guid of c as text) is targetKey then
                        send messageText to c
                        return "ok:guid"
                    end if
                end try
            end repeat
            error "No matching chat for key"
        else if sendMode is "chat_id" then
            set targetChat to chat id targetKey
            send messageText to targetChat
            return "ok:chat_id"
        else if sendMode is "participant" then
            set imsgAccount to first account whose service type = iMessage
            set targetBuddy to participant targetKey of imsgAccount
            send messageText to targetBuddy
            return "ok:participant"
        else if sendMode is "buddy" then
            set imsgService to first service whose service type = iMessage
            set targetBuddy to buddy targetKey of imsgService
            send messageText to targetBuddy
            return "ok:buddy"
        end if
    end tell
end run
'''


def _run_text_script(mode: str, target: str, body: str) -> str:
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", _SEND_SCRIPT, target, body, mode],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "osascript failed").strip()
        raise subprocess.CalledProcessError(result.returncode, "osascript", err)
    return (result.stdout or "").strip()


def _run_file_script(mode: str, target: str, file_path: str) -> str:
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", _SEND_ATTACHMENT_SCRIPT, target, file_path, mode],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "osascript failed").strip()
        raise subprocess.CalledProcessError(result.returncode, "osascript", err)
    return (result.stdout or "").strip()


def check_automation() -> tuple[bool, str]:
    """Return whether Messages accepts Apple events from this process."""
    probe = r'''
tell application "Messages"
    return name
end tell
'''
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", probe],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, "Messages automation OK"
    err = (result.stderr or result.stdout or "unknown error").strip()
    if "not authorized" in err.lower() or "-1743" in err:
        return False, (
            "Not authorized to control Messages. "
            "System Settings → Privacy & Security → Automation → "
            "enable Visual Studio Code (or your terminal app) → Messages."
        )
    return False, err


def send_reply(
    chat_guid: str | None,
    chat_identifier: str | None,
    handle_id: str | None,
    body: str,
) -> str:
    """Try several send strategies; return which one worked."""
    attempts: list[tuple[str, str, object]] = []

    for key in (chat_guid, chat_identifier, handle_id):
        if key:
            attempts.append(
                (f"find_chat({key})", key, lambda k=key: _run_text_script("find_chat", k, body))
            )

    if chat_guid:
        attempts.append(
            ("chat_id", chat_guid, lambda: _run_text_script("chat_id", chat_guid, body))
        )
    if handle_id:
        attempts.append(
            ("participant", handle_id, lambda: _run_text_script("participant", handle_id, body))
        )
        attempts.append(
            ("buddy", handle_id, lambda: _run_text_script("buddy", handle_id, body))
        )

    errors: list[str] = []
    for label, _target, fn in attempts:
        try:
            result = fn()
            return f"{label} → {result or 'sent'}"
        except subprocess.CalledProcessError as exc:
            errors.append(f"{label}: {getattr(exc, 'stderr', None) or exc}")

    detail = "\n  ".join(errors) if errors else "no target"
    raise RuntimeError(f"Could not send message:\n  {detail}")


def test_send(target: str, body: str = "ibot test") -> str:
    """Send a test message using all strategies (for debugging)."""
    return send_reply(target, target, target, body)


_SEND_ATTACHMENT_SCRIPT = r'''
on run argv
    set targetKey to item 1 of argv
    set filePath to item 2 of argv
    set sendMode to item 3 of argv
    set posixFile to POSIX file filePath
    set pngData to missing value
    try
        set pngData to read file filePath as «class PNGf»
    end try

    tell application "Messages"
        activate

        if sendMode is "find_chat" then
            repeat with c in chats
                try
                    if (id of c as text) is targetKey then
                        if pngData is not missing value then
                            send pngData to c
                        else
                            send posixFile to c
                        end if
                        return "ok:id"
                    end if
                end try
                try
                    if (guid of c as text) is targetKey then
                        if pngData is not missing value then
                            send pngData to c
                        else
                            send posixFile to c
                        end if
                        return "ok:guid"
                    end if
                end try
            end repeat
            error "No matching chat for key"
        else if sendMode is "chat_id" then
            set targetChat to chat id targetKey
            if pngData is not missing value then
                send pngData to targetChat
            else
                send posixFile to targetChat
            end if
            return "ok:chat_id"
        else if sendMode is "participant" then
            set imsgAccount to first account whose service type = iMessage
            set targetBuddy to participant targetKey of imsgAccount
            if pngData is not missing value then
                send pngData to targetBuddy
            else
                send posixFile to targetBuddy
            end if
            return "ok:participant"
        else if sendMode is "buddy" then
            set imsgService to first service whose service type = iMessage
            set targetBuddy to buddy targetKey of imsgService
            if pngData is not missing value then
                send pngData to targetBuddy
            else
                send posixFile to targetBuddy
            end if
            return "ok:buddy"
        end if
    end tell
end run
'''


def send_attachment(
    chat_guid: str | None,
    chat_identifier: str | None,
    handle_id: str | None,
    file_path: str,
) -> str:
    """Send a file (e.g. PNG) via Messages."""
    path = file_path
    attempts: list[tuple[str, str]] = []

    for key in (chat_guid, chat_identifier, handle_id):
        if key:
            attempts.append((f"find_chat({key})", key))

    if chat_guid:
        attempts.append(("chat_id", chat_guid))
    if handle_id:
        attempts.append(("participant", handle_id))
        attempts.append(("buddy", handle_id))

    errors: list[str] = []
    for label, target in attempts:
        mode = "find_chat" if label.startswith("find_chat") else label
        try:
            result = _run_file_script(mode, target, path)
            return f"{label} → {result or 'sent'}"
        except subprocess.CalledProcessError as exc:
            errors.append(f"{label}: {getattr(exc, 'stderr', None) or exc}")

    detail = "\n  ".join(errors) if errors else "no target"
    raise RuntimeError(f"Could not send attachment:\n  {detail}")


def send_reply_with_attachment(
    chat_guid: str | None,
    chat_identifier: str | None,
    handle_id: str | None,
    body: str | None,
    file_path: str,
) -> list[str]:
    """Send optional caption text, then an image/file."""
    methods: list[str] = []
    if body:
        methods.append(send_reply(chat_guid, chat_identifier, handle_id, body))
    methods.append(
        send_attachment(chat_guid, chat_identifier, handle_id, file_path)
    )
    return methods
