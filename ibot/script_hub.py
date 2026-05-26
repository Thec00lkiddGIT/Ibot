"""Load, save, and run Script Hub scripts (IbotScript / legacy run())."""

from __future__ import annotations

import importlib.util
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ibot.db import IncomingMessage
from ibot.gui.commands_list import COMMANDS
from ibot.ibotscript import (
    CommandContext,
    IbotMessage,
    ScriptBot,
    ScriptMeta,
    forwardEmbedMethod,
    getConfigData,
    getScriptsPath,
    ibotScript,
    log,
    set_script_context,
    updateConfigData,
)

from ibot.paths import ensure_script_hub

COMMAND_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
BUILTIN_NAMES = frozenset(name for name, _ in COMMANDS)


def _hub() -> Path:
    return ensure_script_hub()


def _manifest() -> Path:
    return _hub() / "manifest.json"

SCRIPT_TEMPLATE = '''"""IbotScript hub script for iMessage."""

from ibot.ibotscript import (
    forwardEmbedMethod,
    getConfigData,
    getScriptsPath,
    ibotScript,
    log,
    updateConfigData,
)


@ibotScript(
    name="{name}",
    author="{author}",
    description="{description}",
    usage="{usage}",
)
def {entry_fn}():
    """
    {name}
    ----------

    {description}

    COMMANDS:
    !{command} <args> - {description}

    EXAMPLES:
    !{command} hello - Example usage
    """

    @bot.command(name="{command}", description="{description}")
    def {command}_handler(ctx, *, args: str):
        if not args:
            ctx.send("Usage: !{command} <text>")
            return
        ctx.send(f"You said: {{args}}")
        log("Handled !{command}", type_="INFO")


{entry_fn}()  # IMPORTANT: call to register commands
'''

_registry_mtime: float = 0.0
_registry_bots: dict[str, ScriptBot] = {}
_registry_commands: dict[str, tuple[str, ScriptBot]] = {}  # cmd -> (script_id, bot)
_registry_meta: dict[str, ScriptMeta] = {}


@dataclass
class HubScript:
    id: str
    name: str
    author: str
    description: str
    usage: str
    command: str
    help: str
    commands: list[str] = field(default_factory=list)
    enabled: bool = True
    created: str = ""
    updated: str = ""
    format: str = "ibotscript"

    def to_dict(self) -> dict:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ensure_hub() -> None:
    hub = _hub()
    (hub / "json").mkdir(parents=True, exist_ok=True)
    manifest = _manifest()
    if not manifest.exists():
        manifest.write_text(json.dumps({"scripts": []}, indent=2) + "\n")


def _load_manifest() -> list[dict]:
    _ensure_hub()
    manifest = _manifest()
    try:
        data = json.loads(manifest.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, list) else []


def _save_manifest(scripts: list[dict]) -> None:
    _ensure_hub()
    _manifest().write_text(json.dumps({"scripts": scripts}, indent=2) + "\n")


def _script_path(script_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", script_id)
    return _hub() / f"{safe}.py"


def _manifest_mtime() -> float:
    manifest = _manifest()
    if not manifest.exists():
        return 0.0
    mt = manifest.stat().st_mtime
    for entry in _load_manifest():
        sid = str(entry.get("id", ""))
        p = _script_path(sid)
        if p.is_file():
            mt = max(mt, p.stat().st_mtime)
    return mt


def _entry_fn_name(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower()) or "script"
    if base[0].isdigit():
        base = f"script_{base}"
    return base


def _hub_script_from_raw(raw: dict) -> HubScript | None:
    try:
        commands = raw.get("commands")
        if not isinstance(commands, list):
            commands = [str(raw.get("command", ""))]
        cmd = str(raw.get("command") or (commands[0] if commands else ""))
        desc = str(raw.get("description") or raw.get("help") or "")
        return HubScript(
            id=str(raw["id"]),
            name=str(raw.get("name") or cmd),
            author=str(raw.get("author") or "Ibot"),
            description=desc,
            usage=str(raw.get("usage") or f"!{cmd}"),
            command=cmd,
            help=desc or str(raw.get("help", "")),
            commands=[str(c) for c in commands if c],
            enabled=bool(raw.get("enabled", True)),
            created=str(raw.get("created", "")),
            updated=str(raw.get("updated", "")),
            format=str(raw.get("format") or "ibotscript"),
        )
    except (KeyError, TypeError):
        return None


def _inject_module(script_id: str, path: Path) -> tuple[Any, ScriptBot]:
    bot = ScriptBot(script_id)
    module_name = f"ibot_hub_{script_id}_{path.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load script module")

    module = importlib.util.module_from_spec(spec)
    module.__dict__.update(
        {
            "bot": bot,
            "ibotScript": ibotScript,
            "getConfigData": getConfigData,
            "updateConfigData": updateConfigData,
            "getScriptsPath": getScriptsPath,
            "forwardEmbedMethod": forwardEmbedMethod,
            "log": log,
        }
    )
    set_script_context(script_id)
    try:
        spec.loader.exec_module(module)
    finally:
        set_script_context(None)

    if bot.meta is None:
        for attr in dir(module):
            obj = getattr(module, attr)
            meta = getattr(obj, "__ibot_script_meta__", None)
            if meta and callable(obj):
                bot.meta = ScriptMeta(
                    script_id=script_id,
                    name=str(meta.get("name", script_id)),
                    author=str(meta.get("author", "Ibot")),
                    description=str(meta.get("description", "")),
                    usage=str(meta.get("usage", "")),
                )
                break

    return module, bot


