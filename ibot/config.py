"""Load config from environment / .env (project root)."""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ENV_LOADED = False


def _load_dotenv() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def weather_api_key() -> str:
    _load_dotenv()
    key = os.environ.get("C99_WEATHER_KEY", "").strip()
    if not key:
        raise ValueError(
            "Missing C99_WEATHER_KEY. Add it to .env (see .env.example)."
        )
    return key


def glseries_api_token() -> str:
    _load_dotenv()
    token = os.environ.get("GLSERIES_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "Missing GLSERIES_TOKEN. Add it to .env (see .env.example)."
        )
    return token


def glseries_base_url() -> str:
    _load_dotenv()
    return os.environ.get("GLSERIES_BASE_URL", "https://live.glseries.net/api/v1").strip()


def serpapi_key() -> str:
    _load_dotenv()
    key = os.environ.get("SERPAPI_KEY", "").strip()
    if not key:
        raise ValueError(
            "Missing SERPAPI_KEY. Add it to .env (see .env.example)."
        )
    return key


def api_ninjas_key() -> str:
    _load_dotenv()
    key = os.environ.get("API_NINJAS_KEY", "").strip()
    if not key:
        raise ValueError(
            "Missing API_NINJAS_KEY. Add it to .env (see .env.example)."
        )
    return key
