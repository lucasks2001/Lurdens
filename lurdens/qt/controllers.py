"""Objetos expostos ao QML: PlayerController (Spotify) e AppController (app)."""

from __future__ import annotations

import os
import platform
import sys
import time

from PySide6.QtCore import (Property, QObject, QStandardPaths, Qt, QTimer, Signal, Slot)
from PySide6.QtGui import QGuiApplication, QPalette

from .. import __version__
from ..changelog import CHANGELOG
from ..backends import create_backend, current_os
from ..launcher import detect_spotify, launch
from ..settings import SettingsStore
from ..state import PlayerState, format_time


def _system_description() -> str:
    os_name = current_os()
    if os_name == "windows":
        return f"Windows {platform.release()} ({platform.version()})"
    if os_name == "macos":
        return f"macOS {platform.mac_ver()[0] or '?'} ({platform.machine()})"
    return (f"{os.environ.get('XDG_SESSION_TYPE', '?')} / {os.environ.get('XDG_CURRENT_DESKTOP', '?')}"
            f" ({platform.machine()})")


class PlayerController(QObject):
    changed = Signal()
    _incoming = Signal(object)

    def __init__(self, parent=None, address: str | None = None):
        super().__init__(parent)
        self._state = PlayerState()
        self._install = detect_spotify()
        self._launch_pending_until = 0.0
        self._incoming.connect(self._apply, Qt.ConnectionType.QueuedConnection)
        self._client = create_backend(self._incoming.emit, address=address)
        # O volume chega em rajadas durante o arraste; agrupa em ~12 envios/s.
        self._volume_target: float | None = None
        self._volume_timer = QTimer(self, interval=80, singleShot=True)
        self._volume_timer.timeout.connect(self._flush_volume)

    def start(self):
        self._client.start()

    def stop(self):
        self._client.stop()

    @Slot(object)
    def _apply(self, state: PlayerState):
        if state.connected:
            self._launch_pending_until = 0.0
        self._state = state
        self.changed.emit()

    @property
    def state(self) -> PlayerState:
        return self._state

    # ------------------------------------------------------------ propriedades
    def _s(attr):  # noqa: N805 - fábrica usada só no corpo da classe
        return lambda self: getattr(self._state, attr)

    busAvailable = Property(bool, _s("bus_available"), notify=changed)
    connected = Property(bool, _s("connected"), notify=changed)
    title = Property(str, _s("title"), notify=changed)
    album = Property(str, _s("album"), notify=changed)
    artUrl = Property(str, _s("art_url"), notify=changed)
    status = Property(str, _s("status"), notify=changed)
    identity = Property(str, _s("identity"), notify=changed)
    busName = Property(str, _s("bus_name"), notify=changed)
    trackId = Property(str, _s("track_id"), notify=changed)
    canRaise = Property(bool, _s("can_raise"), notify=changed)
    hasTrack = Property(bool, lambda self: self._state.has_track, notify=changed)
    playing = Property(bool, lambda self: self._state.playing, notify=changed)
    artist = Property(str, lambda self: ", ".join(self._state.artists), notify=changed)
    lengthMs = Property(int, lambda self: int(self._state.length_us // 1000), notify=changed)
    canPlayPause = Property(bool, lambda self: self._state.connected and (self._state.can_play or self._state.can_pause), notify=changed)
    canNext = Property(bool, lambda self: self._state.connected and self._state.can_next, notify=changed)
    canPrevious = Property(bool, lambda self: self._state.connected and self._state.can_prev, notify=changed)
    canSeek = Property(bool, lambda self: self._state.has_track and self._state.can_seek and self._state.length_us > 0, notify=changed)
    hasVolume = Property(bool, lambda self: self._state.connected and self._state.volume is not None, notify=changed)
    volume = Property(float, lambda self: float(self._state.volume or 0.0), notify=changed)
    hasShuffle = Property(bool, lambda self: self._state.connected and self._state.shuffle is not None, notify=changed)
    shuffle = Property(bool, lambda self: bool(self._state.shuffle), notify=changed)
    hasLoop = Property(bool, lambda self: self._state.connected and self._state.loop_status is not None, notify=changed)
    loopStatus = Property(str, lambda self: self._state.loop_status or "None", notify=changed)
    spotifyInstalled = Property(bool, lambda self: self._install.kind != "none", notify=changed)
    spotifyKind = Property(str, lambda self: self._install.kind, notify=changed)
    spotifyLabel = Property(str, lambda self: self._install.label, notify=changed)
    lastError = Property(str, lambda self: self._client.last_error, notify=changed)
    launching = Property(bool, lambda self: time.monotonic() < self._launch_pending_until, notify=changed)
    backendKind = Property(str, lambda self: self._client.kind, constant=True)
    backendLabel = Property(str, lambda self: self._client.label, constant=True)
    del _s

    # ---------------------------------------------------------------- comandos
    @Slot(result=int)
    def positionMs(self) -> int:
        return int(self._state.position_at() // 1000)

    @Slot(int, result=str)
    def formatTime(self, ms: int) -> str:
        return format_time(int(ms) * 1000)

    @Slot()
    def playPause(self):
        self._client.play_pause()

    @Slot()
    def pause(self):
        self._client.pause()

    @Slot()
    def next(self):
        self._client.next()

    @Slot()
    def previous(self):
        self._client.previous()

    @Slot(int)
    def seek(self, ms: int):
        self._client.seek_to(int(ms) * 1000)

    @Slot(int)
    def seekRelative(self, ms: int):
        if self._state.has_track and self._state.can_seek:
            self._client.seek_by(int(ms) * 1000)

    @Slot(float)
    def setVolume(self, value: float):
        self._volume_target = max(0.0, min(1.0, float(value)))
        if not self._volume_timer.isActive():
            self._volume_timer.start()

    def _flush_volume(self):
        if self._volume_target is not None:
            self._client.set_volume(self._volume_target)
            self._volume_target = None

    @Slot()
    def toggleShuffle(self):
        self._client.toggle_shuffle()

    @Slot()
    def cycleLoop(self):
        self._client.cycle_loop()

    @Slot()
    def raisePlayer(self):
        self._client.raise_player()

    @Slot()
    def refresh(self):
        self._client.refresh()

    @Slot(result=bool)
    def launchSpotify(self) -> bool:
        self._install = detect_spotify()
        ok = launch(self._install)
        if ok:
            self._launch_pending_until = time.monotonic() + 20
            QTimer.singleShot(20500, self.changed.emit)
        self.changed.emit()
        return ok


class AppController(QObject):
    changed = Signal()
    quitRequested = Signal()
    showRequested = Signal()
    hideRequested = Signal()
    keepAboveChanged = Signal(bool)
    compactChanged = Signal(bool)
    trayChanged = Signal(bool)
    notify = Signal(str)

    def __init__(self, settings: SettingsStore, player: PlayerController, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._player = player
        self._keep_above_msg = ""
        self._tray_available = False
        self.font_family = ""
        self.font_is_preferred = False
        self.extra_diagnostics = lambda: []
        app = QGuiApplication.instance()
        hints = app.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda *_: self.changed.emit())
        if hasattr(app, "paletteChanged"):
            app.paletteChanged.connect(lambda *_: self.changed.emit())

    # ------------------------------------------------------------ configurações
    def _getter(key):  # noqa: N805
        return lambda self: self._settings.get(key)

    def _setter(key, signal_name=None):  # noqa: N805
        def setter(self, value):
            if self._settings.set(key, value):
                self.changed.emit()
                if signal_name:
                    getattr(self, signal_name).emit(value)
        return setter

    theme = Property(str, _getter("theme"), _setter("theme"), notify=changed)
    alwaysOnTop = Property(bool, _getter("alwaysOnTop"), _setter("alwaysOnTop", "keepAboveChanged"), notify=changed)
    launchSpotifyOnStart = Property(bool, _getter("launchSpotifyOnStart"), _setter("launchSpotifyOnStart"), notify=changed)
    trayEnabled = Property(bool, _getter("trayEnabled"), _setter("trayEnabled", "trayChanged"), notify=changed)
    startMinimized = Property(bool, _getter("startMinimized"), _setter("startMinimized"), notify=changed)
    closeToTray = Property(bool, _getter("closeToTray"), _setter("closeToTray"), notify=changed)
    compactMode = Property(bool, _getter("compactMode"), _setter("compactMode", "compactChanged"), notify=changed)
    del _getter, _setter

    # ------------------------------------------------------------ informações
    def _system_dark(self) -> bool:
        app = QGuiApplication.instance()
        hints = app.styleHints()
        if hasattr(hints, "colorScheme"):
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        return app.palette().color(QPalette.ColorRole.Window).lightness() < 128

    systemDark = Property(bool, _system_dark, notify=changed)
    dark = Property(bool, lambda self: self._settings.get("theme") == "dark"
                    or (self._settings.get("theme") == "auto" and self._system_dark()), notify=changed)
    version = Property(str, lambda self: __version__, constant=True)
    osName = Property(str, lambda self: current_os(), constant=True)
    # Como o sistema se chama nos textos ("Iniciar com o KDE", "Iniciar com o Windows"…)
    desktopName = Property(str, lambda self: {"windows": "Windows", "macos": "macOS"}.get(current_os(), "KDE"),
                           constant=True)
    platformName = Property(str, lambda self: QGuiApplication.platformName(), constant=True)
    isWayland = Property(bool, lambda self: QGuiApplication.platformName().startswith("wayland"), constant=True)
    configPath = Property(str, lambda self: str(self._settings.path), constant=True)
    keepAboveMessage = Property(str, lambda self: self._keep_above_msg, notify=changed)
    trayAvailable = Property(bool, lambda self: self._tray_available, notify=changed)
    settingsError = Property(str, lambda self: self._settings.load_error, constant=True)
    fontFamily = Property(str, lambda self: self.font_family, constant=True)
    fontIsJetBrains = Property(bool, lambda self: self.font_is_preferred, constant=True)
    changelog = Property("QVariantList", lambda self: CHANGELOG, constant=True)
    hasUnseenVersion = Property(bool, lambda self: self._settings.get("lastSeenVersion") != __version__, notify=changed)

    @Slot()
    def markVersionSeen(self):
        if self._settings.set("lastSeenVersion", __version__):
            self.changed.emit()

    def set_keep_above_message(self, msg: str):
        self._keep_above_msg = msg
        self.changed.emit()

    def set_tray_available(self, available: bool):
        self._tray_available = available
        self.changed.emit()

    # -------------------------------------------------------------------- ações
    @Slot()
    def quit(self):
        self.quitRequested.emit()

    @Slot()
    def hideToTray(self):
        self.hideRequested.emit()

    @Slot(result=bool)
    def handleClose(self) -> bool:
        """Chamado no fechamento da janela. True = encerrar; False = só ocultar."""
        if self._tray_available and self._settings.get("trayEnabled") and self._settings.get("closeToTray"):
            self.hideRequested.emit()
            return False
        self.quitRequested.emit()
        return True

    @Slot(result=str)
    def diagnostics(self) -> str:
        st = self._player.state
        try:
            from PySide6 import __version__ as pyside_version
            from PySide6.QtCore import qVersion
            qt = f"PySide6 {pyside_version} / Qt {qVersion()}"
        except Exception:  # pragma: no cover
            qt = "PySide6 ?"
        lines = [
            f"Lurdens {__version__}",
            f"Python {platform.python_version()} ({sys.executable})",
            qt,
            f"Plataforma Qt: {QGuiApplication.platformName()}",
            f"Sistema: {_system_description()}",
            f"Backend: {self._player._client.label}",
            f"Serviço de mídia: {'ok' if st.bus_available else 'indisponível'}",
            f"Spotify: {(st.bus_name or 'conectado') if st.connected else 'não encontrado'}",
            f"Estado: {st.status or '-'} | faixa: {st.title or '-'}",
            f"Recursos: seek={st.can_seek} volume={st.volume is not None} "
            f"aleatório={st.shuffle is not None} repetição={st.loop_status is not None}",
            f"Instalação do Spotify: {self._player._install.label}",
            f"Bandeja do sistema: {'disponível' if self._tray_available else 'indisponível'}",
            f"Configurações: {self._settings.path}",
            f"Cache de capas: {QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)}",
        ]
        if self._player._client.last_error:
            lines.append(f"Último erro do backend: {self._player._client.last_error}")
        if self._keep_above_msg:
            lines.append(f"Sempre no topo: {self._keep_above_msg}")
        hint = ("sudo dnf install jetbrains-mono-fonts-all" if current_os() == "linux"
                else "baixe em jetbrains.com/lp/mono e instale")
        lines.append(f"Fonte: {self.font_family}" + ("" if self.font_is_preferred
                     else f" (JetBrains Mono não instalada: {hint})"))
        try:
            lines.extend(self.extra_diagnostics())
        except Exception as exc:  # diagnóstico nunca falha
            lines.append(f"(erro ao coletar diagnóstico extra: {exc})")
        return "\n".join(lines)

    @Slot()
    def copyDiagnostics(self):
        QGuiApplication.clipboard().setText(self.diagnostics())
        self.notify.emit("Diagnóstico copiado")
