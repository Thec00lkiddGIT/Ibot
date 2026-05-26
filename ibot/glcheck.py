"""GLSeries web filter check API (live.glseries.net)."""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from ibot.config import glseries_api_token, glseries_base_url

TIMEOUT_SECONDS = 45
MAX_MESSAGE_LEN = 3800


@dataclass(frozen=True)
class FilterResult:
    key: str
    name: str
    category: str
    blocked: bool
    error: bool
    response_time: int | None = None


def _request(path: str, params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    url = f"{glseries_base_url().rstrip('/')}{path}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Ibot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API HTTP {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        # Common on captive portals / SSL-intercepting networks: server returns non-TLS
        # bytes on an HTTPS socket, producing WRONG_VERSION_NUMBER.
        if isinstance(reason, ssl.SSLError) and "WRONG_VERSION_NUMBER" in str(reason).upper():
            raise RuntimeError(
                "Network error: SSL handshake failed (WRONG_VERSION_NUMBER). "
                "This usually means your network/proxy is intercepting or blocking "
                "`https://live.glseries.net`. Try a different network/hotspot/VPN, "
                "or set `GLSERIES_BASE_URL` to a reachable endpoint."
            ) from exc
        raise RuntimeError(f"Network error: {reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON from GLSeries API") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Unexpected API response")
    if not data.get("success", True) and data.get("error"):
        raise RuntimeError(str(data.get("error")))
    return data


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError("URL required")
    if not re.match(r"^https?://", raw, re.I):
        raw = f"https://{raw}"
    return raw


def fetch_check(url: str, *, filter_key: str | None = None) -> tuple[str, list[FilterResult]]:
    params = {"token": glseries_api_token(), "url": normalize_url(url)}
    if filter_key:
        params["filter"] = filter_key
    data = _request("/check", params)
    results = [_parse_result(row) for row in data.get("results") or []]
    display_url = str(data.get("url") or url)
    return display_url, results


def fetch_bulk(urls: list[str]) -> list[tuple[str, list[FilterResult]]]:
    if not urls:
        raise ValueError("At least one URL required")
    if len(urls) > 3:
        raise ValueError("Bulk check supports up to 3 URLs")
    normalized = [normalize_url(u) for u in urls]
    params = {
        "token": glseries_api_token(),
        "urls": ",".join(normalized),
    }
    data = _request("/bulk", params)
    out: list[tuple[str, list[FilterResult]]] = []
    for entry in data.get("results") or []:
        if not isinstance(entry, dict):
            continue
        display_url = str(entry.get("url") or "?")
        rows = [_parse_result(row) for row in entry.get("results") or []]
        out.append((display_url, rows))
    return out


def _parse_result(row: dict) -> FilterResult:
    return FilterResult(
        key=str(row.get("filter") or ""),
        name=str(row.get("name") or row.get("filter") or "Unknown"),
        category=str(row.get("category") or "Unknown"),
        blocked=bool(row.get("blocked")),
        error=bool(row.get("error")),
        response_time=row.get("responseTime"),
    )


def _status_text(result: FilterResult) -> str:
    if result.error:
        return "Error"
    return "Blocked" if result.blocked else "Allowed"


def _filter_embed_block(result: FilterResult) -> str:
    status = _status_text(result)
    lines = [
        result.name,
        f"  Category: {result.category}",
        f"  Status: {status}",
    ]
    return "\n".join(lines)


def format_check_embed(display_url: str, results: list[FilterResult]) -> list[str]:
    """Format one URL check as iMessage-friendly embed chunk(s)."""
    if not results:
        return [f"URL Check\n{display_url}\n\nNo filter results."]

    blocked_count = sum(1 for r in results if r.blocked and not r.error)
    header = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 URL Check\n"
        f"{display_url}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"{len(results)} filters · {blocked_count} blocked"
    )

    blocks = [_filter_embed_block(r) for r in results]
    body_parts: list[str] = []
    current = header + "\n\n"
    for block in blocks:
        candidate = (current + block + "\n\n") if current else block + "\n\n"
        if len(candidate) + len(footer) > MAX_MESSAGE_LEN and current.strip() != header.strip():
            body_parts.append(current.rstrip())
            current = block + "\n\n"
        else:
            current = candidate
    body_parts.append(current.rstrip() + footer)

    if len(body_parts) == 1:
        return body_parts
    return [f"{chunk}\n({i}/{len(body_parts)})" for i, chunk in enumerate(body_parts, 1)]


def check_reply(url: str, *, filter_key: str | None = None) -> list[str]:
    display_url, results = fetch_check(url, filter_key=filter_key)
    return format_check_embed(display_url, results)


def bulk_reply(urls: list[str]) -> list[str]:
    all_messages: list[str] = []
    for display_url, results in fetch_bulk(urls):
        all_messages.extend(format_check_embed(display_url, results))
    return all_messages
