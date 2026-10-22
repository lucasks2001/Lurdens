"""Inicialização da aplicação Qt: janela, bandeja, instância única e autoteste."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import re
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import (QObject, QPoint, QRect, QSize, Qt, QTimer, QUrl, Signal)
from PySide6.QtGui import QAction, QFont, QFontDatabase, QGuiApplication, QIcon, QWindow
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .. import APP_ID, __version__
from ..kwin import set_keep_above_async
from ..settings import SettingsStore
from .controllers import AppController, PlayerController
from .session import SessionController

log = logging.getLogger("lurdens")

PKG_DIR = Path(__file__).resolve().parent.parent
QML_DIR = PKG_DIR / "qml"
RES_DIR = PKG_DIR / "resources"
ICON_DIR = RES_DIR / "icons"


PREFERRED_FONT = "JetBrains Mono"
FALLBACK_FONTS = ("JetBrains Mono NL", "Source Code Pro", "Noto Sans Mono", "DejaVu Sans Mono",
                  "Liberation Mono", "Cascadia Mono", "Hack")


def setup_font(app) -> tuple[str, bool]:
    """Aplica a JetBrains Mono como fonte da aplicação, com alternativas.

    Procura a fonte no sistema (fontconfig, inclusive ~/.local/share/fonts) e,
    se o usuário colocar os .ttf em lurdens/resources/fonts/, carrega de lá.
    Retorna (família usada, se é a JetBrains Mono).
    """
    fonts_dir = RES_DIR / "fonts"
    if fonts_dir.is_dir():
        for f in sorted(fonts_dir.glob("*.[ot]tf")):
            if QFontDatabase.addApplicationFont(str(f)) < 0:
                log.warning("não foi possível carregar a fonte %s", f.name)
    families = set(QFontDatabase.families())
    if PREFERRED_FONT in families:
        family, preferred = PREFERRED_FONT, True
    else:
        family = next((f for f in FALLBACK_FONTS if f in families), "")
        if not family:
            family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        preferred = False
        log.info("JetBrains Mono não encontrada; usando %s", family)
    base = QFont(family)
    base.setPointSizeF(max(9.0, app.font().pointSizeF()))
    base.setStyleHint(QFont.StyleHint.Monospace)
    app.setFont(base)
    return family, preferred


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        p = ICON_DIR / f"lurdens-{s}.png"
        if p.exists():
            icon.addFile(str(p), QSize(s, s))
    svg = ICON_DIR / "lurdens.svg"
    if svg.exists():
        icon.addFile(str(svg))
    if icon.isNull():
        icon = QIcon.fromTheme(APP_ID)
    return icon


# ---------------------------------------------------------------- janela
class WindowManager(QObject):
    _kwin_result = Signal(str)

    def __init__(self, window: QQuickWindow, settings: SettingsStore, appctl: AppController):
        super().__init__(window)
        self.w = window
        self.settings = settings
        self.appctl = appctl
        self.wayland = QGuiApplication.platformName().startswith("wayland")
        self.compact = settings.get("compactMode")
        self._kwin_result.connect(appctl.set_keep_above_message)
        self._save_timer = QTimer(self, interval=600, singleShot=True)
        self._save_timer.timeout.connect(self.remember_geometry)
        for sig in (window.widthChanged, window.heightChanged, window.xChanged, window.yChanged):
            sig.connect(lambda *_: self._save_timer.start())
        window.visibilityChanged.connect(self._on_visibility)
        appctl.keepAboveChanged.connect(self.apply_keep_above)
        appctl.compactChanged.connect(self.apply_compact)

    def _geo_key(self) -> str:
        return "compactWindow" if self.compact else "window"

    def restore_geometry(self):
        geo = self.settings.get(self._geo_key())
        self.w.resize(geo["width"], geo["height"])
        if self.wayland:
            return  # no Wayland o KWin decide a posição; aplicações não podem defini-la
        screen = QGuiApplication.primaryScreen()
        x, y = geo.get("x"), geo.get("y")
        if x is not None and y is not None:
            target = QRect(x, y, geo["width"], geo["height"])
            if any(s.availableGeometry().intersects(target) for s in QGuiApplication.screens()):
                self.w.setPosition(QPoint(x, y))
                return
        if screen:
            area = screen.availableGeometry()
            self.w.setPosition(area.center() - QPoint(geo["width"] // 2, geo["height"] // 2))

    def show_initial(self, hidden: bool):
        self.restore_geometry()
        if self.settings.get("alwaysOnTop") and not self.wayland:
            self.w.setFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        if hidden:
            return
        if self.settings.get("window").get("maximized") and not self.compact:
            self.w.showMaximized()
        else:
            self.w.show()
        self._after_show()

    def _after_show(self):
        if self.settings.get("alwaysOnTop") and self.wayland:
            QTimer.singleShot(400, lambda: self.apply_keep_above(True))

    def _on_visibility(self, vis):
        if vis in (QWindow.Visibility.Maximized, QWindow.Visibility.Windowed) and not self.compact:
            geo = dict(self.settings.get("window"))
            maximized = vis == QWindow.Visibility.Maximized
            if geo.get("maximized") != maximized:
                geo["maximized"] = maximized
                self.settings.set("window", geo)

    def remember_geometry(self):
        if not self.w.isVisible() or self.w.visibility() != QWindow.Visibility.Windowed:
            return
        key = self._geo_key()
        geo = dict(self.settings.get(key))
        geo["width"], geo["height"] = self.w.width(), self.w.height()
        if not self.wayland:
            geo["x"], geo["y"] = self.w.x(), self.w.y()
        self.settings.set(key, geo)

    def show(self):
        if self.w.visibility() == QWindow.Visibility.Minimized:
            self.w.showNormal()
        elif not self.w.isVisible():
            self.w.show()
            self.restore_geometry_if_needed()
            self._after_show()
        self.w.raise_()
        self.w.requestActivate()

    def restore_geometry_if_needed(self):
        if self.wayland:
            geo = self.settings.get(self._geo_key())
            self.w.resize(geo["width"], geo["height"])

    def hide(self):
        self.remember_geometry()
        self.w.hide()

    def toggle(self):
        if self.w.isVisible() and self.w.visibility() != QWindow.Visibility.Minimized:
            self.hide()
        else:
            self.show()

    def apply_keep_above(self, on: bool):
        if self.wayland:
            self.appctl.set_keep_above_message("aplicando pelo KWin…")
            set_keep_above_async(bool(on), lambda err: self._kwin_result.emit(
                err and f"{err}. Alternativa: Alt+F3 › Mais ações › Manter acima das outras." or ""))
        else:
            visible = self.w.isVisible()
            self.w.setFlag(Qt.WindowType.WindowStaysOnTopHint, bool(on))
            if visible:
                self.w.show()

    def apply_compact(self, on: bool):
        self.remember_geometry()
        self.compact = bool(on)
        if self.w.visibility() in (QWindow.Visibility.Maximized, QWindow.Visibility.FullScreen):
            self.w.showNormal()
        geo = self.settings.get(self._geo_key())
        self.w.resize(geo["width"], geo["height"])


# ---------------------------------------------------------------- bandeja
class Tray(QObject):
    def __init__(self, icon: QIcon, wm: WindowManager, player: PlayerController, appctl: AppController,
                 session: SessionController):
        super().__init__(wm)
        self.wm, self.player, self.appctl, self.session = wm, player, appctl, session
        self.icon = QSystemTrayIcon(icon, self)
        self.icon.setToolTip("Lurdens")
        menu = QMenu()
        self.menu = menu
        self.a_toggle = QAction("Mostrar Lurdens", menu, triggered=wm.toggle)
        self.a_play = QAction("Reproduzir", menu, triggered=player.playPause)
        self.a_prev = QAction("Música anterior", menu, triggered=player.previous)
        self.a_next = QAction("Próxima música", menu, triggered=player.next)
        self.a_quit = QAction("Sair do Lurdens", menu, triggered=appctl.quit)
        self.a_now = QAction("", menu)
        self.a_now.setEnabled(False)            # linha informativa: o que está tocando
        self.sleep_menu = QMenu("Temporizador para dormir", menu)
        for m in (15, 30, 45, 60):
            self.sleep_menu.addAction(f"Pausar em {m} min", lambda m=m: session.startSleep(m))
        self.sleep_menu.addSeparator()
        self.a_sleep_cancel = self.sleep_menu.addAction("Cancelar temporizador", session.cancelSleep)
        for a in (self.a_now, None, self.a_play, self.a_prev, self.a_next, None, self.sleep_menu,
                  None, self.a_toggle, self.a_quit):
            if a is None:
                menu.addSeparator()
            elif isinstance(a, QMenu):
                menu.addMenu(a)
            else:
                menu.addAction(a)
        menu.aboutToShow.connect(self._refresh)
        session.sleepChanged.connect(self._refresh_sleep)
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self._activated)
        player.changed.connect(self._refresh)
        wm.w.visibleChanged.connect(lambda *_: self._refresh())
        self._refresh()

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.wm.toggle()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.player.playPause()

    def _refresh(self):
        p = self.player
        self.a_toggle.setText("Ocultar Lurdens" if self.wm.w.isVisible() else "Mostrar Lurdens")
        self.a_play.setText("Pausar" if p.playing else "Reproduzir")
        self.a_play.setEnabled(p.canPlayPause)
        self.a_next.setEnabled(p.canNext)
        self.a_prev.setEnabled(p.canPrevious)
        if p.hasTrack:
            tip = f"{p.title} — {p.artist}" if p.artist else p.title
            now = ("▶ " if p.playing else "❚❚ ") + tip
            tip += "" if p.playing else " (pausado)"
        elif p.connected:
            tip = now = "Spotify aberto — nada tocando"
        else:
            tip = now = "Spotify fechado"
        self.a_now.setText(now if len(now) <= 60 else now[:57] + "…")
        self.icon.setToolTip("Lurdens — " + tip)
        self._refresh_sleep()

    def _refresh_sleep(self):
        s = self.session
        self.sleep_menu.setTitle(f"Temporizador: {s.sleepRemainingText}" if s.sleepActive
                                 else "Temporizador para dormir")
        self.a_sleep_cancel.setEnabled(s.sleepActive)

    def set_visible(self, on: bool):
        self.icon.setVisible(on)


# ------------------------------------------------------- instância única
def _server_name() -> str:
    # Um servidor por usuário. O Windows não tem getuid(): usa o nome do usuário
    # (o QLocalServer vira um named pipe, que já é isolado por sessão).
    try:
        user = str(os.getuid())
    except AttributeError:
        user = re.sub(r"[^A-Za-z0-9_.-]", "_", getpass.getuser())
    return f"{APP_ID}-{user}"


def notify_running_instance(message: bytes = b"show") -> bool:
    sock = QLocalSocket()
    sock.connectToServer(_server_name())
    if not sock.waitForConnected(300):
        return False
    sock.write(message + b"\n")
    sock.flush()
    sock.waitForBytesWritten(300)
    sock.disconnectFromServer()
    return True


def start_instance_server(on_show) -> QLocalServer:
    server = QLocalServer()
    QLocalServer.removeServer(_server_name())
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if server.listen(_server_name()):
        def on_conn():
            conn = server.nextPendingConnection()
            if conn is None:
                return
            def on_ready():
                data = bytes(conn.readAll())
                if not data.startswith(b"autostart"):   # autostart repetido: não mexe na janela
                    on_show()
            conn.readyRead.connect(on_ready)
            conn.disconnected.connect(conn.deleteLater)
        server.newConnection.connect(on_conn)
    return server


# --------------------------------------------------------------- principal
def parse_args(argv):
    ap = argparse.ArgumentParser(prog="lurdens", description="Player complementar para o Spotify.")
    ap.add_argument("--version", action="version", version=f"Lurdens {__version__}")
    ap.add_argument("--debug", action="store_true", help="mostra mensagens de diagnóstico no terminal")
    ap.add_argument("--minimized", action="store_true", help="inicia oculto na bandeja")
    ap.add_argument("--autostart", action="store_true",
                    help="usado pela inicialização automática: inicia na bandeja e nunca abre 2 instâncias")
    ap.add_argument("--selftest", nargs="?", const="", metavar="PASTA",
                    help="renderiza a interface fora da tela, salva capturas e verifica erros de QML")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING,
                        format="%(name)s: %(message)s")
    selftest = args.selftest is not None
    if selftest:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        tmp = tempfile.mkdtemp(prefix="lurdens-selftest-")
        os.environ["XDG_CONFIG_HOME"] = os.path.join(tmp, "config")
        os.environ["XDG_STATE_HOME"] = os.path.join(tmp, "state")
        os.environ["XDG_CACHE_HOME"] = os.path.join(tmp, "cache")
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setApplicationName("Lurdens")
    QApplication.setApplicationDisplayName("Lurdens")
    QApplication.setOrganizationName("Lurdens")
    QApplication.setApplicationVersion(__version__)
    QApplication.setDesktopFileName(APP_ID)
    app = QApplication(sys.argv[:1])

    if not selftest and notify_running_instance(b"autostart" if args.autostart else b"show"):
        if not args.autostart:
            print("Lurdens já está aberto; trazendo a janela para frente.")
        return 0

    icon = app_icon()
    app.setWindowIcon(icon)
    font_family, font_ok = setup_font(app)
    QQuickStyle.setStyle("Basic")

    settings = SettingsStore()
    player = PlayerController(app)
    appctl = AppController(settings, player, app)
    appctl.font_family, appctl.font_is_preferred = font_family, font_ok
    session = SessionController(settings, player, app, desktop=not selftest)
    appctl.extra_diagnostics = session.diagnostics_lines

    engine = QQmlApplicationEngine()
    qml_messages: list[str] = []
    engine.warnings.connect(lambda ws: qml_messages.extend(w.toString() for w in ws))
    ctx = engine.rootContext()
    ctx.setContextProperty("player", player)
    ctx.setContextProperty("app", appctl)
    ctx.setContextProperty("session", session)
    ctx.setContextProperty("resourcesUrl", QUrl.fromLocalFile(str(RES_DIR) + "/").toString())
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        for m in qml_messages:
            print(m, file=sys.stderr)
        print("Falha ao carregar a interface QML.", file=sys.stderr)
        return 1
    window: QQuickWindow = engine.rootObjects()[0]
    window.setIcon(icon)

    if selftest:
        from .selftest import run_selftest
        code = run_selftest(app, window, player, appctl, settings, qml_messages, args.selftest, session)
        session.shutdown()
        return code

    wm = WindowManager(window, settings, appctl)
    server = start_instance_server(wm.show)  # noqa: F841 - mantém o servidor vivo

    tray = None
    tray_ok = QSystemTrayIcon.isSystemTrayAvailable()
    appctl.set_tray_available(tray_ok)
    if tray_ok:
        tray = Tray(icon, wm, player, appctl, session)
        tray.set_visible(settings.get("trayEnabled"))

    def on_tray_setting(on):
        if tray:
            tray.set_visible(on)
        app.setQuitOnLastWindowClosed(not (tray and on))
    appctl.trayChanged.connect(on_tray_setting)
    on_tray_setting(settings.get("trayEnabled"))

    def quit_app():
        wm.remember_geometry()
        app.quit()
    appctl.quitRequested.connect(quit_app)
    appctl.hideRequested.connect(lambda: wm.hide() if tray and settings.get("trayEnabled") else window.showMinimized())
    appctl.showRequested.connect(wm.show)
    session.window_active = lambda: window.isVisible() and window.isActive()

    def on_global_action(action):
        if action == "play-pause":
            player.playPause()
        elif action == "next":
            player.next()
        elif action == "previous":
            player.previous()
        elif action == "show":
            if window.isVisible() and window.isActive() and window.visibility() != QWindow.Visibility.Minimized:
                if tray and settings.get("trayEnabled"):
                    wm.hide()
                else:
                    window.showMinimized()   # sem bandeja, ocultar deixaria a janela inalcançável
            else:
                wm.show()
    session.actionRequested.connect(on_global_action)
    session.notify.connect(appctl.notify)

    tray_on = bool(tray) and settings.get("trayEnabled")
    start_hidden = tray_on and (settings.get("startMinimized") or args.minimized or args.autostart)
    wm.show_initial(hidden=start_hidden)
    if args.autostart and not tray_on:
        window.showMinimized()     # sem bandeja não dá para ocultar: começa minimizado

    player.start()
    if settings.get("launchSpotifyOnStart"):
        QTimer.singleShot(1500, lambda: (not player.connected) and player.launchSpotify())

    app.aboutToQuit.connect(player.stop)
    app.aboutToQuit.connect(session.shutdown)
    code = app.exec()
    if args.debug:
        for m in qml_messages:
            print(m, file=sys.stderr)
    return code
