"""Command handlers for the selfbot."""

from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ibot.dadjoke import dadjoke_reply
from ibot.db import IncomingMessage
from ibot.glcheck import bulk_reply, check_reply
from ibot.qr import prepare_qr
from ibot.randomword import word_reply
from ibot.youtube import youtube_reply
from ibot.send import send_reply, send_reply_with_attachment
from ibot.typewrite import run_typewrite
from ibot.weather import weather_reply

PREFIX = "!"
BOT_REPLIES = frozenset({"pong"})

# Subset of GLSeries filter keys for optional `!check <filter> <url>`
FILTER_KEYS = frozenset(
    {
        "fortiguard",
        "lightspeed",
        "paloalto",
        "blocksiweb",
        "blocksiai",
        "blocksiguardian",
        "linewize",
        "cisco",
        "securly",
        "goguardian",
        "goguardianv2",
        "goguardianai",
        "lanschool",
        "lanschoolair",
        "contentkeeper",
        "aristotle",
        "senso",
        "deledao",
        "iboss",
        "barracuda",
        "dnsfilter",
        "qustodio",
        "sophos",
        "zscaler",
        "gaggle",
        "smoothwall",
        "safedns",
        "ruckus",
        "unifi",
        "webroot",
        "nextdns",
        "netsweeper",
        "hapara",
        "forcepoint",
        "cleanbrowsing",
        "adguard",
        "googlesafebrowsing",
        "opendns",
        "watchguard",
        "cloudflareintel",
        "cloudflarefamily",
        "quad9",
        "trellix",
        "controld",
        "dragonflyai",
        "norton",
        "ciracs",
        "safesurfer",
    }
)


@dataclass(frozen=True)
class CommandResult:
    handled: bool
    reply: str | None = None
    replies: tuple[str, ...] = ()
    typewrite_text: str | None = None
    attachment_path: str | None = None


def _parse_command(text: str) -> tuple[str, str]:
    body = text[len(PREFIX) :].strip()
    parts = body.split(None, 1)
    name = parts[0].lower() if parts else ""
    args = parts[1].strip() if len(parts) > 1 else ""
    return name, args


def _parse_check_args(args: str) -> tuple[str | None, str]:
    parts = args.split()
    if not parts:
        raise ValueError("missing url")
    if parts[0].lower() in FILTER_KEYS:
        if len(parts) < 2:
            raise ValueError("missing url after filter name")
        return parts[0].lower(), parts[1]
    return None, args


