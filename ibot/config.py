"""Load config from ~/Library/Application Support/Ibot/.env"""

from __future__ import annotations

import os

from ibot.paths import ensure_env_file, env_file


def config_env_path() -> str:
    return str(env_file())


def _load_dotenv() -> None:
    path = ensure_env_file()
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
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
            f"Missing C99_WEATHER_KEY. Edit {config_env_path()}"
        )
    return key


def glseries_api_token() -> str:
    _load_dotenv()
    token = os.environ.get("GLSERIES_TOKEN", "").strip()
    if not token:
        raise ValueError(
            f"Missing GLSERIES_TOKEN. Edit {config_env_path()}"
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
            f"Missing SERPAPI_KEY. Edit {config_env_path()}"
        )
    return key


def api_ninjas_key() -> str:
    _load_dotenv()
    key = os.environ.get("API_NINJAS_KEY", "").strip()
    if not key:
        raise ValueError(
            f"Missing API_NINJAS_KEY. Edit {config_env_path()}"
        )
    return key
