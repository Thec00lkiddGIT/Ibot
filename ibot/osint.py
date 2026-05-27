"""OSINT Industries API (https://app.osint.industries)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ibot.config import osint_api_key

API_BASE = "https://api.osint.industries"
TIMEOUT_SECONDS = 75
MAX_MESSAGE_LEN = 3800

SEARCH_TYPES = frozenset({"email", "phone", "username", "name", "wallet"})


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Ibot/1.0",
        "accept": "application/json",
        "api-key": osint_api_key(),
    }


def _read_json(req: urllib.request.Request) -> Any:
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        msg = body[:300] if body else exc.reason
        if exc.code == 401:
            raise RuntimeError("Invalid OSINT API key.") from exc
        if exc.code == 402:
            raise RuntimeError("OSINT credits exhausted.") from exc
        raise RuntimeError(f"OSINT API HTTP {exc.code}: {msg}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON from OSINT API") from exc


def fetch_credits() -> dict[str, Any]:
    url = f"{API_BASE}/misc/credits"
    req = urllib.request.Request(url, headers=_headers())
    data = _read_json(req)
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected credits response")
    return data


def fetch_search(
    search_type: str,
    query: str,
    *,
    timeout: int = 60,
    premium: bool = False,
    exact_match: bool = True,
) -> list[dict[str, Any]]:
    params: dict[str, str | int] = {
        "type": search_type,
        "query": query,
        "timeout": max(25, min(80, timeout)),
        "exact_match": str(exact_match).lower(),
        "premium": str(premium).lower(),
    }
    url = f"{API_BASE}/v2/request?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=_headers())
    data = _read_json(req)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        modules = data.get("modules") or data.get("results")
        if isinstance(modules, list):
            return [item for item in modules if isinstance(item, dict)]
        return [data]
    raise RuntimeError("Unexpected search response")


def _field_value(raw: Any) -> Any:
    if isinstance(raw, dict):
        if "value" in raw:
            return raw["value"]
        if "proper_key" in raw and "value" in raw:
            return raw["value"]
    return raw


def _parse_spec_format(spec_format: list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for block in spec_format:
        if not isinstance(block, dict):
            continue
        for key, raw in block.items():
            if key == "platform_variables" and isinstance(raw, list):
                for var in raw:
                    if not isinstance(var, dict):
                        continue
                    label = var.get("proper_key") or var.get("key") or "field"
                    val = var.get("value")
                    if val not in (None, "", []):
                        out[str(label)] = val
            else:
                val = _field_value(raw)
                label = key
                if isinstance(raw, dict) and raw.get("proper_key"):
                    label = raw["proper_key"]
                if val not in (None, "", []):
                    out[str(label).replace("_", " ").title() if "_" in str(label) else str(label)] = val
    return out


def _format_module(mod: dict[str, Any]) -> str:
    name = mod.get("module") or mod.get("name") or "Unknown"
    reliable = mod.get("reliableSource")
    status = mod.get("status") or mod.get("from") or ""
    header = f"▸ {name}"
    if reliable is True:
        header += " ✓"
    lines = [header]
    if status:
        lines.append(f"  status: {status}")

    spec = mod.get("spec_format")
    fields: dict[str, Any] = {}
    if isinstance(spec, list):
        fields = _parse_spec_format(spec)
    elif isinstance(mod.get("data"), dict):
        fields = {k: v for k, v in mod["data"].items() if v not in (None, "", [])}

    for key, val in sorted(fields.items(), key=lambda kv: kv[0].lower()):
        if isinstance(val, (dict, list)):
            val = json.dumps(val, ensure_ascii=False)
        lines.append(f"  {key}: {val}")

    if len(lines) == 1:
        lines.append("  (no fields returned)")
    return "\n".join(lines)


def _chunk_text(header: str, body: str) -> list[str]:
    chunks: list[str] = []
    current = header + "\n\n"
    for line in body.splitlines():
        candidate = current + line + "\n"
        if len(candidate) > MAX_MESSAGE_LEN and current.strip() != header.strip():
            chunks.append(current.rstrip())
            current = line + "\n"
        else:
            current = candidate
    if current.strip():
        chunks.append(current.rstrip())
    return chunks or [header]


def format_credits(data: dict[str, Any]) -> str:
    for key in ("credits", "remaining", "balance", "credit_balance"):
        if key in data:
            return f"OSINT credits remaining: {data[key]}"
    return f"OSINT credits: {json.dumps(data, ensure_ascii=False)}"


def format_search(search_type: str, query: str, modules: list[dict[str, Any]]) -> list[str]:
    if not modules:
        return [f"OSINT ({search_type}): no results for {query}"]

    header = f"OSINT · {search_type} · {query}\n{len(modules)} module(s)"
    body = "\n\n".join(_format_module(m) for m in modules)
    return _chunk_text(header, body)


def credits_reply() -> str:
    return format_credits(fetch_credits())


def search_reply(
    search_type: str,
    query: str,
    *,
    premium: bool = False,
    timeout: int = 60,
) -> list[str]:
    st = search_type.lower()
    if st == "user":
        st = "username"
    if st not in SEARCH_TYPES:
        raise ValueError(f"Unknown type '{search_type}'. Use: email, phone, username, name, wallet")
    if not query.strip():
        raise ValueError(f"Missing query for {st}")
    modules = fetch_search(st, query.strip(), timeout=timeout, premium=premium)
    return format_search(st, query.strip(), modules)
