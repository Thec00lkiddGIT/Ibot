"""API Ninjas QR code generator."""

from __future__ import annotations

import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ibot.config import api_ninjas_key

API_URL = "https://api.api-ninjas.com/v1/qrcode"
TIMEOUT_SECONDS = 20


def fetch_qr_png(data: str) -> bytes:
    if not data.strip():
        raise ValueError("Text or URL required")

    params = urllib.parse.urlencode({"data": data.strip(), "format": "png"})
    url = f"{API_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Ibot/1.0",
            "X-Api-Key": api_ninjas_key(),
            "Accept": "image/png",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API HTTP {exc.code}: {err_body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    if not body.startswith(b"\x89PNG"):
        raise RuntimeError("API did not return a PNG image")
    return body


def format_qr_caption(data: str) -> str:
    preview = data.strip()
    if len(preview) > 120:
        preview = preview[:117] + "..."
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📷 QR Code\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{preview}\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


def prepare_qr(data: str) -> tuple[str, Path]:
    """Return caption text and path to a temp PNG (caller deletes after send)."""
    png = fetch_qr_png(data)
    tmp = Path(tempfile.mkstemp(prefix="ibot-qr-", suffix=".png")[1])
    tmp.write_bytes(png)
    return format_qr_caption(data), tmp
