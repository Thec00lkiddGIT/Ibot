"""API Ninjas dad jokes."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ibot.config import api_ninjas_key

API_URL = "https://api.api-ninjas.com/v1/dadjokes"
TIMEOUT_SECONDS = 15


def fetch_dad_joke() -> str:
    req = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": "Ibot/1.0",
            "X-Api-Key": api_ninjas_key(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API HTTP {exc.code}: {body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON from API Ninjas") from exc

    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))

    if isinstance(data, list) and data:
        joke = data[0].get("joke") if isinstance(data[0], dict) else None
        if joke:
            return str(joke).strip()

    raise RuntimeError("No joke returned from API")


def format_dad_joke(joke: str) -> str:
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Dad Joke\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{joke}\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


def dadjoke_reply() -> str:
    return format_dad_joke(fetch_dad_joke())
