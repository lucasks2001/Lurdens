"""Inicialização automática com a sessão (XDG autostart, usado pelo KDE Plasma).

A fonte da verdade é o próprio arquivo ~/.config/autostart/lurdens.desktop:
se o usuário remover a entrada em Configurações do Sistema › Inicialização
automática, o Lurdens enxerga a mudança.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path

FILE_NAME = "lurdens.desktop"


def autostart_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return Path(base) / "autostart"


def launcher_command() -> str:
    """Comando que inicia esta instalação do Lurdens."""
    launcher = os.environ.get("LURDENS_LAUNCHER")
    if launcher and os.path.isfile(launcher):
        return shlex.quote(launcher)
    found = shutil.which("lurdens")
    if found:
        return shlex.quote(found)
    pkg_parent = str(Path(__file__).resolve().parent.parent)
    return (f"env PYTHONPATH={shlex.quote(pkg_parent)} "
            f"{shlex.quote(sys.executable)} -m lurdens")


def is_enabled(directory: Path | None = None) -> bool:
    path = (directory or autostart_dir()) / FILE_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key.strip() in ("Hidden", "X-KDE-Autostart-Disabled") and value.strip().lower() == "true":
            return False
        if key.strip() == "X-GNOME-Autostart-enabled" and value.strip().lower() == "false":
            return False
    return True


def enable(directory: Path | None = None, command: str | None = None) -> Path:
    d = directory or autostart_dir()
    d.mkdir(parents=True, exist_ok=True)
    cmd = command or launcher_command()
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Lurdens\n"
        "Comment=Player complementar para o Spotify (inicia na bandeja)\n"
        f"Exec={cmd} --autostart\n"
        "Icon=lurdens\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "X-KDE-autostart-phase=2\n"
    )
    path = d / FILE_NAME
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
    return path


def disable(directory: Path | None = None) -> None:
    try:
        ((directory or autostart_dir()) / FILE_NAME).unlink()
    except FileNotFoundError:
        pass
