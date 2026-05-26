#!/usr/bin/env python3
"""Launch the Ibot app (native WebKit dashboard)."""

from __future__ import annotations

import argparse
import sys


def _run_web(host: str, port: int) -> int:
    import webbrowser

    from ibot.gui.bootstrap import prepare_runtime
    from ibot.gui.server import get_runtime, run_server

    server = run_server(host, port)
    url = f"http://{host}:{port}/"
    print(f"Ibot web UI: {url}", flush=True)
    prepare_runtime()
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        get_runtime().stop()
        server.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ibot app")
    parser.add_argument(
        "--web",
        action="store_true",
        help="Open in your browser instead of the native window",
    )
    parser.add_argument(
        "--tk",
        action="store_true",
        help="Old tkinter UI (broken on many Macs)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.web:
        return _run_web(args.host, args.port)

    if args.tk:
        try:
            from ibot.gui.app import run_app
        except ImportError:
            print("tkinter not available", file=sys.stderr)
            return 1
        run_app()
        return 0

    from ibot.gui.native_window import run_native_app

    run_native_app(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
