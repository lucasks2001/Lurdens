"""Pastas do Lurdens em cada sistema.

| Pasta    | Linux (XDG)                 | Windows                           | macOS                                   |
|----------|-----------------------------|-----------------------------------|-----------------------------------------|
| config   | ~/.config/lurdens           | %APPDATA%\\Lurdens                 | ~/Library/Application Support/Lurdens   |
| estado   | ~/.local/state/lurdens      | %LOCALAPPDATA%\\Lurdens\\state      | ~/Library/Application Support/Lurdens/state |
| cache    | ~/.cache/lurdens            | %LOCALAPPDATA%\\Lurdens\\cache      | ~/Library/Caches/Lurdens                |

As variáveis XDG_CONFIG_HOME, XDG_STATE_HOME e XDG_CACHE_HOME têm prioridade
em qualquer sistema quando definidas — é assim que o autoteste e os testes
isolam seus arquivos.
"""

from __future__ import annotations

import os
from pathlib import Path

from .backends import current_os

APP_DIR = "lurdens"        # Linux: minúsculas, como as demais pastas XDG
APP_NAME = "Lurdens"       # Windows/macOS: nome do aplicativo


def _home() -> Path:
    return Path.home()


def _env_path(var: str) -> Path | None:
    value = os.environ.get(var)
    return Path(value) if value else None


def config_dir(os_name: str | None = None) -> Path:
    xdg = _env_path("XDG_CONFIG_HOME")
    if xdg:
        return xdg / APP_DIR
    os_name = os_name or current_os()
    if os_name == "windows":
        return Path(os.environ.get("APPDATA") or _home() / "AppData" / "Roaming") / APP_NAME
    if os_name == "macos":
        return _home() / "Library" / "Application Support" / APP_NAME
    return _home() / ".config" / APP_DIR


def state_dir(os_name: str | None = None) -> Path:
    xdg = _env_path("XDG_STATE_HOME")
    if xdg:
        return xdg / APP_DIR
    os_name = os_name or current_os()
    if os_name == "windows":
        return _local_appdata() / APP_NAME / "state"
    if os_name == "macos":
        return _home() / "Library" / "Application Support" / APP_NAME / "state"
    return _home() / ".local" / "state" / APP_DIR


def cache_dir(os_name: str | None = None) -> Path:
    xdg = _env_path("XDG_CACHE_HOME")
    if xdg:
        return xdg / APP_DIR
    os_name = os_name or current_os()
    if os_name == "windows":
        return _local_appdata() / APP_NAME / "cache"
    if os_name == "macos":
        return _home() / "Library" / "Caches" / APP_NAME
    return _home() / ".cache" / APP_DIR


def _local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or _home() / "AppData" / "Local")
