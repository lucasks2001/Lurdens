"""Detecção e abertura do Spotify instalado (RPM, Flatpak ou Snap)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

FLATPAK_ID = "com.spotify.Client"


@dataclass(frozen=True)
class SpotifyInstall:
    kind: str          # "rpm" | "flatpak" | "snap" | "none"
    command: tuple[str, ...]
    label: str


def _flatpak_installed(home: Path) -> bool:
    candidates = [
        home / ".local/share/flatpak/app" / FLATPAK_ID,
        Path("/var/lib/flatpak/app") / FLATPAK_ID,
    ]
    return any(p.exists() for p in candidates)


def detect_spotify(home: Path | None = None, which=shutil.which) -> SpotifyInstall:
    home = home or Path.home()
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
    return SpotifyInstall("none", (), "Spotify não encontrado")


def launch(install: SpotifyInstall) -> bool:
    if not install.command:
        return False
    try:
        subprocess.Popen(list(install.command), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, env=os.environ.copy())
        return True
    except OSError:
        return False
