"""Decode iMessage text from message.text or attributedBody (Ventura+)."""

from __future__ import annotations

import plistlib
import struct

# Ported/adapted from messages-blade-mcp typedstream heuristics (NSArchiver blobs).
_TYPEDSTREAM_MAGIC = b"streamtyped"
_TEXT_MARKERS = (
    b"NSString",
    b"NSMutableString",
    b"NSMutableAttributedString",
    b"NSAttributedString",
)
_CLASS_NAMES = frozenset(
    {
        "NSMutableAttributedString",
        "NSAttributedString",
        "NSString",
        "NSMutableString",
        "NSObject",
        "NSDictionary",
        "streamtyped",
    }
)


def message_text(text: str | None, attributed_body: bytes | memoryview | None) -> str:
    if text and str(text).strip():
        return str(text).strip()
    if attributed_body is None:
        return ""
    if isinstance(attributed_body, memoryview):
        attributed_body = attributed_body.tobytes()
    decoded = decode_attributed_body(attributed_body)
    return decoded.strip() if decoded else ""


def decode_attributed_body(blob: bytes | None) -> str | None:
    if not blob:
        return None

    if blob.startswith(b"bplist"):
        try:
            parsed = plistlib.loads(blob)
            if isinstance(parsed, str) and _looks_like_text(parsed):
                return parsed
        except Exception:
            pass

    for fn in (_decode_typedstream, _decode_fallback):
        try:
            result = fn(blob)
            if result:
                return result
        except Exception:
            continue
    return None


def _decode_typedstream(blob: bytes) -> str | None:
    candidates: list[str] = []

    if _TYPEDSTREAM_MAGIC in blob or b"typedstream" in blob:
        for marker in _TEXT_MARKERS:
            start = 0
            while True:
                idx = blob.find(marker, start)
                if idx == -1:
                    break
                search_start = idx + len(marker)
                found = _extract_length_prefixed_string(blob, search_start, search_start + 300)
                if found:
                    candidates.append(found)
                start = idx + 1

        for pattern in (b"\x84\x01", b"\x84\x84", b"\x69\x01"):
            start = 0
            while True:
                idx = blob.find(pattern, start)
                if idx == -1:
                    break
                base = idx + 2
                # Common: \x84\x01\x2b <len> <utf8>  (+ opcode then 1-byte length)
                if base < len(blob) and blob[base] == 0x2B and base + 1 < len(blob):
                    length = blob[base + 1]
                    text_start = base + 2
                    if text_start < len(blob):
                        raw = blob[text_start : text_start + max(length, 1)]
                        raw = raw.split(b"\x86")[0].split(b"\x84")[0]
                        candidate = _try_decode_utf8(raw)
                        if candidate:
                            candidates.append(candidate.lstrip("+"))
                found = _extract_length_prefixed_string(blob, base, base + 300)
                if found:
                    candidates.append(found)
                start = idx + 1

    best = _pick_best_candidate(candidates)
    return best


def _decode_fallback(blob: bytes) -> str | None:
    candidates: list[str] = []

    for terminator in (b"\x86\x84", b"\x86\x86", b"\x00\x86"):
        for part in blob.split(terminator):
            tail = part[-500:] if len(part) > 500 else part
            found = _try_extract_readable_tail(tail)
            if found:
                candidates.append(found)

    for found in _find_text_runs(blob):
        candidates.append(found)

    return _pick_best_candidate(candidates)


def _extract_length_prefixed_string(blob: bytes, start: int, end: int) -> str | None:
    end = min(end, len(blob))
    pos = start

    while pos < end - 1:
        byte = blob[pos]
        if byte == 0:
            pos += 1
            continue

        if byte == 0x81 and pos + 3 <= len(blob):
            length = struct.unpack_from("<H", blob, pos + 1)[0]
            str_start = pos + 3
            if 1 <= length <= 100_000 and str_start + length <= len(blob):
                candidate = _try_decode_utf8(blob[str_start : str_start + length])
                if candidate and _looks_like_text(candidate):
                    return candidate
            pos += 1
            continue

        if byte == 0x82 and pos + 5 <= len(blob):
            length = struct.unpack_from("<I", blob, pos + 1)[0]
            str_start = pos + 5
            if 1 <= length <= 1_000_000 and str_start + length <= len(blob):
                candidate = _try_decode_utf8(blob[str_start : str_start + length])
                if candidate and _looks_like_text(candidate):
                    return candidate
            pos += 1
            continue

        if 1 <= byte <= 127:
            str_start = pos + 1
            if str_start + byte <= len(blob):
                candidate = _try_decode_utf8(blob[str_start : str_start + byte])
                if candidate and _looks_like_text(candidate):
                    return candidate

        pos += 1

    return None


def _find_text_runs(blob: bytes) -> list[str]:
    """Collect plausible UTF-8 runs (not just the longest)."""
    found: list[str] = []
    i = 0
    while i < len(blob):
        for end in range(min(i + 500, len(blob)), i + 1, -1):
            candidate = _try_decode_utf8(blob[i:end])
            if candidate and _looks_like_text(candidate) and len(candidate) >= 1:
                found.append(candidate)
                i = end
                break
        else:
            i += 1
    return found


def _try_extract_readable_tail(data: bytes) -> str | None:
    text_bytes = bytearray()
    for b in reversed(data):
        if 32 <= b <= 126 or b in (0x0A, 0x0D):
            text_bytes.append(b)
        elif text_bytes:
            break
    if not text_bytes:
        return None
    text_bytes.reverse()
    candidate = _try_decode_utf8(bytes(text_bytes))
    return candidate if candidate and _looks_like_text(candidate) else None


def _try_decode_utf8(data: bytes) -> str | None:
    try:
        text = data.decode("utf-8")
        text = "".join(
            c for c in text if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127)
        )
        return text.strip() if text.strip() else None
    except (UnicodeDecodeError, ValueError):
        return None


def _looks_like_text(s: str) -> bool:
    if not s:
        return False
    if s in _CLASS_NAMES:
        return False
    if "kIMMessage" in s and "Attribute" in s:
        return False
    if s.startswith("__kIM") or (s.startswith("NS") and "Attribute" in s):
        return False
    if s.startswith("_kIM"):
        return False
    if "streamtyped" in s or "NSDictionary" in s:
        return False

    printable = sum(1 for c in s if c.isalnum() or c in " .,!?;:'-\"()\n\t@#$%&*+=/")
    if len(s) == 0:
        return False
    return printable / len(s) >= 0.6


def _pick_best_candidate(candidates: list[str]) -> str | None:
    if not candidates:
        return None

    scored: list[tuple[int, str]] = []
    for raw in candidates:
        s = raw.lstrip("+").strip()
        if not _looks_like_text(s):
            continue
        score = len(s) * 3
        if len(s) < 3:
            score -= 80
        if len(s) >= 4:
            score += 30
        if s.startswith("!"):
            score += 300
        if any(c.isalpha() for c in s):
            score += 20
        if " " in s:
            score += 15
        if s.startswith("__"):
            score -= 500
        scored.append((score, s))

    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]
