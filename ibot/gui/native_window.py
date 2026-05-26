"""Native app window using macOS WebKit (Safari engine) - not Chrome."""

from __future__ import annotations

import threading
import time


def run_native_app(host: str = "127.0.0.1", port: int = 8765) -> None:
    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "Missing pywebview. Install it once:\n\n"
            "  pip3 install pywebview\n\n"
            "This opens a native macOS window (WebKit/Safari engine), not Chrome."
        ) from exc

    from ibot.gui.bootstrap import prepare_runtime
    from ibot.gui.server import get_runtime, run_server

    server = run_server(host, port)
    url = f"http://{host}:{port}/"

    threading.Thread(target=server.serve_forever, name="ibot-http", daemon=True).start()
    time.sleep(0.3)
    prepare_runtime()

    webview.create_window(
        "Ibot",
        url,
        width=1100,
        height=700,
        min_size=(880, 560),
        background_color="#060a12",
        text_select=True,
    )
    webview.start(gui="cocoa")
    get_runtime().stop()
    server.shutdown()