def handle_command(message: IncomingMessage) -> CommandResult:
    text = message.body.strip()
    if not text.startswith(PREFIX):
        return CommandResult(handled=False)

    name, args = _parse_command(text)

    if name == "ping":
        return CommandResult(handled=True, reply="pong")

    if name == "gay":
        pct = random.randint(0, 100)
        return CommandResult(handled=True, reply=f"YOU are {pct}% gay")

    if name == "word":
        try:
            reply = word_reply()
        except ValueError as exc:
            reply = str(exc)
        except RuntimeError as exc:
            reply = f"Word error: {exc}"
        return CommandResult(handled=True, reply=reply)

    if name == "dadjoke":
        try:
            reply = dadjoke_reply()
        except ValueError as exc:
            reply = str(exc)
        except RuntimeError as exc:
            reply = f"Dad joke error: {exc}"
        return CommandResult(handled=True, reply=reply)

    if name == "qr":
        if not args:
            return CommandResult(
                handled=True,
                reply="Usage: !qr <text or link>\nExample: !qr https://example.com",
            )
        try:
            caption, png_path = prepare_qr(args)
            return CommandResult(
                handled=True,
                reply=caption,
                attachment_path=str(png_path),
            )
        except ValueError as exc:
            return CommandResult(handled=True, reply=str(exc))
        except RuntimeError as exc:
            return CommandResult(handled=True, reply=f"QR error: {exc}")

    if name == "youtube":
        parts = args.split(None, 1)
        if len(parts) < 2:
            return CommandResult(
                handled=True,
                reply=(
                    "Usage:\n"
                    "!youtube search <query>\n"
                    "!youtube video <id or url>\n"
                    "!youtube trans <id or url>"
                ),
            )
        sub, arg = parts[0].lower(), parts[1].strip()
        try:
            result = youtube_reply(sub, arg)
        except ValueError as exc:
            return CommandResult(handled=True, reply=str(exc))
        except RuntimeError as exc:
            return CommandResult(handled=True, reply=f"YouTube error: {exc}")
        if isinstance(result, list):
            return CommandResult(handled=True, replies=tuple(result))
        return CommandResult(handled=True, reply=result)

    if name == "weather":
        if not args:
            return CommandResult(
                handled=True,
                reply="Usage: !weather <city>\nExample: !weather Groves",
            )
        try:
            reply = weather_reply(args)
        except ValueError as exc:
            reply = str(exc)
        except RuntimeError as exc:
            reply = f"Weather error: {exc}"
        return CommandResult(handled=True, reply=reply)

    if name == "check":
        if not args:
            return CommandResult(
                handled=True,
                reply="Usage: !check <url>\nExample: !check https://example.com\n"
                "Optional: !check linewize example.com",
            )
        try:
            filter_key, url = _parse_check_args(args)
            chunks = check_reply(url, filter_key=filter_key)
        except ValueError as exc:
            return CommandResult(handled=True, reply=str(exc))
        except RuntimeError as exc:
            return CommandResult(handled=True, reply=f"Check error: {exc}")
        return CommandResult(handled=True, replies=tuple(chunks))

    if name == "bulk":
        urls = args.split()
        if not urls:
            return CommandResult(
                handled=True,
                reply="Usage: !bulk <url1> <url2> [url3]\nExample: !bulk google.com youtube.com",
            )
        try:
            chunks = bulk_reply(urls)
        except ValueError as exc:
            return CommandResult(handled=True, reply=str(exc))
        except RuntimeError as exc:
            return CommandResult(handled=True, reply=f"Bulk error: {exc}")
        return CommandResult(handled=True, replies=tuple(chunks))

    if name == "typewrite":
        if not args:
            return CommandResult(
                handled=True,
                reply="Usage: !typewrite <message>\nExample: !typewrite Hello World",
            )
        return CommandResult(handled=True, typewrite_text=args)

    from ibot.script_hub import dispatch_hub_command

    try:
        hub_result = dispatch_hub_command(name, args, message)
    except Exception as exc:  # noqa: BLE001
        return CommandResult(handled=True, reply=f"Script error: {exc}")
    if hub_result is not None:
        if isinstance(hub_result, list):
            return CommandResult(handled=True, replies=tuple(hub_result))
        return CommandResult(handled=True, reply=hub_result)

    return CommandResult(handled=False)


def should_ignore_self_message(message: IncomingMessage) -> bool:
    if not message.is_from_me:
        return False
    return message.body.strip().lower() in BOT_REPLIES


def dispatch(message: IncomingMessage) -> bool:
    if should_ignore_self_message(message):
        return False

    result = handle_command(message)
    if result.handled:
        return _send_command_result(message, result)

    from ibot.script_hub import dispatch_message_listeners

    listener_replies = dispatch_message_listeners(message)
    if listener_replies:
        fake = CommandResult(handled=True, replies=tuple(listener_replies))
        return _send_command_result(message, fake)
    return False


def _send_command_result(message: IncomingMessage, result: CommandResult) -> bool:
    if result.typewrite_text is not None:
        try:
            run_typewrite(
                message.chat_guid,
                message.chat_identifier,
                message.handle_id,
                result.typewrite_text,
            )
            print("  typewrite: done")
        except Exception as exc:  # noqa: BLE001
            send_reply(
                message.chat_guid,
                message.chat_identifier,
                message.handle_id,
                f"Typewrite failed: {exc}",
            )
            print(f"  typewrite failed: {exc}", file=sys.stderr)
        return True

    if result.attachment_path:
        path = Path(result.attachment_path)
        try:
            methods = send_reply_with_attachment(
                message.chat_guid,
                message.chat_identifier,
                message.handle_id,
                result.reply,
                str(path),
            )
            for i, method in enumerate(methods, 1):
                print(f"  send [{i}/{len(methods)}]: {method}")
        except Exception as exc:  # noqa: BLE001
            send_reply(
                message.chat_guid,
                message.chat_identifier,
                message.handle_id,
                f"QR send failed: {exc}",
            )
            print(f"  qr send failed: {exc}", file=sys.stderr)
        finally:
            path.unlink(missing_ok=True)
        return True

    outgoing = list(result.replies) if result.replies else []
    if result.reply is not None:
        outgoing.insert(0, result.reply)
    if not outgoing:
        return False

    for i, text in enumerate(outgoing):
        if i:
            time.sleep(0.4)
        method = send_reply(
            message.chat_guid,
            message.chat_identifier,
            message.handle_id,
            text,
        )
        print(f"  send [{i + 1}/{len(outgoing)}]: {method}")
    return True
