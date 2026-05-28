"""http.cat status code images."""

from __future__ import annotations

import urllib.error
import urllib.request

BASE_URL = "https://http.cat"
TIMEOUT_SECONDS = 20


def fetch_httpcat_image(code: int) -> tuple[bytes, str]:
    if code < 100 or code > 599:
        raise ValueError("Status code must be between 100 and 599")

    url = f"{BASE_URL}/{code}"
    req = urllib.request.Request(url, headers={"User-Agent": "Ibot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError(f"http.cat has no image for HTTP {code}") from exc
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"http.cat HTTP {exc.code}: {err_body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    if body.startswith(b"\xff\xd8\xff"):
        ext = "jpg"
    elif body.startswith(b"\x89PNG"):
        ext = "png"
    elif body.startswith(b"GIF"):
        ext = "gif"
    else:
        raise RuntimeError("http.cat did not return an image (unknown status or invalid code)")

    return body, f"httpcat-{code}.{ext}"


def httpcat_caption(code: int) -> str:
    return f"HTTP {code} — {BASE_URL}/{code}"
