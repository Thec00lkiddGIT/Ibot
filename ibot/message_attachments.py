"""Read image attachments from Messages chat.db."""

from __future__ import annotations

from pathlib import Path

from ibot.db import connect

IMAGE_MIMES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }
)
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})

_ATTACHMENT_SQL = """
SELECT a.filename, a.mime_type, a.transfer_name
FROM message_attachment_join maj
JOIN attachment a ON a.ROWID = maj.attachment_id
WHERE maj.message_id = ?
"""

_RECENT_IN_CHAT_SQL = """
SELECT a.filename, a.mime_type, a.transfer_name
FROM message m
JOIN message_attachment_join maj ON maj.message_id = m.ROWID
JOIN attachment a ON a.ROWID = maj.attachment_id
JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
JOIN chat c ON c.ROWID = cmj.chat_id
WHERE c.guid = ?
  AND m.ROWID <= ?
  AND m.is_from_me = 1
ORDER BY m.ROWID DESC
LIMIT ?
"""


def _resolve_attachment_path(filename: str) -> Path | None:
    if not filename:
        return None
    raw = filename.strip()
    path = Path(raw).expanduser()
    if path.is_file():
        return path
    candidates = [
        Path.home() / "Library" / "Messages" / raw,
        Path.home() / "Library" / "Messages" / "Attachments" / raw,
    ]
    if "Attachments" in raw:
        candidates.insert(0, Path(raw).expanduser())
    for alt in candidates:
        if alt.is_file():
            return alt
    return None


def _is_image(path: Path, mime_type: str | None) -> bool:
    if mime_type and mime_type.lower() in IMAGE_MIMES:
        return True
    return path.suffix.lower() in IMAGE_SUFFIXES


def _load_image_row(filename: str, mime_type: str | None, transfer_name: str | None) -> tuple[bytes, str, str] | None:
    path = _resolve_attachment_path(str(filename or ""))
    if path is None:
        return None
    if not _is_image(path, str(mime_type) if mime_type else None):
        if path.suffix.lower() in {".heic", ".heif"}:
            raise ValueError("HEIC/HEIF is not supported by !poof. Send as JPG/PNG/WebP.")
        return None
    data = path.read_bytes()
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("Image too large (max 20MB).")
    name = str(transfer_name or path.name)
    ctype = str(mime_type or "application/octet-stream")
    return data, name, ctype


def _first_image_from_rows(rows: list) -> tuple[bytes, str, str] | None:
    for filename, mime_type, transfer_name in rows:
        hit = _load_image_row(
            str(filename or ""),
            str(mime_type) if mime_type else None,
            str(transfer_name) if transfer_name else None,
        )
        if hit:
            return hit
    return None


def first_image_attachment(
    message_rowid: int,
    *,
    chat_guid: str | None = None,
    lookback: int = 12,
) -> tuple[bytes, str, str] | None:
    """Image on this message, or the latest image you sent in the same chat."""
    conn = connect()
    try:
        rows = conn.execute(_ATTACHMENT_SQL, (message_rowid,)).fetchall()
        hit = _first_image_from_rows(rows)
        if hit:
            return hit
        if chat_guid:
            recent = conn.execute(
                _RECENT_IN_CHAT_SQL,
                (chat_guid, message_rowid, lookback),
            ).fetchall()
            return _first_image_from_rows(recent)
    finally:
        conn.close()
    return None
