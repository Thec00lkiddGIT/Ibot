"""Poof.bg background removal (https://docs.poof.bg)."""

from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.request
from typing import Any

from ibot.config import poof_api_key
from ibot.message_attachments import first_image_attachment

API_URL = "https://api.poof.bg/v1/remove"
TIMEOUT_SECONDS = 120
ALLOWED_FORMATS = frozenset({"png", "jpg", "webp"})
ALLOWED_CHANNELS = frozenset({"rgba", "rgb"})
ALLOWED_SIZES = frozenset({"full", "preview", "small", "medium", "large"})


def _parse_options(args: str) -> dict[str, str]:
    options: dict[str, str] = {}
    for part in args.split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in ("format", "channels", "bg_color", "size", "crop"):
            options[key] = value
    return options


def _encode_multipart(
    fields: list[tuple[str, str]],
    files: list[tuple[str, str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----IbotPoof{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    for field_name, filename, data, content_type in files:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n".encode()
        )
        parts.append(data)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def _error_message(code: int, body: bytes) -> str:
    try:
        data = json.loads(body.decode("utf-8"))
        if isinstance(data, dict):
            msg = data.get("message") or data.get("error")
            if isinstance(msg, dict):
                msg = msg.get("message")
            if msg:
                return str(msg)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    text = body.decode("utf-8", errors="replace").strip()
    return text[:300] if text else f"HTTP {code}"


def remove_background(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    *,
    options: dict[str, str] | None = None,
) -> tuple[bytes, str, dict[str, Any]]:
    opts = dict(options or {})
    fmt = opts.get("format", "png").lower()
    if fmt not in ALLOWED_FORMATS:
        raise ValueError("format must be png, jpg, or webp")
    channels = opts.get("channels", "rgba").lower()
    if channels not in ALLOWED_CHANNELS:
        raise ValueError("channels must be rgba or rgb")
    size = opts.get("size", "full").lower()
    if size not in ALLOWED_SIZES:
        raise ValueError("size must be full, preview, small, medium, or large")

    fields = [
        ("format", fmt),
        ("channels", channels),
        ("size", size),
    ]
    if opts.get("bg_color"):
        fields.append(("bg_color", opts["bg_color"]))
    if opts.get("crop", "").lower() in ("1", "true", "yes"):
        fields.append(("crop", "true"))

    body, boundary = _encode_multipart(
        fields,
        [("image_file", filename, image_bytes, content_type or "application/octet-stream")],
    )
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "x-api-key": poof_api_key(),
            "User-Agent": "Ibot/1.0",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "image/png, image/jpeg, image/webp, */*",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            result = resp.read()
            meta = {
                "request_id": resp.headers.get("X-Request-ID"),
                "processing_time_ms": resp.headers.get("X-Processing-Time-Ms"),
                "width": resp.headers.get("X-Image-Width"),
                "height": resp.headers.get("X-Image-Height"),
                "content_type": (resp.headers.get("Content-Type") or "").split(";")[0],
            }
    except urllib.error.HTTPError as exc:
        detail = _error_message(exc.code, exc.read())
        if exc.code == 401:
            raise ValueError("Invalid POOF_API_KEY") from exc
        if exc.code == 402:
            raise ValueError("Poof credits exhausted - upgrade your plan") from exc
        if exc.code == 429:
            raise ValueError("Poof rate limit - try again later") from exc
        raise RuntimeError(f"Poof HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    out_type = meta.get("content_type") or f"image/{fmt}"
    if "jpeg" in out_type or fmt == "jpg":
        out_name = "poof-result.jpg"
    elif "webp" in out_type or fmt == "webp":
        out_name = "poof-result.webp"
    else:
        out_name = "poof-result.png"
    return result, out_name, meta


def poof_from_message_rowid(
    message_rowid: int,
    args: str,
    *,
    chat_guid: str | None = None,
) -> tuple[str, bytes, str]:
    hit = first_image_attachment(message_rowid, chat_guid=chat_guid)
    if not hit:
        raise ValueError(
            "Send an image in this chat, then !poof "
            "(same message or your latest image, JPEG/PNG/WebP, max 20MB)."
        )
    image_bytes, filename, content_type = hit
    options = _parse_options(args)
    result_bytes, out_name, meta = remove_background(
        image_bytes,
        filename,
        content_type,
        options=options,
    )

    lines = ["Background removed (Poof.bg)"]
    if meta.get("width") and meta.get("height"):
        lines.append(f"Size: {meta['width']}x{meta['height']}")
    if meta.get("processing_time_ms"):
        lines.append(f"Processed in {meta['processing_time_ms']}ms")
    if options:
        lines.append("Options: " + ", ".join(f"{k}={v}" for k, v in options.items()))
    return "\n".join(lines), result_bytes, out_name