def reload_registry() -> None:
    global _registry_mtime, _registry_bots, _registry_commands, _registry_meta
    _registry_bots = {}
    _registry_commands = {}
    _registry_meta = {}

    for raw in _load_manifest():
        script = _hub_script_from_raw(raw)
        if script is None or not script.enabled:
            continue
        path = _script_path(script.id)
        if not path.is_file():
            continue
        try:
            _, bot = _inject_module(script.id, path)
        except Exception:
            continue
        _registry_bots[script.id] = bot
        if bot.meta:
            _registry_meta[script.id] = bot.meta
        for spec in bot.commands.values():
            if spec.script_id != script.id:
                continue
            _registry_commands[spec.name] = (script.id, bot)
            for alias in spec.aliases:
                _registry_commands[alias] = (script.id, bot)

    _registry_mtime = _manifest_mtime()


def ensure_registry() -> None:
    if _manifest_mtime() != _registry_mtime:
        reload_registry()


def hub_command_specs() -> list[dict]:
    ensure_registry()
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for bot in _registry_bots.values():
        for spec in bot.commands.values():
            key = (spec.script_id, spec.name)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "name": spec.name,
                    "help": spec.description or spec.usage,
                    "script_id": spec.script_id,
                    "aliases": list(spec.aliases),
                }
            )
    out.sort(key=lambda x: x["name"])
    return out


def validate_command_name(command: str, *, exclude_id: str | None = None) -> str | None:
    name = command.strip().lower()
    if not COMMAND_RE.match(name):
        return "Command must be 2-32 chars: lowercase letters, digits, underscore; start with a letter."
    if name in BUILTIN_NAMES:
        return f"!{name} is already a built-in command."
    for entry in _load_manifest():
        if entry.get("id") == exclude_id:
            continue
        cmds = entry.get("commands") or [entry.get("command")]
        if name in {str(c).lower() for c in cmds if c}:
            return f"!{name} is already used by another hub script."
    return None


def _extract_commands_from_code(code: str, script_id: str | None) -> tuple[list[str], str | None]:
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(code)
            tmp_path = Path(tmp.name)
        sid = script_id or "_validate"
        _, bot = _inject_module(sid, tmp_path)
        tmp_path.unlink(missing_ok=True)
    except Exception as exc:
        return [], str(exc)
    names = sorted({s.name for s in bot.commands.values() if s.script_id == sid})
    if names:
        return names, None
    if "def run(" in code:
        return [], None
    return [], "Script must use @ibotScript + @bot.command, or legacy run(args)."


def validate_code(code: str, *, script_id: str | None = None) -> str | None:
    if not code.strip():
        return "Script code cannot be empty."
    try:
        compile(code, "<script>", "exec")
    except SyntaxError as exc:
        return f"Syntax error: {exc.msg} (line {exc.lineno})"
    _, err = _extract_commands_from_code(code, script_id)
    return err


