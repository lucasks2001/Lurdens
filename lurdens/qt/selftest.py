"""Autoteste da interface: `lurdens --selftest [PASTA]`.

Renderiza a janela fora da tela (plataforma offscreen, renderizador por
software) em vários tamanhos e temas, salva capturas PNG e falha se o QML
emitir qualquer aviso ou erro. Os estados de reprodução usados aqui são de
DEMONSTRAÇÃO e só existem nas capturas do autoteste — nunca na interface real.
"""

from __future__ import annotations

import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer

from ..state import PlayerState

RES = Path(__file__).resolve().parent.parent / "resources"


def _wait(ms: int):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def demo_state(**kw) -> PlayerState:
    base = dict(
        bus_available=True, connected=True, bus_name="org.mpris.MediaPlayer2.spotify",
        identity="Spotify", status="Playing", track_id="/demo/track/1",
        title="DEMONSTRAÇÃO — Hachura em Diagonal", artists=("Autoteste do Lurdens",),
        album="Captura de verificação", art_url=(RES / "placeholder-cover.png").as_uri(),
        length_us=215_000_000, position_us=83_000_000, position_ts=time.monotonic(),
        can_control=True, can_play=True, can_pause=True, can_next=True, can_prev=True,
        can_seek=True, volume=0.62, shuffle=True, loop_status="Track",
    )
    base.update(kw)
    return PlayerState(**base)


def _title_centered(window) -> bool:
    """Procura o Text do título ("Curto") e confere se está centrado no MarqueeText."""
    def walk(item):
        yield item
        for child in item.childItems():
            yield from walk(child)

    for item in walk(window.contentItem()):
        parent = item.parentItem()
        if item.property("text") == "Curto" and parent is not None and parent.property("overflow") is not None:
            expected = round((parent.width() - item.implicitWidth()) / 2)
            return abs(item.x() - expected) <= 1
    return False


def _find(window, object_name):
    def walk(item):
        yield item
        for child in item.childItems():
            yield from walk(child)
    for item in walk(window.contentItem()):
        if item.objectName() == object_name:
            return item
    return None


