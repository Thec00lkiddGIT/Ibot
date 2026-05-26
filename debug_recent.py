#!/usr/bin/env python3
"""Print recent iMessages (for debugging). Run from Terminal with Full Disk Access."""

from __future__ import annotations

import sys

from ibot.db import connect, max_rowid
from ibot.decode import message_text


def main() -> int:
    try:
        conn = connect()
    except (FileNotFoundError, PermissionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    top = max_rowid(conn)
    print(f"Max message ROWID: {top}\n")
    print("Last 20 messages (all directions):\n")

    rows = conn.execute(
        """
        SELECT m.ROWID, m.is_from_me, m.text, m.attributedBody,
               (SELECT h.id FROM handle h WHERE h.ROWID = m.handle_id)
        FROM message m
        ORDER BY m.ROWID DESC
        LIMIT 20
        """
    ).fetchall()

    for rowid, is_from_me, text, attributed_body, handle in rows:
        body = message_text(text, attributed_body)
        direction = "YOU →" if is_from_me else "← THEM"
        flag = ""
        if not body:
            flag = " [empty/decode failed]"
        elif body.startswith("__kIM") or body.startswith("NS"):
            flag = " [bad decode - update bot]"
        print(f"{rowid:6} {direction:8} {handle or '?':20} {body!r}{flag}")

    print(
        "\nIf decoded text is empty for your !ping, the decoder failed."
        "\nIf direction is YOU →, the bot ignores it unless you use: python3 bot.py --self"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
