"""Local web dashboard for Ibot (stdlib HTTP server)."""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ibot.config import config_env_path
from ibot.hostinfo import computer_handle
from ibot.paths import app_support_dir, ensure_env_file

from ibot.gui.commands_list import COMMANDS
from ibot.runtime import BotRuntime, get_runtime
from ibot.script_hub import (
    delete_script,
    list_scripts,
    new_script_template,
    read_script_code,
    run_script,
    save_script,
    set_script_enabled,
    test_script_code,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: object) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "IbotDashboard/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            ensure_env_file()
            rt = get_runtime()
            st = rt.status()
            st["display_name"] = os.environ.get("IBOT_DISPLAY_NAME", "Ibot")
            st["handle"] = computer_handle()
            st["version"] = "1.0.2"
            st["env_path"] = config_env_path()
            st["app_support"] = str(app_support_dir())
            built_ins = [{"name": n, "help": h, "source": "builtin"} for n, h in COMMANDS]
            hub = []
            for s in list_scripts():
                for cmd in s.commands or [s.command]:
                    if not cmd:
                        continue
                    hub.append(
                        {
                            "name": cmd,
                            "help": s.description or s.help,
                            "source": "hub",
                            "enabled": s.enabled,
                        }
                    )
            st["commands"] = built_ins + hub
            _json_response(self, 200, st)
            return

        if path == "/api/scripts":
            scripts = []
            for s in list_scripts():
                item = s.to_dict()
                item["code"] = read_script_code(s.id)
                scripts.append(item)
            _json_response(self, 200, {"scripts": scripts})
            return

        if path == "/api/scripts/template":
            qs = parse_qs(parsed.query)
            name = qs.get("name", ["My Script"])[0]
            command = qs.get("command", ["mycommand"])[0]
            author = qs.get("author", ["Ibot"])[0]
            description = qs.get("description", ["My custom command"])[0]
            _json_response(
                self,
                200,
                new_script_template(
                    name=name,
                    author=author,
                    command=command,
                    description=description,
                ),
            )
            return

        if path == "/api/events":
            qs = parse_qs(parsed.query)
            after = int(qs.get("after", ["0"])[0])
            _json_response(self, 200, {"events": get_runtime().events_since(after)})
            return

        if path in ("/", "/index.html"):
            self._serve_file(STATIC_DIR / "index.html")
            return

        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            self._serve_file(STATIC_DIR / rel)
            return

        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            _json_response(self, 400, {"ok": False, "error": "invalid json"})
            return

        if path == "/api/scripts":
            action = data.get("action", "save")
            if action == "save":
                script, err = save_script(
                    script_id=data.get("id") or None,
                    name=str(data.get("name", "")),
                    author=str(data.get("author", "Ibot")),
                    description=str(data.get("description", "") or data.get("help", "")),
                    usage=str(data.get("usage", "")),
                    command=str(data.get("command", "")),
                    help_text=str(data.get("help", "")),
                    code=str(data.get("code", "")),
                    enabled=bool(data.get("enabled", True)),
                )
                if err:
                    _json_response(self, 400, {"ok": False, "error": err})
                    return
                _json_response(
                    self,
                    200,
                    {"ok": True, "script": script.to_dict() if script else None},
                )
                return
            if action == "delete":
                ok = delete_script(str(data.get("id", "")))
                _json_response(self, 200, {"ok": ok})
                return
            if action == "toggle":
                script = set_script_enabled(
                    str(data.get("id", "")),
                    bool(data.get("enabled", True)),
                )
                if script is None:
                    _json_response(self, 404, {"ok": False, "error": "not found"})
                    return
                _json_response(self, 200, {"ok": True, "script": script.to_dict()})
                return
            if action == "test":
                script_id = str(data.get("id", ""))
                args = str(data.get("args", ""))
                command = str(data.get("command", ""))
                code = data.get("code")
                try:
                    if code is not None:
                        result = test_script_code(str(code), command, args)
                    else:
                        result = run_script(script_id, args)
                except Exception as exc:  # noqa: BLE001
                    _json_response(self, 400, {"ok": False, "error": str(exc)})
                    return
                _json_response(self, 200, {"ok": True, "result": result})
                return
            _json_response(self, 400, {"ok": False, "error": "unknown action"})
            return

        if path != "/api/control":
            self.send_error(404)
            return

        rt = get_runtime()
        action = data.get("action", "")

        if action == "start":
            ok, msg = rt.start()
            _json_response(self, 200, {"ok": ok, "message": msg})
            return

        if action == "stop":
            rt.stop()
            _json_response(self, 200, {"ok": True, "message": "Stopped"})
            return

        if action == "settings":
            allowed = {}
            for key in ("include_self", "verbose", "catch_up", "poll"):
                if key in data:
                    allowed[key] = data[key]
            settings = rt.update_settings(**allowed)
            _json_response(
                self,
                200,
                {"ok": True, "settings": settings.__dict__},
            )
            return

        if action == "open_fda":
            from ibot.permissions import open_fda_settings

            ok = open_fda_settings()
            _json_response(self, 200, {"ok": ok})
            return

        if action == "open_env":
            from ibot.paths import open_env_in_editor

            ok = open_env_in_editor()
            _json_response(self, 200, {"ok": ok, "path": config_env_path()})
            return

        _json_response(self, 400, {"ok": False, "error": "unknown action"})

    def _serve_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        content = path.read_bytes()
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    return server
