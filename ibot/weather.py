"""C99.nl weather API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from ibot.config import weather_api_key

API_BASE = "https://api.c99.nl/weather"
TIMEOUT_SECONDS = 15


def fetch_weather_raw(location: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "key": weather_api_key(),
            "location": location,
        }
    )
    url = f"{API_BASE}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Ibot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API HTTP {exc.code}: {body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON from weather API") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Unexpected API response")
    return data


def format_weather(data: dict) -> str:
    if not data.get("success"):
        err = data.get("error") or data.get("message") or "Weather lookup failed."
        return f"Weather: {err}"

    city = data.get("city", "?")
    country = data.get("country", "")
    place = f"{city}, {country}" if country else city

    weather = data.get("weather", "-")
    desc = data.get("description", "")
    headline = f"{weather} · {desc}" if desc else weather

    temp = data.get("temperature", "-")
    tmin = data.get("temperature_min", "")
    tmax = data.get("temperature_max", "")
    temp_line = temp
    if tmin or tmax:
        temp_line = f"{temp}  (low {tmin}, high {tmax})"

    lines = [
        f"Weather - {place}",
        "",
        headline,
        temp_line,
        "",
        f"Humidity: {data.get('humidity', '-')}%",
        f"Wind: {data.get('speed', '-')} m/s @ {data.get('degrees', '-')}°",
        f"Pressure: {data.get('pressure', '-')} hPa",
        "",
        f"Sunrise: {data.get('sunrise', '-')}",
        f"Sunset: {data.get('sunset', '-')}",
    ]

    lat = data.get("latitude")
    lon = data.get("longitude")
    if lat is not None and lon is not None:
        lines.append(f"Coords: {lat}, {lon}")

    return "\n".join(lines)


def weather_reply(location: str) -> str:
    data = fetch_weather_raw(location)
    return format_weather(data)
