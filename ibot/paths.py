"""User-writable paths (Application Support) vs bundled app files."""

from __future__ import annotations

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
"""


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

    return path


def state_file() -> Path:
    return ensure_app_support() / ".state.json"


def stats_file() -> Path:
    return ensure_app_support() / ".gui_stats.json"


def gui_settings_file() -> Path:
    return ensure_app_support() / ".gui_settings.json"


def hub_dir() -> Path:
    return ensure_app_support() / "scripts" / "hub"


def ensure_script_hub() -> Path:
    """User script hub in Application Support; seed from bundle once."""
    hub = hub_dir()
    hub.mkdir(parents=True, exist_ok=True)
    manifest = hub / "manifest.json"
    if manifest.is_file():
        return hub

    bundled = project_root() / "scripts" / "hub"
    if bundled.is_dir():
        for item in bundled.iterdir():
            dest = hub / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
    else:
        manifest.write_text('{"scripts": []}\n')
    return hub


def open_env_in_editor() -> bool:
    import subprocess

    path = ensure_env_file()
    try:
        subprocess.run(["open", "-e", str(path)], check=False)
        return True
    except OSError:
        return False
