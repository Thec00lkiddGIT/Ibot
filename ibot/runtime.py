"""Background bot loop with events for the GUI."""

from __future__ import annotations

import re
import sqlite3
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from ibot.commands import PREFIX, dispatch
from ibot.afk import send_afk_reply
from ibot.bot_log import set_emitter
from ibot.db import connect, fetch_batch, max_rowid
from ibot.permissions import check_access, fda_fix_message, fda_target_for_host, is_app_bundle, open_fda_settings, bundle_fda_python_path
from ibot.send import check_automation
from ibot.state import load_gui_settings, load_state, load_stats, save_gui_settings, save_state, save_stats

COMMAND_RE = re.compile(rf"^{re.escape(PREFIX)}(\w+)", re.IGNORECASE)


@dataclass
class BotEvent:
    id: int
    kind: str  # info | success | error
    title: str
    body: str
    source: str
    ts: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BotSettings:
    poll: float = 0.5
    include_self: bool = True
    verbose: bool = True
    catch_up: bool = False
    running: bool = False
    afk_enabled: bool = False
    afk_message: str = ""


class BotRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._settings = BotSettings()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._events: deque[BotEvent] = deque(maxlen=200)
        self._event_id = 0
        self._session = uuid.uuid4().hex[:8]
        self._last_rowid = 0
        self._error: str | None = None
        self._commands_used = 0
        self._messages_seen = 0
        stats = load_stats()
        self._commands_used = stats["commands_used"]
        self._messages_seen = stats["messages_seen"]
        set_emitter(self._push_event)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def _push_event(
        self,
        kind: str,
        title: str,
        body: str,
        source: str = "Ibot",
    ) -> BotEvent:
        with self._lock:
            self._event_id += 1
            ev = BotEvent(
                id=self._event_id,
                kind=kind,
                title=title,
                body=body,
                source=source,
                ts=self._now_iso(),
            )
            self._events.append(ev)
            return ev

    def settings(self) -> BotSettings:
        with self._lock:
            return BotSettings(**asdict(self._settings))

    def update_settings(self, **kwargs: object) -> BotSettings:
        persist: dict[str, object] = {}
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._settings, key):
                    setattr(self._settings, key, value)
                    if key in ("include_self", "verbose", "catch_up", "afk_enabled", "afk_message"):
                        persist[key] = value
            result = BotSettings(**asdict(self._settings))
        if persist:
            save_gui_settings(**persist)
        return result

    def _sync_running_state(self) -> None:
        """Mark stopped if the worker thread died while still flagged running."""
        with self._lock:
            if not self._settings.running:
                return
            if self._thread is None or not self._thread.is_alive():
                self._settings.running = False
                if not self._error:
                    self._error = "Bot loop stopped unexpectedly. Click Start bot again."

    def start(self) -> tuple[bool, str]:
        with self._lock:
            if self._settings.running:
                return True, "Already running"
            self._stop.clear()
            self._error = None
            self._settings.running = True
        self._thread = threading.Thread(target=self._loop, name="ibot-loop", daemon=True)
        self._thread.start()
        self._push_event("success", "Bot started", "Watching Messages for commands.")
        return True, "Started"

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self._settings.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._push_event("info", "Bot stopped", "Polling paused.")

    def events_since(self, after_id: int) -> dict:
        with self._lock:
            return {
                "session": self._session,
                "latest_id": self._event_id,
                "events": [e.to_dict() for e in self._events if e.id > after_id],
            }

    def status(self) -> dict:
        self._sync_running_state()
        access = check_access()
        auto_ok, auto_msg = check_automation()
        with self._lock:
            return {
                "running": self._settings.running,
                "include_self": self._settings.include_self,
                "verbose": self._settings.verbose,
                "catch_up": self._settings.catch_up,
                "poll": self._settings.poll,
                "afk_enabled": self._settings.afk_enabled,
                "afk_message": self._settings.afk_message,
                "last_rowid": self._last_rowid,
                "commands_used": self._commands_used,
                "messages_seen": self._messages_seen,
                "error": self._error,
                "fda_ok": access.sqlite_ok,
                "fda_host": access.host_app,
                "fda_target": fda_target_for_host(access.host_app, python=access.python),
                "fda_bundle": is_app_bundle(),
                "fda_app_path": access.app_bundle,
                "fda_python_path": bundle_fda_python_path() or access.python,
                "fda_help": None if access.sqlite_ok else fda_fix_message(python=access.python, host=access.host_app),
                "fda_error": access.error,
                "python": access.python,
                "automation_ok": auto_ok,
                "automation_msg": auto_msg,
                "session": self._session,
                "latest_event_id": self._event_id,
            }

    def _command_name(self, body: str) -> str | None:
        m = COMMAND_RE.match(body.strip())
        return m.group(1).lower() if m else None

    def _persist_stats(self) -> None:
        save_stats(self._commands_used, self._messages_seen)

    def _loop(self) -> None:
        conn = None
        try:
            conn = connect()
        except (FileNotFoundError, PermissionError) as exc:
            with self._lock:
                self._error = str(exc)
                self._settings.running = False
            self._push_event("error", "Cannot open chat.db", str(exc))
            return

        settings = self.settings()
        if settings.catch_up:
            last_rowid = load_state()
            watch_note = f"Resuming from saved ROWID {last_rowid}."
        else:
            last_rowid = max_rowid(conn)
            save_state(last_rowid)
            watch_note = (
                f"Only messages after ROWID {last_rowid} "
                "(enable Catch up before starting to replay older traffic)."
            )

        with self._lock:
            self._last_rowid = last_rowid
        self._push_event("info", "Watching messages", watch_note)
        if not settings.include_self:
            self._push_event(
                "info",
                "Self messages ignored",
                "Turn on \"React to my messages\" to test !commands from this Mac.",
            )

        while not self._stop.is_set():
            settings = self.settings()
            try:
                batch = fetch_batch(conn, last_rowid, include_self=settings.include_self)
            except sqlite3.Error as exc:
                with self._lock:
                    self._error = str(exc)
                self._push_event("error", "Database read failed", str(exc))
                time.sleep(2.0)
                continue

            for message in batch.messages:
                if self._stop.is_set():
                    break
                who = message.handle_id or message.chat_identifier or "?"
                src = "you" if message.is_from_me else "them"
                preview = message.body[:120] + ("…" if len(message.body) > 120 else "")

                with self._lock:
                    self._messages_seen += 1

                cmd = self._command_name(message.body)
                if settings.verbose or cmd:
                    self._push_event(
                        "info",
                        f"Message from {src}",
                        f"{who}: {preview}",
                        source=message.chat_identifier or "iMessage",
                    )

                try:
                    handled = False
                    if not message.is_from_me:
                        handled = dispatch(message)
                    elif settings.include_self:
                        handled = dispatch(message)
                except Exception as exc:  # noqa: BLE001
                    self._push_event(
                        "error",
                        "Reply failed",
                        str(exc),
                        source=who,
                    )
                    continue

                if handled:
                    with self._lock:
                        self._commands_used += 1
                    label = cmd or "command"
                    self._push_event(
                        "success",
                        f"!{label} handled",
                        f"Replied to {who}",
                        source=message.chat_identifier or "iMessage",
                    )
                    self._persist_stats()
                    continue

                if (
                    settings.afk_enabled
                    and not message.is_from_me
                    and message.body.strip()
                    and not cmd
                ):
                    reply_text = (settings.afk_message or "").strip()
                    if not reply_text:
                        continue
                    try:
                        method = send_afk_reply(message, reply_text)
                        self._push_event(
                            "success",
                            "AFK reply sent",
                            f"{who}: {reply_text[:80]}",
                            source=message.chat_identifier or "iMessage",
                        )
                        print(f"  afk send: {method}")
                    except Exception as exc:  # noqa: BLE001
                        self._push_event(
                            "error",
                            "AFK reply failed",
                            str(exc),
                            source=who,
                        )
                    continue

            if batch.watermark > last_rowid:
                last_rowid = batch.watermark
                save_state(last_rowid)
                with self._lock:
                    self._last_rowid = last_rowid

            time.sleep(max(0.2, settings.poll))

        if conn:
            conn.close()
        with self._lock:
            self._settings.running = False


_runtime: BotRuntime | None = None


def get_runtime() -> BotRuntime:
    global _runtime
    if _runtime is None:
        _runtime = BotRuntime()
        set_emitter(_runtime._push_event)
        gui = load_gui_settings()
        _runtime.update_settings(
            include_self=bool(gui["include_self"]),
            verbose=bool(gui["verbose"]),
            catch_up=bool(gui["catch_up"]),
            afk_enabled=bool(gui.get("afk_enabled", False)),
            afk_message=str(gui.get("afk_message", "")),
        )
    return _runtime
