"""User-writable paths (Application Support) vs bundled app files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

APP_NAME = "Ibot"
DEFAULT_ENV = """# Ibot API keys (edit these values)
# Created automatically on first launch.

C99_WEATHER_KEY=
GLSERIES_TOKEN=
GLSERIES_BASE_URL=https://live.glseries.net/api/v1
API_NINJAS_KEY=
SERPAPI_KEY=
OSINT_INDUSTRIES_KEY=

# Poof.bg (!poof) - https://docs.poof.bg
POOF_API_KEY=
"""

FLX_APP_SUPPORT = Path.home() / "Library" / "Application Support" / "Flx"

# Copy from Flx config.env when Ibot's value is still empty.
SYNC_KEYS_FROM_FLX = (
    "POOF_API_KEY",
    "C99_WEATHER_KEY",
    "GLSERIES_TOKEN",
    "GLSERIES_BASE_URL",
    "API_NINJAS_KEY",
    "SERPAPI_KEY",
    "OSINT_INDUSTRIES_KEY",
)


def _parse_env_lines(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_empty(value: str | None) -> bool:
    return not (value or "").strip()


def sync_env_from_flx() -> bool:
    """Fill empty Ibot keys from ~/Library/Application Support/Flx/config.env."""
    flx_env = FLX_APP_SUPPORT / "config.env"
    ibot_env = env_file()
    if not flx_env.is_file() or not ibot_env.is_file():
        return False

    flx_vals = _parse_env_lines(flx_env)
    lines = ibot_env.read_text(encoding="utf-8").splitlines()
    changed = False
    seen: set[str] = set()
    out: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, sep, value = line.partition("=")
            key = key.strip()
            seen.add(key)
            if key in SYNC_KEYS_FROM_FLX and _env_empty(value) and not _env_empty(flx_vals.get(key)):
                out.append(f"{key}={flx_vals[key]}")
                changed = True
                continue
        out.append(line)

    for key in SYNC_KEYS_FROM_FLX:
        if key in seen:
            continue
        if not _env_empty(flx_vals.get(key)):
            out.append(f"{key}={flx_vals[key]}")
            changed = True

    if changed:
        ibot_env.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return changed


def project_root() -> Path:
    """Bundled or dev project root (read-only when installed from .app)."""
    return Path(__file__).resolve().parents[1]


def app_support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def ensure_app_support() -> Path:
    support = app_support_dir()
    support.mkdir(parents=True, exist_ok=True)
    return support


def env_file() -> Path:
    """Visible config file (Finder hides dotfiles like .env)."""
    return ensure_app_support() / "config.env"


def ensure_env_file() -> Path:
    """Create Application Support/config.env on first launch."""
    ensure_app_support()
    path = env_file()
    if path.exists():
        sync_env_from_flx()
        return path

    support = app_support_dir()
    hidden = support / ".env"
    example = project_root() / ".env.example"
    legacy = project_root() / ".env"

    if hidden.is_file():
        shutil.copy2(hidden, path)
    elif legacy.is_file() and legacy.resolve() != path.resolve():
        shutil.copy2(legacy, path)
    elif example.is_file():
        path.write_text(example.read_text())
    else:
        path.write_text(DEFAULT_ENV)

    sync_env_from_flx()
    return path


def state_file() -> Path:
    return ensure_app_support() / ".state.json"


def stats_file() -> Path:
    return ensure_app_support() / ".gui_stats.json"


def gui_settings_file() -> Path:
    return ensure_app_support() / ".gui_settings.json"


def hub_dir() -> Path:
    return ensure_app_support() / "scripts" / "hub"


def bundled_hub_dir() -> Path | None:
    root = project_root() / "scripts" / "hub"
    return root if root.is_dir() else None


def _hub_commands(entries: list[dict]) -> set[str]:
    names: set[str] = set()
    for entry in entries:
        cmd = str(entry.get("command") or "").strip().lower()
        if cmd:
            names.add(cmd)
        for c in entry.get("commands") or []:
            if c:
                names.add(str(c).strip().lower())
    return names


def _read_hub_manifest(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    scripts = data.get("scripts")
    return list(scripts) if isinstance(scripts, list) else []


def _write_hub_manifest(path: Path, scripts: list[dict]) -> None:
    path.write_text(json.dumps({"scripts": scripts}, indent=2) + "\n", encoding="utf-8")


def _copy_bundled_tree(bundled: Path, hub: Path) -> None:
    for item in bundled.iterdir():
        dest = hub / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


def _merge_bundled_scripts(hub: Path, bundled: Path) -> None:
    """Add bundled example scripts the user does not already have (by id or command)."""
    manifest = hub / "manifest.json"
    user_scripts = _read_hub_manifest(manifest)
    user_ids = {str(s.get("id")) for s in user_scripts if s.get("id")}
    user_commands = _hub_commands(user_scripts)

    bundled_scripts = _read_hub_manifest(bundled / "manifest.json")
    if not bundled_scripts:
        return

    added = False
    for entry in bundled_scripts:
        sid = str(entry.get("id") or "").strip()
        if not sid or sid in user_ids:
            continue
        cmds = _hub_commands([entry])
        if cmds & user_commands:
            continue
        src = bundled / f"{sid}.py"
        if not src.is_file():
            continue
        shutil.copy2(src, hub / f"{sid}.py")
        user_scripts.append(entry)
        user_ids.add(sid)
        user_commands |= cmds
        added = True

    if added or not manifest.is_file():
        _write_hub_manifest(manifest, user_scripts)


def ensure_script_hub() -> Path:
    """User script hub in Application Support; seed and merge bundled defaults."""
    hub = hub_dir()
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "json").mkdir(parents=True, exist_ok=True)
    manifest = hub / "manifest.json"
    bundled = bundled_hub_dir()

    if not manifest.is_file():
        if bundled:
            _copy_bundled_tree(bundled, hub)
        else:
            _write_hub_manifest(manifest, [])
    elif bundled:
        _merge_bundled_scripts(hub, bundled)

    return hub


def open_env_in_editor() -> bool:
    import subprocess

    path = ensure_env_file()
    try:
        subprocess.run(["open", "-e", str(path)], check=False)
        return True
    except OSError:
        return False
