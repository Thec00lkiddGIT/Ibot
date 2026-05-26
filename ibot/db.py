"""Read incoming messages from ~/Library/Messages/chat.db."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ibot.decode import message_text

DEFAULT_DB = Path.home() / "Library" / "Messages" / "chat.db"

# One row per message (joins can duplicate without subqueries)
INCOMING_SQL = """
SELECT
    m.ROWID AS rowid,
    m.text,
    m.attributedBody,
    m.is_from_me,
    (SELECT h.id FROM handle h WHERE h.ROWID = m.handle_id) AS handle_id,
    (
        SELECT c.guid
        FROM chat_message_join cmj
        JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE cmj.message_id = m.ROWID
        LIMIT 1
    ) AS chat_guid,
    (
        SELECT c.chat_identifier
        FROM chat_message_join cmj
        JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE cmj.message_id = m.ROWID
        LIMIT 1
    ) AS chat_identifier
FROM message m
WHERE m.ROWID > ?
  AND m.is_from_me IN ({from_me_filter})
  AND (m.item_type IS NULL OR m.item_type = 0)
ORDER BY m.ROWID ASC
LIMIT 200
"""


@dataclass(frozen=True)
class IncomingMessage:
    rowid: int
    body: str
    is_from_me: bool
    handle_id: str | None
    chat_guid: str | None
    chat_identifier: str | None


@dataclass(frozen=True)
class FetchBatch:
    messages: list[IncomingMessage]
    watermark: int


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB
    if not path.exists():
        raise FileNotFoundError(
            f"Messages database not found at {path}. "
            "Enable iMessage and sign into Messages on this Mac."
        )
    uri = f"file:{path}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if "authorization denied" in msg or "unable to open" in msg:
            from ibot.permissions import fda_fix_message, _parent_host_app

            host = _parent_host_app()
            raise PermissionError(
                f"Cannot read chat.db (host: {host}).\n\n{fda_fix_message()}"
            ) from exc
        raise


def max_rowid(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(ROWID), 0) FROM message").fetchone()
    return int(row[0])


def fetch_batch(
    conn: sqlite3.Connection,
    after_rowid: int,
    *,
    include_self: bool = False,
) -> FetchBatch:
    from_me = "0, 1" if include_self else "0"
    sql = INCOMING_SQL.format(from_me_filter=from_me)
    rows = conn.execute(sql, (after_rowid,)).fetchall()

    messages: list[IncomingMessage] = []
    watermark = after_rowid

    for rowid, text, attributed_body, is_from_me, handle_id, chat_guid, chat_identifier in rows:
        rowid = int(rowid)
        watermark = max(watermark, rowid)
        body = message_text(text, attributed_body)
        if not body:
            continue
        messages.append(
            IncomingMessage(
                rowid=rowid,
                body=body,
                is_from_me=bool(is_from_me),
                handle_id=str(handle_id) if handle_id else None,
                chat_guid=str(chat_guid) if chat_guid else None,
                chat_identifier=str(chat_identifier) if chat_identifier else None,
            )
        )

    return FetchBatch(messages=messages, watermark=watermark)


def fetch_incoming(
    conn: sqlite3.Connection,
    after_rowid: int,
    *,
    include_self: bool = False,
) -> list[IncomingMessage]:
    return fetch_batch(conn, after_rowid, include_self=include_self).messages
