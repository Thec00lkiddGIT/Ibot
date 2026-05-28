"""Write outbound attachment bytes to a temp file."""

from __future__ import annotations

import tempfile
from pathlib import Path


def write_temp_attachment(filename: str, data: bytes) -> Path:
    suffix = Path(filename).suffix or ".bin"
    tmp = Path(tempfile.mkstemp(prefix="ibot-", suffix=suffix)[1])
    tmp.write_bytes(data)
    return tmp
