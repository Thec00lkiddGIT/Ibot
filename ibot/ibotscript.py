"""IbotScript API for custom iMessage commands."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ibot.db import IncomingMessage

HUB_DIR = Path(__file__).resolve().parents[1] / "scripts" / "hub"
JSON_DIR = HUB_DIR / "json"
CONFIG_FILE = HUB_DIR / "config.json"

_current_script_id: str | None = None


def getScriptsPath() -> str:
    """Return the Script Hub directory."""
    HUB_DIR.mkdir(parents=True, exist_ok=True)
    return str(HUB_DIR)


def _load_config_file() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_config_file(data: dict) -> None:
    HUB_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n")


def _script_prefix() -> str:
    if not _current_script_id:
        return ""
    return f"{_current_script_id}__"


def getConfigData() -> dict:
    """Key-value config for the active script (namespaced in shared config.json)."""
    all_cfg = _load_config_file()
    prefix = _script_prefix()
    if not prefix:
        return dict(all_cfg)
    return {k[len(prefix) :]: v for k, v in all_cfg.items() if k.startswith(prefix)}


def updateConfigData(key: str, value: Any) -> None:
    """Set a config value for the active script."""
    all_cfg = _load_config_file()
    prefix = _script_prefix()
    all_cfg[f"{prefix}{key}"] = value
    _save_config_file(all_cfg)


def forwardEmbedMethod(
    *,
    content: str,
    title: str | None = None,
    image: str | None = None,
) -> str:
    """Format a rich embed-style reply (iMessage text; no Discord embeds)."""
    lines: list[str] = []
    if title:
        lines.extend(["━━━━━━━━━━━━━━━━━━━━", title, "━━━━━━━━━━━━━━━━━━━━", ""])
    lines.append(content)
    if image:
        lines.extend(["", str(image)])
    return "\n".join(lines).strip()


def log(message: str, type_: str = "INFO") -> None:
    """Log to stderr with a simple level tag."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sid = _current_script_id or "script"
    print(f"[{ts}] [{sid}] [{type_}] {message}", file=sys.stderr)


@dataclass
class IbotMessage:
    """Message wrapper for event listeners."""

    raw: IncomingMessage
    content: str
    is_from_me: bool
    handle_id: str | None
    chat_identifier: str | None

    @classmethod
    def from_incoming(cls, msg: IncomingMessage) -> IbotMessage:
        return cls(
            raw=msg,
            content=msg.body,
            is_from_me=msg.is_from_me,
            handle_id=msg.handle_id,
            chat_identifier=msg.chat_identifier,
        )


@dataclass
class CommandContext:
    """Context passed to @bot.command handlers."""

    message: IbotMessage
    script_id: str
    command: str
    args: str
    _outgoing: list[str] = field(default_factory=list)

    def send(self, content: str) -> None:
        if content:
            self._outgoing.append(content)

    def reply_embed(self, *, content: str, title: str | None = None, image: str | None = None) -> None:
        self.send(forwardEmbedMethod(content=content, title=title, image=image))

    @property
    def replies(self) -> list[str]:
        return list(self._outgoing)


@dataclass(frozen=True)
class CommandSpec:
    script_id: str
    name: str
    description: str
    usage: str
    handler: Callable[..., Any]
    aliases: tuple[str, ...]


@dataclass
class ScriptMeta:
    script_id: str
    name: str
    author: str
    description: str
    usage: str


class ScriptBot:
    """Per-script bot - register commands and listeners here."""

    def __init__(self, script_id: str) -> None:
        self.script_id = script_id
        self.commands: dict[str, CommandSpec] = {}
        self.listeners: dict[str, Callable[..., Any]] = {}
        self.meta: ScriptMeta | None = None

    def command(
        self,
        name: str,
        *,
        usage: str = "",
        description: str = "",
        aliases: list[str] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            spec = CommandSpec(
                script_id=self.script_id,
                name=name.lower(),
                description=description,
                usage=usage,
                handler=fn,
                aliases=tuple(a.lower() for a in (aliases or [])),
            )
            self.commands[spec.name] = spec
            for alias in spec.aliases:
                self.commands[alias] = spec
            return fn

        return decorator

    def listen(self, event: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.listeners[event] = fn
            return fn

        return decorator


def ibotScript(
    *,
    name: str,
    author: str = "Ibot",
    description: str = "",
    usage: str = "",
) -> Callable[[Callable[[], None]], Callable[[], None]]:
    """Decorator marking the script entry point."""

    def decorator(fn: Callable[[], None]) -> Callable[[], None]:
        fn.__ibot_script_meta__ = {  # type: ignore[attr-defined]
            "name": name,
            "author": author,
            "description": description,
            "usage": usage,
        }
        return fn

    return decorator


def set_script_context(script_id: str | None) -> None:
    global _current_script_id
    _current_script_id = script_id
