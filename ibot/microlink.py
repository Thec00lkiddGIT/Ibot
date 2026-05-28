"""Microlink screenshot API (https://microlink.io)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.microlink.io/"
TIMEOUT_SECONDS = 90


def _normalize_url(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise ValueError("URL required")
    if not re.match(r"^https?://", text, re.I):
        text = f"https://{text}"
    parsed = urllib.parse.urlparse(text)
    if not parsed.netloc:
        raise ValueError("Invalid URL")
    return text


def filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.netloc or "screenshot").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.strip("/").replace("/", "-")
    name = f"{host}-{path}" if path else host
    name = re.sub(r"[^\w.\-]+", "_", name).strip("._") or "screenshot"
    if len(name) > 96:
        name = name[:96]
    return f"{name}.png"


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Ibot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Microlink HTTP {exc.code}: {detail[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected Microlink response")
    return data


def _fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Ibot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Screenshot download HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def screenshot_lookup(target_url: str) -> tuple[str, bytes, str]:
    """Return caption, PNG bytes, and filename."""
    page_url = _normalize_url(target_url)
    api_url = f"{API_BASE}?screenshot&url={urllib.parse.quote(page_url, safe='')}"

    payload = _fetch_json(api_url)
    if payload.get("status") != "success":
        message = payload.get("message") or "Microlink request failed"
        raise RuntimeError(str(message))

    data = payload.get("data") or {}
    screenshot = data.get("screenshot") or {}
    image_url = screenshot.get("url")
    if not isinstance(image_url, str) or not image_url.startswith("http"):
        raise RuntimeError("Microlink did not return a screenshot URL")

    png = _fetch_bytes(image_url)
    if not png.startswith(b"\x89PNG") and not png.startswith(b"\xff\xd8"):
        raise RuntimeError("Microlink did not return an image")

    filename = filename_from_url(page_url)
    title = data.get("title") or page_url
    size_pretty = screenshot.get("size_pretty") or ""
    width = screenshot.get("width")
    height = screenshot.get("height")

    lines = [f"Screenshot — {title}", page_url]
    if width and height:
        lines.append(f"{width}x{height}" + (f" · {size_pretty}" if size_pretty else ""))

    return "\n".join(lines), png, filename
