"""SessionController: funcionalidades da 1.2 expostas ao QML.

Tudo é alimentado pelo MESMO fluxo de estado do player (PlayerController.changed):
histórico, notificações e easter egg não mantêm acompanhamentos paralelos do Spotify.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QSystemTrayIcon

from .. import autostart, paths
from ..backends import current_os
from ..easter import EasterWatcher
from ..notify import Notifier
from ..settings import SettingsStore
from ..shortcuts import ACTIONS, GlobalShortcuts, key_text
from ..timers import SleepTimer, UsageTracker, format_clock, format_duration
from ..tracks import History, PlayDetector

log = logging.getLogger("lurdens.session")

RES_DIR = Path(__file__).resolve().parent.parent / "resources"
EASTER_DIR = RES_DIR / "easter"
NOTIFY_DEBOUNCE_MS = 900


def state_dir() -> Path:
    return paths.state_dir()


def _launch_detached(cmd: list[str]) -> bool:
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def _open_system_page(page: str) -> bool:
    """Abre uma página das configurações do sistema ("notifications" ou "shortcuts")."""
    os_name = current_os()
    if os_name == "windows":
        uri = {"notifications": "ms-settings:notifications"}.get(page)
        if not uri:
            return False
        try:
            os.startfile(uri)           # type: ignore[attr-defined]
            return True
        except OSError:
            return False
    if os_name == "macos":
        uri = {"notifications": "x-apple.systempreferences:com.apple.preference.notifications",
               "shortcuts": "x-apple.systempreferences:com.apple.preference.keyboard?Shortcuts"}.get(page)
        return bool(uri) and _launch_detached(["open", uri])
    kcm = {"notifications": "kcm_notifications", "shortcuts": "kcm_keys"}[page]
    return _launch_detached(["systemsettings", kcm])


class TrayNotifier(QObject):
    """Notificações pelo ícone da bandeja, para sistemas sem o serviço do freedesktop.

    No Windows viram notificações da Central de Ações; no macOS, da Central de
    Notificações. Precisam do ícone da bandeja visível (Configurações ›
    Ícone na bandeja do sistema). Mesma interface do Notifier do Linux.
    """
    _post = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon: QSystemTrayIcon | None = None
        self.last_error = ""
        self.sent = 0
        self._post.connect(self._deliver)

    def attach(self, icon: QSystemTrayIcon | None) -> None:
        self._icon = icon

    def track(self, title: str, artist: str, album: str, art_url: str) -> None:
        self._post.emit(title, artist + (f"\n{album}" if album else ""))

    def message(self, summary: str, body: str = "") -> None:
        self._post.emit(summary, body)

    def stop(self) -> None:
        self._icon = None

    def _deliver(self, title: str, body: str) -> None:
        icon = self._icon
        if icon is None or not icon.isVisible() or not QSystemTrayIcon.supportsMessages():
            self.last_error = "ícone da bandeja desligado: sem onde mostrar notificações"
            return
        icon.showMessage(title, body, icon.icon(), 5000)
        self.sent += 1
        self.last_error = ""


class SessionController(QObject):
    historyChanged = Signal()
    easterChanged = Signal()
    sleepChanged = Signal()
    usageChanged = Signal()
    settingsChanged = Signal()
    shortcutsChanged = Signal()
    actionRequested = Signal(str)        # atalho global pressionado
    notify = Signal(str)                 # aviso curto para a interface (toast)
    _shortcut_pressed = Signal(str)
    _shortcut_state = Signal()

    def __init__(self, settings: SettingsStore, player, parent=None, desktop: bool = True,
                 bus_address: str | None = None):
        super().__init__(parent)
        self._settings = settings
        self._player = player
        self.window_active = lambda: False
        sdir = state_dir()

        # histórico e detecção de faixas
        self._detector = PlayDetector()
        self._history = History(sdir / "history.json", persist=settings.get("historyPersist"))
        self._pending_event = None
        self._notify_timer = QTimer(self, singleShot=True, interval=NOTIFY_DEBOUNCE_MS)
        self._notify_timer.timeout.connect(self._send_pending_notification)

        # easter egg
        self._easter = EasterWatcher()
        self.easter_available = all((EASTER_DIR / f"ludens-hatch-{v}.png").exists() for v in ("light", "dark"))
        if not self.easter_available:
            log.warning("arte do easter egg ausente em %s — efeito desativado", EASTER_DIR)

        # temporizadores
        self._sleep = SleepTimer()
        self._usage = UsageTracker(sdir / "usage.json", persist=settings.get("usageTracking"))
        self._tick = QTimer(self, interval=1000)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()
        self._ticks = 0

        # integrações com o desktop (desligadas no autoteste)
        self.os_name = current_os()
        linux = self.os_name == "linux"
        self._notifier = None
        if desktop:
            self._notifier = Notifier(bus_address) if linux else TrayNotifier(self)
        self._shortcuts = None
        self._shortcuts_note = "desativados no autoteste"
        if not linux:
            # kglobalaccel é do KDE. No Windows e no macOS as teclas de mídia do
            # teclado já vão direto para o Spotify.
            self._shortcuts_note = ("disponíveis só no KDE Plasma; as teclas de mídia do teclado "
                                    "controlam o Spotify diretamente")
        elif desktop:
            self._shortcut_pressed.connect(self.actionRequested)
            self._shortcut_state.connect(self.shortcutsChanged)
            self._shortcuts = GlobalShortcuts(self._shortcut_pressed.emit, self._shortcut_state.emit, bus_address)
            self._shortcuts.start()

        player.changed.connect(self._on_player_state)

    # ================================================================ fluxo
    def _on_player_state(self):
        state = self._player.state
        if self._easter.update(state):
            self.easterChanged.emit()
        ev = self._detector.update(state)
        if ev is None:
            return
        self._history.add(ev)
        self.historyChanged.emit()
        if not ev.initial:
            # espera a faixa "assentar": trocas rápidas geram uma notificação só
            self._pending_event = ev
            self._notify_timer.start()

    def _send_pending_notification(self):
        ev, self._pending_event = self._pending_event, None
        if ev is None or self._notifier is None or not self._settings.get("notifyTracks"):
            return
        if ev.track_id != self._player.state.track_id:
            return
        if self.window_active():
            return     # o usuário já está olhando para o Lurdens
        self._notifier.track(ev.title, ev.artist, ev.album, ev.art_url)

    def _on_tick(self):
        self._ticks += 1
        if self._sleep.active:
            if self._sleep.poll():
                self._sleep_finished()
            self.sleepChanged.emit()
        self._usage.tick()
        self.usageChanged.emit()
        if self._ticks % 60 == 0:
            self._usage.flush()

    def _sleep_finished(self):
        st = self._player.state
        if st.connected and st.playing:
            self._player.pause()
            msg = "Temporizador terminou: reprodução pausada"
        elif st.connected:
            msg = "Temporizador terminou (já estava pausado)"
        else:
            msg = "Temporizador terminou (Spotify não estava aberto)"
        self.notify.emit(msg)
        if self._notifier is not None:
            self._notifier.message("Lurdens", msg)

    def attach_tray(self, icon) -> None:
        """Liga as notificações à bandeja (Windows/macOS)."""
        if isinstance(self._notifier, TrayNotifier):
            self._notifier.attach(icon)

    def shutdown(self):
        self._tick.stop()
        self._usage.flush()
        if self._notifier:
            self._notifier.stop()
        if self._shortcuts:
            self._shortcuts.stop()

    # ============================================================ histórico
    history = Property("QVariantList", lambda self: [e.as_qml() for e in self._history.entries], notify=historyChanged)
    historyCount = Property(int, lambda self: len(self._history.entries), notify=historyChanged)

    @Slot()
    def clearHistory(self):
        self._history.clear()
        self.historyChanged.emit()

    def _get_history_persist(self):
        return self._settings.get("historyPersist")

    def _set_history_persist(self, on):
        if self._settings.set("historyPersist", bool(on)):
            self._history.set_persist(bool(on))
            self.settingsChanged.emit()

    historyPersist = Property(bool, _get_history_persist, _set_history_persist, notify=settingsChanged)
    historyFile = Property(str, lambda self: str(self._history.path), constant=True)

    # ========================================================== easter egg
    easterMode = Property(str, lambda self: self._easter.mode if self.easter_available else "off", notify=easterChanged)
    easterEdition = Property(str, lambda self: self._easter.edition, notify=easterChanged)
    easterAvailable = Property(bool, lambda self: self.easter_available, constant=True)

    # ======================================================= temporizador
    sleepActive = Property(bool, lambda self: self._sleep.active, notify=sleepChanged)
    sleepRemaining = Property(int, lambda self: self._sleep.remaining(), notify=sleepChanged)
    sleepRemainingText = Property(str, lambda self: format_clock(self._sleep.remaining()), notify=sleepChanged)
    sleepDuration = Property(int, lambda self: self._sleep.duration, notify=sleepChanged)

    @Slot(int)
    def startSleep(self, minutes: int):
        self._sleep.start(int(minutes) * 60)
        self.sleepChanged.emit()
        self.notify.emit(f"Pausa em {int(minutes)} min")

    @Slot(int)
    def extendSleep(self, minutes: int):
        self._sleep.extend(int(minutes) * 60)
        self.sleepChanged.emit()

    @Slot()
    def restartSleep(self):
        self._sleep.restart()
        self.sleepChanged.emit()

    @Slot()
    def cancelSleep(self):
        self._sleep.cancel()
        self.sleepChanged.emit()
        self.notify.emit("Temporizador cancelado")

    # ======================================================== tempo de uso
    usageSession = Property(str, lambda self: format_duration(self._usage.session_seconds()), notify=usageChanged)
    usageToday = Property(str, lambda self: format_duration(int(self._usage.today_seconds)), notify=usageChanged)
    usageStart = Property(str, lambda self: self._usage.session_started_at.strftime("%d/%m/%Y às %H:%M"),
                          notify=usageChanged)

    def _get_usage_enabled(self):
        return self._settings.get("usageTracking")

    def _set_usage_enabled(self, on):
        if self._settings.set("usageTracking", bool(on)):
            self._usage.set_persist(bool(on))
            self.settingsChanged.emit()
            self.usageChanged.emit()

    usageEnabled = Property(bool, _get_usage_enabled, _set_usage_enabled, notify=settingsChanged)
    usageFile = Property(str, lambda self: str(self._usage.path), constant=True)

    @Slot()
    def resetUsageSession(self):
        self._usage.reset_session()
        self.usageChanged.emit()
        self.notify.emit("Contador da sessão reiniciado")

    # ======================================================= notificações
    def _get_notify(self):
        return self._settings.get("notifyTracks")

    def _set_notify(self, on):
        if self._settings.set("notifyTracks", bool(on)):
            self.settingsChanged.emit()

    notifyTracks = Property(bool, _get_notify, _set_notify, notify=settingsChanged)

    @Slot()
    def openNotificationSettings(self):
        if not _open_system_page("notifications"):
            self.notify.emit("Não foi possível abrir as Configurações do Sistema")

    # ======================================================== autostart
    def _get_autostart(self):
        return autostart.is_enabled()

    def _set_autostart(self, on):
        try:
            autostart.enable() if on else autostart.disable()
        except OSError as exc:
            self.notify.emit(f"Falha ao alterar a inicialização: {exc}")
        self.settingsChanged.emit()

    autostartEnabled = Property(bool, _get_autostart, _set_autostart, notify=settingsChanged)
    autostartFile = Property(str, lambda self: autostart.location(), constant=True)

    # =========================================================== atalhos
    def _shortcut_list(self):
        sc = self._shortcuts
        out = []
        for a in ACTIONS:
            key = sc.keys.get(a.id, 0) if sc else 0
            out.append({"id": a.id, "label": a.label, "key": key, "text": self.keyText(key),
                        "defaultText": self.keyText(a.default),
                        "conflict": bool(sc and a.id in sc.conflicts)})
        return out

    shortcuts = Property("QVariantList", _shortcut_list, notify=shortcutsChanged)
    shortcutsAvailable = Property(bool, lambda self: bool(self._shortcuts and self._shortcuts.available),
                                  notify=shortcutsChanged)
    shortcutsStatus = Property(str, lambda self: self._shortcuts.status if self._shortcuts else self._shortcuts_note,
                               notify=shortcutsChanged)

    @Slot(int, result=str)
    def keyText(self, key: int) -> str:
        if not key:
            return ""
        try:
            text = QKeySequence(int(key)).toString(QKeySequence.SequenceFormat.NativeText)
            return text or key_text(key)
        except Exception:
            return key_text(key)

    @Slot(str, int)
    def setShortcut(self, action: str, key: int):
        if self._shortcuts and self._shortcuts.available:
            self._shortcuts.set_key(action, int(key))

    @Slot()
    def resetShortcuts(self):
        if self._shortcuts and self._shortcuts.available:
            self._shortcuts.reset_defaults()

    @Slot()
    def openSystemShortcuts(self):
        if not _open_system_page("shortcuts"):
            self.notify.emit("Não foi possível abrir as Configurações do Sistema")

    # ======================================================== diagnóstico
    def diagnostics_lines(self) -> list[str]:
        lines = [
            f"Atalhos globais: {self.shortcutsStatus}",
            f"Notificações: {'ligadas' if self._settings.get('notifyTracks') else 'desligadas'}"
            + (f" (último erro: {self._notifier.last_error})" if self._notifier and self._notifier.last_error else ""),
            f"Inicialização com a sessão: {'sim' if autostart.is_enabled() else 'não'}",
            f"Histórico: {len(self._history.entries)} faixas, "
            f"{'salvo em ' + str(self._history.path) if self._history.persist else 'só em memória'}",
            f"Arte do easter egg: {'ok' if self.easter_available else 'AUSENTE em ' + str(EASTER_DIR)}",
        ]
        for err in (self._history.error, self._usage.error):
            if err:
                lines.append(f"Aviso: {err}")
        return lines
