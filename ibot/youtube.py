"""SerpAPI YouTube search, video info, and transcripts."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import parse_qs, urlparse

from ibot.config import serpapi_key

API_BASE = "https://serpapi.com/search.json"
TIMEOUT_SECONDS = 45
MAX_MESSAGE_LEN = 3800


def _request(params: dict[str, str]) -> dict:
    params = {**params, "api_key": serpapi_key()}
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Ibot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API HTTP {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON from SerpAPI") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Unexpected API response")
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data


def extract_video_id(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError("Video ID or URL required")

    if raw.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        if parsed.hostname in ("youtu.be", "www.youtu.be"):
            vid = parsed.path.lstrip("/").split("/")[0]
            if vid:
                return vid
        if parsed.hostname and "youtube" in parsed.hostname:
            qs = parse_qs(parsed.query)
            if qs.get("v"):
                return qs["v"][0]
            match = re.search(r"/(?:embed|shorts|live)/([^/?&]+)", parsed.path)
            if match:
                return match.group(1)

    if re.fullmatch(r"[\w-]{6,}", raw):
        return raw

    raise ValueError("Invalid YouTube video ID or URL")


def _chunk_text(header: str, body: str, footer: str = "") -> list[str]:
    chunks: list[str] = []
    current = header + "\n\n"
    for line in body.splitlines():
        candidate = current + line + "\n"
        limit = MAX_MESSAGE_LEN - len(footer) - 20
        if len(candidate) > limit and current.strip() != header.strip():
            chunks.append(current.rstrip())
            current = line + "\n"
        else:
            current = candidate
    if current.strip():
        chunks.append(current.rstrip() + footer)
    return chunks or [header + footer]


def format_search(data: dict, query: str) -> str:
    results = data.get("video_results") or []
    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "YouTube Search",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Query: {query}",
        "",
    ]
    if not results:
        lines.append("No results found.")
    else:
        for i, item in enumerate(results[:8], 1):
            if not isinstance(item, dict):
                continue
            title = item.get("title", "?")
            vid = item.get("video_id", "?")
            channel = (item.get("channel") or {}).get("name", "?")
            views = item.get("views", "?")
            length = item.get("length", "?")
            link = item.get("link", f"https://youtube.com/watch?v={vid}")
            lines.extend(
                [
                    f"{i}. {title}",
                    f"   Channel: {channel}",
                    f"   Views: {views} · Length: {length}",
                    f"   ID: {vid}",
                    f"   {link}",
                    "",
                ]
            )
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_video(data: dict, video_id: str) -> str:
    title = data.get("title", "?")
    channel = (data.get("channel") or {}).get("name", "?")
    views = data.get("views", "?")
    likes = data.get("likes", "?")
    published = data.get("published_date", "?")
    link = f"https://youtube.com/watch?v={video_id}"

    desc = data.get("description")
    if isinstance(desc, dict):
        desc_text = str(desc.get("content") or "")
    else:
        desc_text = str(desc or "")
    if len(desc_text) > 600:
        desc_text = desc_text[:597] + "..."

    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "YouTube Video",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        title,
        "",
        f"Channel: {channel}",
        f"Views: {views}",
        f"Likes: {likes}",
        f"Published: {published}",
        f"ID: {video_id}",
        f"{link}",
        "",
    ]
    if desc_text:
        lines.extend(["Description:", desc_text, ""])
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_transcript(data: dict, video_id: str) -> list[str]:
    entries = data.get("transcript") or []
    link = f"https://youtube.com/watch?v={video_id}"
    header = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "YouTube Transcript\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"ID: {video_id}\n"
        f"{link}\n"
    )
    footer = "\n━━━━━━━━━━━━━━━━━━━━"

    if not entries:
        return [header + "\nNo transcript available." + footer]

    body_lines: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        time_text = item.get("start_time_text") or item.get("start_time_label") or "?"
        snippet = str(item.get("snippet") or "").strip()
        if snippet:
            body_lines.append(f"[{time_text}] {snippet}")

    if not body_lines:
        return [header + "\nNo transcript text found." + footer]

    body = "\n".join(body_lines)
    chunks = _chunk_text(header, body, footer)
    if len(chunks) == 1:
        return chunks
    return [f"{chunk}\n({i}/{len(chunks)})" for i, chunk in enumerate(chunks, 1)]


def search_reply(query: str) -> str:
    if not query.strip():
        raise ValueError("Search query required")
    data = _request({"engine": "youtube", "search_query": query.strip()})
    return format_search(data, query.strip())


def video_reply(raw: str) -> str:
    video_id = extract_video_id(raw)
    data = _request({"engine": "youtube_video", "v": video_id})
    return format_video(data, video_id)


def transcript_reply(raw: str) -> list[str]:
    video_id = extract_video_id(raw)
    data = _request(
        {
            "engine": "youtube_video_transcript",
            "v": video_id,
            "language_code": "en",
        }
    )
    return format_transcript(data, video_id)


def youtube_reply(subcommand: str, arg: str) -> str | list[str]:
    sub = subcommand.lower()
    if sub == "search":
        return search_reply(arg)
    if sub == "video":
        return video_reply(arg)
    if sub == "trans":
        return transcript_reply(arg)
    raise ValueError(f"Unknown subcommand: {subcommand}")