def list_scripts(*, include_disabled: bool = True) -> list[HubScript]:
    scripts: list[HubScript] = []
    for raw in _load_manifest():
        script = _hub_script_from_raw(raw)
        if script is None:
            continue
        if include_disabled or script.enabled:
            scripts.append(script)
    scripts.sort(key=lambda s: s.name.lower())
    return scripts


def get_script_by_command(command: str) -> HubScript | None:
    ensure_registry()
    name = command.strip().lower()
    hit = _registry_commands.get(name)
    if not hit:
        return None
    script_id, _ = hit
    for script in list_scripts():
        if script.id == script_id and script.enabled:
            return script
    return None


def read_script_code(script_id: str) -> str:
    path = _script_path(script_id)
    if path.is_file():
        return path.read_text()
    return ""


def new_script_template(
    *,
    name: str = "My Script",
    author: str = "Ibot",
    command: str = "mycommand",
    description: str = "My custom command",
) -> dict:
    cmd = command.strip().lower() or "mycommand"
    entry = _entry_fn_name(name)
    usage = f"!{cmd} <args>"
    return {
        "id": "",
        "name": name,
        "author": author,
        "description": description,
        "usage": usage,
        "command": cmd,
        "help": description,
        "commands": [cmd],
        "enabled": True,
        "format": "ibotscript",
        "code": SCRIPT_TEMPLATE.format(
            name=name,
            author=author,
            description=description.replace('"', '\\"'),
            usage=usage,
            command=cmd,
            entry_fn=entry,
        ),
    }


def save_script(
    *,
    script_id: str | None,
    name: str,
    author: str,
    description: str,
    usage: str,
    command: str,
    help_text: str,
    code: str,
    enabled: bool = True,
) -> tuple[HubScript | None, str | None]:
    sid = script_id or uuid.uuid4().hex[:12]
    err = validate_code(code, script_id=sid)
    if err:
        return None, err

    commands, load_err = _extract_commands_from_code(code, sid)
    if load_err:
        return None, load_err

    primary = command.strip().lower() or (commands[0] if commands else "")
    if not commands and primary:
        err = validate_command_name(primary, exclude_id=sid)
        if err:
            return None, err
        commands = [primary]
    elif commands:
        for cmd in commands:
            err = validate_command_name(cmd, exclude_id=sid)
            if err and cmd != primary:
                return None, err
            if err and not script_id:
                return None, err
    else:
        return None, "No commands found. Add @bot.command or a legacy run(args) function."

    if primary and primary not in commands:
        primary = commands[0]

    manifest = _load_manifest()
    now = _now_iso()
    entry = next((e for e in manifest if e.get("id") == sid), None)
    if entry is None:
        entry = {"id": sid, "created": now, "format": "ibotscript"}
        manifest.append(entry)

    entry["name"] = name.strip() or primary
    entry["author"] = author.strip() or "Ibot"
    entry["description"] = description.strip() or help_text.strip()
    entry["usage"] = usage.strip() or f"!{primary}"
    entry["command"] = primary
    entry["help"] = help_text.strip() or entry["description"]
    entry["commands"] = commands
    entry["enabled"] = bool(enabled)
    entry["updated"] = now

    _script_path(sid).write_text(code if code.endswith("\n") else code + "\n")
    _save_manifest(manifest)
    reload_registry()

    script = _hub_script_from_raw(entry)
    return script, None


def delete_script(script_id: str) -> bool:
    manifest = _load_manifest()
    new_manifest = [s for s in manifest if s.get("id") != script_id]
    if len(new_manifest) == len(manifest):
        return False
    _script_path(script_id).unlink(missing_ok=True)
    _save_manifest(new_manifest)
    reload_registry()
    return True


def set_script_enabled(script_id: str, enabled: bool) -> HubScript | None:
    manifest = _load_manifest()
    for entry in manifest:
        if entry.get("id") == script_id:
            entry["enabled"] = bool(enabled)
            entry["updated"] = _now_iso()
            _save_manifest(manifest)
            reload_registry()
            return _hub_script_from_raw(entry)
    return None


