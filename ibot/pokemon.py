"""PokéAPI (https://pokeapi.co) lookups."""

from __future__ import annotations

import json
import random
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://pokeapi.co/api/v2"
MAX_POKEMON_ID = 1025
TIMEOUT_SECONDS = 20


def _fetch_json(path: str) -> dict:
    path = path if path.startswith("/") else f"/{path}"
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "Ibot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError("Pokémon not found. Use a name or National Dex number.") from exc
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PokéAPI HTTP {exc.code}: {detail[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected PokéAPI response")
    return data


def _fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Ibot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Sprite HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def _species_flavor(species: dict) -> str:
    for entry in species.get("flavor_text_entries") or []:
        lang = (entry.get("language") or {}).get("name")
        if lang == "en":
            text = str(entry.get("flavor_text", "")).replace("\n", " ").replace("\f", " ")
            return " ".join(text.split())
    return ""


def _format_stats(data: dict) -> str:
    order = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")
    by_name = {
        (s.get("stat") or {}).get("name"): s.get("base_stat")
        for s in data.get("stats") or []
    }
    labels = {
        "hp": "HP",
        "attack": "Atk",
        "defense": "Def",
        "special-attack": "SpA",
        "special-defense": "SpD",
        "speed": "Spe",
    }
    parts = [f"{labels[k]} {by_name[k]}" for k in order if k in by_name]
    return " · ".join(parts)


def _resolve_query(query: str) -> str:
    text = query.strip().lower()
    if not text or text == "random":
        return str(random.randint(1, MAX_POKEMON_ID))
    return urllib.parse.quote(text)


def pokemon_lookup(query: str) -> tuple[str, bytes | None, str]:
    """Return caption text, optional sprite bytes, and filename."""
    key = _resolve_query(query)
    data = _fetch_json(f"/pokemon/{key}")

    name = str(data.get("name", "?")).replace("-", " ").title()
    pid = data.get("id", "?")
    types = ", ".join(
        t["type"]["name"].replace("-", " ").title()
        for t in data.get("types") or []
        if isinstance(t, dict) and "type" in t
    )
    abilities = ", ".join(
        a["ability"]["name"].replace("-", " ").title()
        for a in (data.get("abilities") or [])[:4]
        if isinstance(a, dict) and "ability" in a
    )
    height_m = (data.get("height") or 0) / 10
    weight_kg = (data.get("weight") or 0) / 10

    flavor = ""
    try:
        species = _fetch_json(f"/pokemon-species/{data.get('id', key)}")
        flavor = _species_flavor(species)
    except (ValueError, RuntimeError):
        pass

    lines = [
        f"#{pid} {name}",
        f"Type: {types or '?'}",
        f"Abilities: {abilities or '?'}",
        f"Height: {height_m:g} m · Weight: {weight_kg:g} kg",
        _format_stats(data),
    ]
    if flavor:
        if len(flavor) > 280:
            flavor = flavor[:277] + "..."
        lines.append(flavor)
    lines.append(f"https://pokeapi.co/api/v2/pokemon/{data.get('id', key)}")

    sprite_bytes: bytes | None = None
    sprite_name = f"{name.lower().replace(' ', '-')}.png"
    sprite_url = (data.get("sprites") or {}).get("front_default")
    if isinstance(sprite_url, str) and sprite_url.startswith("http"):
        try:
            png = _fetch_bytes(sprite_url)
            if png.startswith(b"\x89PNG") or png.startswith(b"\xff\xd8"):
                ext = "png" if png.startswith(b"\x89PNG") else "jpg"
                sprite_name = f"{name.lower().replace(' ', '-')}.{ext}"
                sprite_bytes = png
        except RuntimeError:
            pass

    return "\n".join(lines), sprite_bytes, sprite_name
