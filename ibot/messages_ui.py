"""System Events helpers for controlling the Messages.app window."""

from __future__ import annotations

import subprocess

# Single tell-block script (handlers break System Events UI element syntax).
_EDIT_MESSAGE_SCRIPT = r'''
on run argv
    set newText to item 1 of argv
    set the clipboard to newText

    tell application "Messages" to activate
    delay 0.5

    tell application "System Events"
        if not (exists process "Messages") then return "fail:no-process"
        tell process "Messages"
            set frontmost to true
            delay 0.2
            set msgWindow to front window
            set chatView to missing value
            set clickX to 0
            set clickY to 0

            -- Find conversation transcript (try several layouts)
            try
                set sg to splitter group 1 of msgWindow
                if (count of groups of sg) is greater than or equal to 2 then
                    set convoGroup to group 2 of sg
                    try
                        set chatView to scroll area 1 of convoGroup
                    end try
                end if
            end try

            if chatView is missing value then
                try
                    set chatView to scroll area 1 of splitter group 1 of msgWindow
                end try
            end if

            if chatView is missing value then
                try
                    set chatView to scroll area 2 of splitter group 1 of msgWindow
                end try
            end if

            if chatView is not missing value then
                set {posX, posY} to position of chatView
                set {sizeW, sizeH} to size of chatView
                set clickX to (posX + sizeW - 60) as integer
                set clickY to (posY + sizeH - 50) as integer
            else
                set {posX, posY} to position of msgWindow
                set {sizeW, sizeH} to size of msgWindow
                set clickX to (posX + (sizeW * 0.72)) as integer
                set clickY to (posY + (sizeH * 0.76)) as integer
            end if

            click at {clickX, clickY}
            delay 0.12
            click at {clickX, clickY}
            delay 0.1
            click at {clickX, clickY}
            delay 0.4

            set edited to false
            try
                click menu item "Edit" of menu 1
                set edited to true
            end try
            if edited is false then
                try
                    click menu item "Edit Message" of menu 1
                    set edited to true
                end try
            end if
            if edited is false then
                try
                    click menu item "Edit" of menu "Edit" of menu bar item "Edit" of menu bar 1
                    set edited to true
                end try
            end if
            if edited is false then return "fail:no-edit-menu"

            delay 0.4
            keystroke "a" using command down
            delay 0.08
            keystroke "v" using command down
            delay 0.12
            keystroke return
            delay 0.25
            return "ok"
        end tell
    end tell
end run
'''

_PROBE_UI_SCRIPT = r'''
on run
    tell application "Messages" to activate
    delay 0.4
    tell application "System Events"
        if not (exists process "Messages") then return "fail:no-process"
        tell process "Messages"
            set w to front window
            set n to 0
            try
                set n to count of scroll areas of w
            end try
            return "ok:scroll-areas=" & n
        end tell
    end tell
end run
'''


def run_applescript(script: str, *args: str) -> str:
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


def edit_last_outgoing_message(new_text: str) -> str:
    return run_applescript(_EDIT_MESSAGE_SCRIPT, new_text)


def probe_messages_ui() -> str:
    return run_applescript(_PROBE_UI_SCRIPT)