def run_selftest(app, window, player, appctl, settings, messages, outdir: str, session=None) -> int:
    out = Path(outdir) if outdir else Path(tempfile.mkdtemp(prefix="lurdens-capturas-"))
    out.mkdir(parents=True, exist_ok=True)
    shots = []
    checks = []          # (descrição, ok)

    def shot(name, w, h, state, theme="dark", wait=700, **pages):
        appctl.theme = theme
        player._apply(state)
        for prop in ("settingsOpen", "aboutOpen", "changelogOpen", "historyOpen", "sleepOpen"):
            window.setProperty(prop, bool(pages.get(prop, False)))
        window.resize(w, h)
        window.show()
        _wait(wait)
        img = window.grabWindow()
        path = out / f"{name}.png"
        ok = img.save(str(path))
        shots.append((path, ok, img.width(), img.height()))

    long_title = demo_state(title="DEMONSTRAÇÃO — um título muito longo que precisa rolar sem invadir os controles",
                            status="Paused", shuffle=False, loop_status="None")
    legacy = demo_state(volume=None, shuffle=None, loop_status=None, art_url="")

    shot("01-retrato-escuro", 420, 720, demo_state())
    shot("02-retrato-claro", 420, 720, demo_state(), theme="light")
    shot("03-titulo-longo-pausado", 420, 720, long_title)
    shot("04-sem-recursos-opcionais", 420, 720, legacy)
    shot("05-spotify-fechado", 420, 720, PlayerState(bus_available=True))
    shot("06-sem-dbus", 420, 720, PlayerState())
    shot("07-amplo", 1280, 800, demo_state())
    shot("08-amplo-claro", 1600, 900, demo_state(), theme="light")
    shot("09-mini", 420, 184, demo_state())
    shot("10-minimo", 320, 480, demo_state())
    shot("11-configuracoes", 420, 720, demo_state(), settingsOpen=True)
    shot("12-sobre", 420, 720, demo_state(), aboutOpen=True)
    shot("13-novidades", 420, 720, demo_state(), changelogOpen=True)

    # troca de faixa: o título curto precisa ficar centralizado logo em seguida
    shot("14-antes-troca", 420, 720, demo_state(title="Um título razoavelmente comprido aqui"))
    player._apply(demo_state(track_id="/demo/track/2", title="Curto"))
    _wait(60)
    after = out / "15-logo-apos-troca.png"
    shots.append((after, window.grabWindow().save(str(after)), 420, 720))
    checks.append(("Título centralizado após troca", _title_centered(window)))

    # ---- 1.2: configurações completas, histórico, temporizador, easter egg
    shot("16-configuracoes-completas", 420, 2600, demo_state(), settingsOpen=True)
    for i in range(3, 7):
        player._apply(demo_state(track_id=f"/demo/track/{i}", title=f"DEMONSTRAÇÃO — faixa {i}"))
    shot("17-historico", 420, 720, demo_state(track_id="/demo/track/7", title="DEMONSTRAÇÃO — faixa 7"),
         historyOpen=True)
    if session is not None:
        checks.append(("Histórico registra cada troca uma vez", session.historyCount >= 6))
        session.startSleep(30)
        shot("18-temporizador-ativo", 420, 720, demo_state(), sleepOpen=True)
        shot("19-barra-com-temporizador", 420, 720, demo_state())
        checks.append(("Temporizador ativo", session.sleepActive and 1700 < session.sleepRemaining <= 1800))
        session.cancelSleep()

    # A arte do easter egg não fica no repositório (é gerada por tools/make_easter.py);
    # sem ela o efeito fica desligado de propósito, então essas verificações não se aplicam.
    if session is not None and not session.easterAvailable:
        print("  -- easter egg: arte ausente, verificações puladas")
    elif session is not None:
        ludens = demo_state(track_id="/demo/ludens", title="Ludens", artists=("Bring Me The Horizon",),
                            album="DEMONSTRAÇÃO do autoteste")
        shot("20-easter-ludens-escuro", 420, 720, ludens, wait=1800)
        art = _find(window, "ludensArt")
        bg = art.parentItem() if art is not None else None
        checks.append(("Easter egg ativa com Ludens tocando", session.easterMode == "playing"))
        checks.append(("Arte do easter egg carregada",
                       art is not None and art.property("status") == 1 and bg.property("opacity") > 0.15))
        shot("21-easter-ludens-claro", 420, 720, ludens, theme="light", wait=1800)
        shot("22-easter-ludens-amplo", 1280, 800, ludens, wait=1800)
        shot("23-easter-pausado", 420, 720, replace(ludens, status="Paused"), wait=1800)
        checks.append(("Easter egg discreto ao pausar", session.easterMode == "paused"))
        shot("24-apos-ludens", 420, 720, demo_state(track_id="/demo/outra", title="DEMONSTRAÇÃO — outra"),
             wait=1800)
        checks.append(("Fundo volta ao normal na troca de faixa",
                       session.easterMode == "off" and (bg is None or bg.property("opacity") < 0.01)))
        player._apply(replace(ludens, artists=("Outra Banda",)))
        _wait(100)
        checks.append(("Easter egg ignora outro artista", session.easterMode == "off"))

    # persistência de configurações (em diretório temporário)
    appctl.alwaysOnTop = True
    appctl.theme = "auto"
    from ..settings import SettingsStore
    reloaded = SettingsStore(settings.path)
    checks.append(("Configurações persistem",
                   reloaded.get("alwaysOnTop") is True and reloaded.get("theme") == "auto"))
    checks.append((f"Fonte: {appctl.fontFamily}" + ("" if appctl.fontIsJetBrains else " (JetBrains Mono ausente — aviso)"),
                   True))

    print(f"Capturas em: {out}")
    for path, ok, w, h in shots:
        print(f"  {'ok ' if ok else 'ERRO'} {path.name} ({w}×{h})")
    print()
    for desc, ok in checks:
        print(f"  {'ok ' if ok else 'ERRO'} {desc}")
    if messages:
        print(f"\n{len(messages)} aviso(s) do QML:", file=sys.stderr)
        for m in dict.fromkeys(messages):
            print("  " + m, file=sys.stderr)
    failed = bool(messages) or not all(ok for _, ok in checks) or not all(ok for _, ok, *_ in shots)
    print("\nAUTOTESTE: " + ("FALHOU" if failed else "OK"))
    app.processEvents()
    return 1 if failed else 0
