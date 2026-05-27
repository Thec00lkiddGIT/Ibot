"""AFK auto-reply for incoming iMessages."""

from __future__ import annotations

import time

from ibot.db import IncomingMessage
from ibot.send import send_reply


def send_afk_reply(message: IncomingMessage, text: str) -> str:
    """Send AFK message to the chat; return send method label."""
    time.sleep(0.3)
    return send_reply(
        message.chat_guid,
        message.chat_identifier,
        message.handle_id,
        text,
    )