def _run_legacy(script_id: str, args: str) -> str | list[str]:
    path = _script_path(script_id)
    module, _ = _inject_module(script_id, path)
    run_fn = getattr(module, "run", None)
    if not callable(run_fn):
        raise RuntimeError("Legacy script must define run(args)")
    set_script_context(script_id)
    try:
        result = run_fn(args)
    finally:
        set_script_context(None)
    if isinstance(result, str):
        return result
    if isinstance(result, list) and all(isinstance(x, str) for x in result):
        return result
    raise RuntimeError("run(args) must return str or list[str]")


def dispatch_hub_command(
    command: str,
    args: str,
    message: IncomingMessage,
) -> str | list[str] | None:
    ensure_registry()
    name = command.strip().lower()
    hit = _registry_commands.get(name)
    if hit:
        script_id, bot = hit
        spec = bot.commands.get(name)
        if spec is None:
            return None
        ctx = CommandContext(
            message=IbotMessage.from_incoming(message),
            script_id=script_id,
            command=spec.name,
            args=args,
        )
        set_script_context(script_id)
        try:
            spec.handler(ctx, args=args)
        finally:
            set_script_context(None)
        if ctx.replies:
            return ctx.replies if len(ctx.replies) > 1 else ctx.replies[0]
        return None

    script = get_script_by_command(name)
    if script is None:
        for s in list_scripts():
            if s.command.lower() == name and s.enabled:
                script = s
                break
    if script is None:
        return None

    path = _script_path(script.id)
    if not path.is_file():
        return None
    try:
        _, bot = _inject_module(script.id, path)
    except Exception:
        bot = None
    if bot and bot.commands:
        return dispatch_hub_command(command, args, message)
    return _run_legacy(script.id, args)


def dispatch_message_listeners(message: IncomingMessage) -> list[str]:
    ensure_registry()
    imsg = IbotMessage.from_incoming(message)
    outgoing: list[str] = []

    for script_id, bot in _registry_bots.items():
        handler = bot.listeners.get("on_message")
        if not handler:
            continue
        set_script_context(script_id)
        try:
            result = handler(imsg)
            if isinstance(result, str) and result:
                outgoing.append(result)
            elif isinstance(result, list):
                outgoing.extend(str(x) for x in result if x)
        except Exception as exc:
            log(f"Listener error: {exc}", type_="ERROR")
        finally:
            set_script_context(None)

    return outgoing


def test_script_code(code: str, command: str, args: str) -> str | list[str]:
    import tempfile

    err = validate_code(code, script_id="_test")
    if err:
        raise ValueError(err)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = Path(tmp.name)
    try:
        module, bot = _inject_module("_test", tmp_path)
        cmd = command.strip().lower()
        if not cmd and bot.commands:
            cmd = next(iter({s.name for s in bot.commands.values()}))
        if cmd and cmd in bot.commands:
            spec = bot.commands[cmd]
            ctx = CommandContext(
                message=IbotMessage.from_incoming(
                    IncomingMessage(
                        rowid=0,
                        body=f"!{cmd} {args}".strip(),
                        is_from_me=True,
                        handle_id=None,
                        chat_guid=None,
                        chat_identifier="test",
                    )
                ),
                script_id="_test",
                command=spec.name,
                args=args,
            )
            set_script_context("_test")
            try:
                spec.handler(ctx, args=args)
            finally:
                set_script_context(None)
            if ctx.replies:
                return ctx.replies if len(ctx.replies) > 1 else ctx.replies[0]
            raise RuntimeError("Command produced no output")
        run_fn = getattr(module, "run", None)
        if callable(run_fn):
            set_script_context("_test")
            try:
                result = run_fn(args)
            finally:
                set_script_context(None)
            if isinstance(result, str):
                return result
            if isinstance(result, list):
                return result
        raise RuntimeError("No command handler matched")
    finally:
        tmp_path.unlink(missing_ok=True)


def run_script(script_id: str, args: str) -> str | list[str]:
    ensure_registry()
    path = _script_path(script_id)
    if not path.is_file():
        raise FileNotFoundError("Script file missing")

    script = next((s for s in list_scripts() if s.id == script_id), None)
    cmd = script.command if script else ""
    if cmd:
        fake = IncomingMessage(
            rowid=0,
            body=f"!{cmd} {args}".strip(),
            is_from_me=True,
            handle_id=None,
            chat_guid=None,
            chat_identifier="test",
        )
        result = dispatch_hub_command(cmd, args, fake)
        if result is not None:
            return result
    return _run_legacy(script_id, args)
