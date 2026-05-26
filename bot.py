#!/usr/bin/env python3
"""Ibot - iMessage selfbot. Polls chat.db and replies via AppleScript."""

from __future__ import annotations

import argparse
import sys
import time

from ibot.commands import dispatch
from ibot.db import connect, fetch_batch, max_rowid
from ibot.permissions import check_access, format_check_report, open_fda_settings
from ibot.messages_ui import probe_messages_ui
from ibot.send import check_automation, test_send
from ibot.typewrite import edit_last_outgoing_message

from ibot.state import get_state_file, load_state, save_state

DEFAULT_POLL_SECONDS = 0.5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ibot iMessage selfbot")
    parser.add_argument(
        "--poll",
        type=float,
        default=DEFAULT_POLL_SECONDS,
        help=f"Poll interval in seconds (default {DEFAULT_POLL_SECONDS})",
    )
    parser.add_argument(
        "--catch-up",
        action="store_true",
        help="Resume from saved .state.json instead of skipping old messages",
    )
    parser.add_argument(
        "--self",
        action="store_true",
        help="Also react to messages YOU send (for testing from this Mac)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log every seen message",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Clear .state.json and exit",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify Full Disk Access and exit",
    )
    parser.add_argument(
        "--test-send",
        metavar="TARGET",
        help="Send a test iMessage (phone/email/chat id from debug_recent.py)",
    )
    parser.add_argument(
        "--test-edit",
        metavar="TEXT",
        nargs="?",
        const="edit test",
        help="Test in-place edit on your last message (Messages must be open on a chat)",
    )
    parser.add_argument(
        "--probe-ui",
        action="store_true",
        help="Check if Messages UI is visible to Accessibility",
    )
    parser.add_argument(
        "--open-fda",
        action="store_true",
        help="Open System Settings → Full Disk Access",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from ibot.paths import ensure_env_file, ensure_script_hub

    ensure_env_file()
    ensure_script_hub()

    if args.reset_state:
        state_path = get_state_file()
        if state_path.exists():
            state_path.unlink()
            print("Cleared .state.json")
        else:
            print("No state file to clear")
        return 0

    if args.open_fda:
        if open_fda_settings():
            print("Opened Full Disk Access settings.")
            report = check_access()
            if not report.sqlite_ok:
                print()
                print(format_check_report(report))
        else:
            print("Could not open System Settings. Go to Privacy & Security → Full Disk Access manually.")
        return 0

    if args.check:
        report = check_access()
        print(format_check_report(report))
        ok, automation_msg = check_automation()
        print(f"\nAutomation: {automation_msg}")
        return 0 if report.sqlite_ok and ok else 1

    if args.probe_ui:
        try:
            print(probe_messages_ui())
            print("If scroll-areas=0, grant Accessibility and open a chat in Messages.")
        except Exception as exc:  # noqa: BLE001
            print(f"UI probe failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.test_edit is not None:
        print(
            "Open Messages on the chat with YOUR last message visible, then this will try to edit it."
        )
        try:
            edit_last_outgoing_message(args.test_edit)
            print(f"Edit OK - your last bubble should now say: {args.test_edit!r}")
        except Exception as exc:  # noqa: BLE001
            print(f"Edit failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.test_send:
        ok, automation_msg = check_automation()
        print(automation_msg)
        if not ok:
            return 1
        try:
            method = test_send(args.test_send)
            print(f"Sent test message via {method}")
            print("Check Messages.app - you should see 'ibot test'.")
        except Exception as exc:  # noqa: BLE001
            print(f"Send failed: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        conn = connect()
    except (FileNotFoundError, PermissionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.catch_up:
        last_rowid = load_state()
        print(f"Catching up from ROWID {last_rowid}")
    else:
        last_rowid = max_rowid(conn)
        save_state(last_rowid)
        print(f"Watching new messages after ROWID {last_rowid}")

    mode = "incoming + your sends" if args.self else "incoming only"
    print(f"Mode: {mode}")
    print("Commands: !ping, !gay, !word, !dadjoke, !qr <text>, !youtube <sub>, !weather <city>, !check <url>, !bulk <urls>, !typewrite <text>")
    if not args.self:
        print("Note: !typewrite must be sent by you - use --self")
    if not args.self:
        print(
            "Tip: messages you send from this Mac are ignored. "
            "Use --self to test from this device, or text from another phone.\n"
        )
    ok, automation_msg = check_automation()
    print(automation_msg)
    if not ok:
        print("Fix Automation before expecting replies in Messages.\n", file=sys.stderr)
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            batch = fetch_batch(conn, last_rowid, include_self=args.self)

            for message in batch.messages:
                if args.verbose:
                    who = message.handle_id or message.chat_identifier or "?"
                    src = "you" if message.is_from_me else "them"
                    print(f"[{message.rowid}] ({src}) {who}: {message.body!r}")

                try:
                    if dispatch(message):
                        who = message.handle_id or message.chat_identifier or "unknown"
                        print(f"[{message.rowid}] → pong sent to {who} (check Messages)")
                except Exception as exc:  # noqa: BLE001
                    print(f"[{message.rowid}] reply failed: {exc}", file=sys.stderr)

            if batch.watermark > last_rowid:
                last_rowid = batch.watermark
                save_state(last_rowid)

            time.sleep(args.poll)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
