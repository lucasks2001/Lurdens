"""Inicialização automática com a sessão do usuário, em cada sistema.

- Linux: XDG autostart (``~/.config/autostart/lurdens.desktop``), usado pelo
  KDE Plasma e pelos demais ambientes. A fonte da verdade é o próprio
  arquivo: se o usuário remover a entrada em Configurações do Sistema ›
  Inicialização automática, o Lurdens enxerga a mudança.
- Windows: valor "Lurdens" em ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``
  (aparece em Gerenciador de Tarefas › Aplicativos de inicialização).
- macOS: LaunchAgent em ``~/Library/LaunchAgents/io.github.lucasks2001.lurdens.plist``
  (aparece em Ajustes do Sistema › Geral › Itens de Início).

Em todos, o Lurdens é iniciado com ``--autostart``: abre na bandeja e não
abre uma segunda cópia.
"""

from __future__ import annotations

import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .backends import current_os

FILE_NAME = "lurdens.desktop"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "Lurdens"
AGENT_LABEL = "io.github.lucasks2001.lurdens"

PKG_PARENT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------ comando de início
def launcher_argv() -> list[str]:
    """Argumentos que iniciam esta instalação do Lurdens."""
    launcher = os.environ.get("LURDENS_LAUNCHER")
    if launcher and os.path.isfile(launcher):
        return [launcher]
    if getattr(sys, "frozen", False):          # executável empacotado (PyInstaller)
        return [sys.executable]
    found = shutil.which("lurdens")
    if found:
        return [found]
    python = sys.executable
    if current_os() == "windows":
        pythonw = Path(python).with_name("pythonw.exe")   # sem janela de console
        if pythonw.exists():
            python = str(pythonw)
    code = (f"import sys; sys.path.insert(0, {str(PKG_PARENT)!r}); "
            "from lurdens.__main__ import run; sys.exit(run())")
    return [python, "-c", code]


def launcher_command() -> str:
    """Linha de comando (shell POSIX) para o Exec= do arquivo .desktop."""
    launcher = os.environ.get("LURDENS_LAUNCHER")
    if launcher and os.path.isfile(launcher):
        return shlex.quote(launcher)
    found = shutil.which("lurdens")
    if found:
        return shlex.quote(found)
    return (f"env PYTHONPATH={shlex.quote(str(PKG_PARENT))} "
            f"{shlex.quote(sys.executable)} -m lurdens")


# ------------------------------------------------------------------ Linux (XDG)
def autostart_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return Path(base) / "autostart"


def _xdg_is_enabled(directory: Path | None = None) -> bool:
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


def _xdg_enable(directory: Path | None = None, command: str | None = None) -> Path:
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


def _xdg_disable(directory: Path | None = None) -> None:
    try:
        ((directory or autostart_dir()) / FILE_NAME).unlink()
    except FileNotFoundError:
        pass


# --------------------------------------------------------------------- Windows
def _winreg(reg=None):
    if reg is not None:
        return reg
    import winreg
    return winreg


def _win_is_enabled(reg=None) -> bool:
    reg = _winreg(reg)
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_READ)
    except OSError:
        return False
    try:
        value, _type = reg.QueryValueEx(key, RUN_VALUE)
        return bool(value)
    except OSError:
        return False
    finally:
        reg.CloseKey(key)


def _win_enable(reg=None, argv: list[str] | None = None) -> str:
    reg = _winreg(reg)
    command = subprocess.list2cmdline((argv or launcher_argv()) + ["--autostart"])
    key = reg.CreateKeyEx(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE)
    try:
        reg.SetValueEx(key, RUN_VALUE, 0, reg.REG_SZ, command)
    finally:
        reg.CloseKey(key)
    return command


def _win_disable(reg=None) -> None:
    reg = _winreg(reg)
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE)
    except OSError:
        return
    try:
        reg.DeleteValue(key, RUN_VALUE)
    except OSError:
        pass
    finally:
        reg.CloseKey(key)


# ----------------------------------------------------------------------- macOS
def launch_agent_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / "Library" / "LaunchAgents" / f"{AGENT_LABEL}.plist"


def _mac_is_enabled(home: Path | None = None) -> bool:
    try:
        with open(launch_agent_path(home), "rb") as fh:
            data = plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return False
    return bool(data.get("RunAtLoad")) and not data.get("Disabled", False)


def _mac_enable(home: Path | None = None, argv: list[str] | None = None) -> Path:
    path = launch_agent_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "Label": AGENT_LABEL,
        "ProgramArguments": (argv or launcher_argv()) + ["--autostart"],
        "RunAtLoad": True,
        "ProcessType": "Interactive",
    }
    tmp = path.with_suffix(".tmp")
    with open(tmp, "wb") as fh:
        plistlib.dump(data, fh)
    os.replace(tmp, path)
    return path


def _mac_disable(home: Path | None = None) -> None:
    try:
        launch_agent_path(home).unlink()
    except FileNotFoundError:
        pass


# ----------------------------------------------------------------- API pública
def is_enabled(directory: Path | None = None, os_name: str | None = None) -> bool:
    os_name = os_name or current_os()
    if os_name == "windows":
        return _win_is_enabled()
    if os_name == "macos":
        return _mac_is_enabled()
    return _xdg_is_enabled(directory)


def enable(directory: Path | None = None, command: str | None = None, os_name: str | None = None):
    os_name = os_name or current_os()
    if os_name == "windows":
        return _win_enable()
    if os_name == "macos":
        return _mac_enable()
    return _xdg_enable(directory, command)


def disable(directory: Path | None = None, os_name: str | None = None) -> None:
    os_name = os_name or current_os()
    if os_name == "windows":
        _win_disable()
    elif os_name == "macos":
        _mac_disable()
    else:
        _xdg_disable(directory)


def location(os_name: str | None = None) -> str:
    """Onde a entrada fica, para mostrar nas configurações."""
    os_name = os_name or current_os()
    if os_name == "windows":
        return rf"HKEY_CURRENT_USER\{RUN_KEY}\{RUN_VALUE}"
    if os_name == "macos":
        return str(launch_agent_path())
    return str(autostart_dir() / FILE_NAME)
