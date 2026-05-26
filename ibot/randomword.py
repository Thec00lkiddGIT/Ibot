"""API Ninjas random word (v2)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ibot.config import api_ninjas_key

API_URL = "https://api.api-ninjas.com/v2/randomword"
TIMEOUT_SECONDS = 15


def fetch_random_word() -> str:
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
        word = data[0]
        if isinstance(word, str) and word.strip():
            return word.strip()
        if isinstance(word, dict):
            for key in ("word", "name", "text"):
                if word.get(key):
                    return str(word[key]).strip()

    raise RuntimeError("No word returned from API")


def word_reply() -> str:
    return fetch_random_word()
