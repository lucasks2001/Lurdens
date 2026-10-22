"""Detecção e abertura do Spotify instalado, em cada sistema.

- Linux: binário nativo (RPM), Flatpak ``com.spotify.Client`` ou Snap;
- Windows: instalador do site (``%APPDATA%\\Spotify\\Spotify.exe``) ou
  Microsoft Store (atalho de execução em ``%LOCALAPPDATA%\\Microsoft\\WindowsApps``);
- macOS: ``Spotify.app`` em /Applications, ~/Applications ou pelo Spotlight.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .backends import current_os

FLATPAK_ID = "com.spotify.Client"


@dataclass(frozen=True)
class SpotifyInstall:
    kind: str          # "rpm" | "flatpak" | "snap" | "windows" | "store" | "macos" | "none"
    command: tuple[str, ...]
    label: str


NOT_FOUND = SpotifyInstall("none", (), "Spotify não encontrado")


# ------------------------------------------------------------------- Linux
def _flatpak_installed(home: Path) -> bool:
    candidates = [
        home / ".local/share/flatpak/app" / FLATPAK_ID,
        Path("/var/lib/flatpak/app") / FLATPAK_ID,
    ]
    return any(p.exists() for p in candidates)


def _detect_linux(home: Path, which) -> SpotifyInstall:
    native = which("spotify")
    # O Flatpak exporta um script "spotify" em .../flatpak/exports/bin quando o PATH inclui essa pasta.
    if native and "flatpak/exports" not in native and "/snap/" not in native:
        return SpotifyInstall("rpm", (native,), "Spotify nativo (RPM)")
    if _flatpak_installed(home) and which("flatpak"):
        return SpotifyInstall("flatpak", ("flatpak", "run", FLATPAK_ID), "Spotify Flatpak")
    if which("snap") and Path("/snap/bin/spotify").exists():
        return SpotifyInstall("snap", ("snap", "run", "spotify"), "Spotify Snap")
    if native:
        return SpotifyInstall("rpm", (native,), "Spotify")
    return NOT_FOUND


# ----------------------------------------------------------------- Windows
def _detect_windows(home: Path, env) -> SpotifyInstall:
    appdata = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
    exe = appdata / "Spotify" / "Spotify.exe"
    if exe.exists():
        return SpotifyInstall("windows", (str(exe),), "Spotify para Windows")
    local = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
    alias = local / "Microsoft" / "WindowsApps" / "Spotify.exe"
    if alias.exists():
        return SpotifyInstall("store", (str(alias),), "Spotify (Microsoft Store)")
    return NOT_FOUND


# ------------------------------------------------------------------- macOS
def _detect_macos(home: Path, finder) -> SpotifyInstall:
    app = finder(home)
    if app:
        return SpotifyInstall("macos", ("open", "-a", app), "Spotify para macOS")
    return NOT_FOUND


def _find_mac_app(home: Path) -> str:
    from .backends.applescript import find_spotify_app
    return find_spotify_app(home)


# --------------------------------------------------------------------- API
def detect_spotify(home: Path | None = None, which=shutil.which, *, os_name: str | None = None,
                   env=None, mac_finder=_find_mac_app) -> SpotifyInstall:
    home = home or Path.home()
    os_name = os_name or current_os()
    if os_name == "windows":
        return _detect_windows(home, os.environ if env is None else env)
    if os_name == "macos":
        return _detect_macos(home, mac_finder)
    return _detect_linux(home, which)


def launch(install: SpotifyInstall) -> bool:
    if not install.command:
        return False
    kw: dict = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=os.environ.copy())
    if os.name == "nt":
        kw["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0)
                               | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen(list(install.command), **kw)
        return True
    except OSError:
        return False
