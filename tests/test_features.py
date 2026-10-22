"""Testes das funcionalidades da 1.2.0 (sem interface gráfica).

Executar:  python3 -m unittest discover -s tests -v
Os testes de integração usam um dbus-daemon privado e serviços simulados
(tests/mock_desktop.py, tests/mock_spotify.py) — não o Plasma nem o Spotify reais.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lurdens import autostart  # noqa: E402
from lurdens.dbus.wire import Connection  # noqa: E402
from lurdens.easter import EasterWatcher, artist_matches, edition, is_ludens, title_matches  # noqa: E402
from lurdens.shortcuts import ACTIONS, META, ALT, decode_keys, encode_keys, key_text  # noqa: E402
from lurdens.state import PlayerState  # noqa: E402
from lurdens.timers import SleepTimer, UsageTracker, format_clock, format_duration  # noqa: E402
from lurdens.tracks import History, PlayDetector  # noqa: E402

MOCK_PY = os.environ.get("LURDENS_MOCK_PYTHON", sys.executable)


def _mocks_available() -> bool:
    if not shutil.which("dbus-daemon"):
        return False
    r = subprocess.run([MOCK_PY, "-c", "import dbus, dbus.service, dbus.mainloop.glib; from gi.repository import GLib"],
                       capture_output=True)
    return r.returncode == 0


def st(**kw) -> PlayerState:
    base = dict(bus_available=True, connected=True, status="Playing", track_id="/t/1",
                title="Ludens", artists=("Bring Me The Horizon",), album="Death Stranding: Timefall",
                length_us=200_000_000, position_us=0, position_ts=time.monotonic())
    base.update(kw)
    return PlayerState(**base)


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


# ------------------------------------------------------------- easter egg
class EasterTests(unittest.TestCase):
    def test_both_editions(self):
        self.assertTrue(is_ludens(st(album="Death Stranding: Timefall")))
        self.assertTrue(is_ludens(st(album="POST HUMAN: SURVIVAL HORROR")))
        self.assertEqual(edition("Death Stranding: Timefall (Original Music…)"), "Death Stranding: Timefall")
        self.assertEqual(edition("post human: survival horror"), "POST HUMAN: SURVIVAL HORROR")

    def test_album_is_not_required(self):
        self.assertTrue(is_ludens(st(album="")))
        self.assertTrue(is_ludens(st(album="Alguma Coletânea")))

    def test_title_variations(self):
        for t in ("Ludens", "LUDENS", "  ludens ", "Ludens - 2020", "Ludens (From Death Stranding: Timefall)",
                  "Lúdens", "Ludens [Explicit]"):
            self.assertTrue(title_matches(t), t)
        for t in ("Ludens (Remix)", "Ludens - Live", "Ludens (Acoustic)", "Ludenss", "Homo Ludens",
                  "Ludens Pt. 2", "", "Teardrops"):
            self.assertFalse(title_matches(t), t)

    def test_artist_variations(self):
        for a in (["Bring Me The Horizon"], ["bring me the horizon"], ["BRING ME THE HORIZON "], ["BMTH"],
                  ["Bring Me the Horizon, Someone"], ["Fulano", "Bring Me The Horizon"]):
            self.assertTrue(artist_matches(a), a)
        for a in ([], [""], ["Bring Me"], ["Horizon"], ["Bring Me The Horizon Tribute Band"], ["Ludens"]):
            self.assertFalse(artist_matches(a), a)

    def test_missing_artist_never_matches(self):
        self.assertFalse(is_ludens(st(artists=())))

    def test_watcher_lifecycle(self):
        w = EasterWatcher()
        self.assertTrue(w.update(st()))
        self.assertEqual(w.mode, "playing")
        self.assertFalse(w.update(st(position_us=50_000_000)))      # posição não muda nada
        self.assertTrue(w.update(st(status="Paused")))
        self.assertEqual(w.mode, "paused")
        self.assertTrue(w.update(st()))
        self.assertEqual(w.mode, "playing")
        # troca de faixa com metadados incompletos: mantém até chegar o título
        self.assertFalse(w.update(st(track_id="/t/2", title="")))
        self.assertEqual(w.mode, "playing")
        self.assertTrue(w.update(st(track_id="/t/2", title="Teardrops")))
        self.assertEqual(w.mode, "off")
        self.assertTrue(w.update(st(album="POST HUMAN: SURVIVAL HORROR", track_id="/t/3")))
        self.assertEqual(w.edition, "POST HUMAN: SURVIVAL HORROR")
        self.assertTrue(w.update(PlayerState(bus_available=True)))   # Spotify fechou
        self.assertEqual(w.mode, "off")

    def test_other_artist_with_same_title(self):
        w = EasterWatcher()
        self.assertFalse(w.update(st(artists=("Outra Banda",))))
        self.assertEqual(w.mode, "off")


# --------------------------------------------------------- histórico/eventos
class DetectorTests(unittest.TestCase):
    def test_entries(self):
        d = PlayDetector(clock=FakeClock())
        ev = d.update(st(title="A", track_id="/a"))
        self.assertTrue(ev and ev.initial)                       # já tocava ao conectar
        self.assertIsNone(d.update(st(title="A", track_id="/a", position_us=9_000_000)))
        self.assertIsNone(d.update(st(title="A", track_id="/a", status="Paused")))
        ev = d.update(st(title="B", track_id="/b"))
        self.assertTrue(ev and not ev.initial)
        self.assertEqual(ev.title, "B")
        ev = d.update(st(title="A", track_id="/a"))              # voltou a uma faixa já ouvida
        self.assertTrue(ev)

    def test_incomplete_and_ads(self):
        d = PlayDetector()
        self.assertIsNone(d.update(st(title="", track_id="/x")))
        ev = d.update(st(title="X", track_id="/x"))
        self.assertTrue(ev.initial, "metadados incompletos não podem consumir o 'initial'")
        self.assertIsNone(d.update(st(title="Anúncio", track_id="/com/spotify/ad/123")))

    def test_reconnect_same_track_no_duplicate(self):
        d = PlayDetector()
        self.assertTrue(d.update(st(track_id="/a", title="A")))
        self.assertIsNone(d.update(PlayerState(bus_available=True)))
        self.assertIsNone(d.update(st(track_id="/a", title="A")))
        ev = d.update(st(track_id="/b", title="B"))
        self.assertFalse(ev.initial)

    def test_repeat_one_counts_as_new_play(self):
        d = PlayDetector()
        d.update(st(track_id="/a", title="A", length_us=100_000_000, position_us=0))
        self.assertIsNone(d.update(st(track_id="/a", title="A", length_us=100_000_000, position_us=97_000_000)))
        ev = d.update(st(track_id="/a", title="A", length_us=100_000_000, position_us=500_000))
        self.assertTrue(ev)

    def test_history_persistence_optional(self):
        with tempfile.TemporaryDirectory() as tdir:
            p = Path(tdir) / "history.json"
            d = PlayDetector(clock=FakeClock(1_700_000_000))
            h = History(p, persist=False)
            h.add(d.update(st(track_id="/a", title="A", art_url="https://i.scdn.co/image/x")))
            self.assertFalse(p.exists())
            h.set_persist(True)
            h.add(d.update(st(track_id="/b", title="B")))
            self.assertEqual([e.title for e in History(p, persist=True).entries], ["B", "A"])
            item = h.entries[0].as_qml()
            self.assertEqual(set(item), {"title", "artist", "album", "artUrl", "time", "day"})
            h.clear()
            self.assertEqual(History(p, persist=True).entries, [])
            h.set_persist(False)
            self.assertFalse(p.exists())
            p.write_text("{lixo")
            self.assertTrue(History(p, persist=True).error)


# ------------------------------------------------------------- temporizadores
class SleepTimerTests(unittest.TestCase):
    def test_fires_once_at_deadline(self):
        c = FakeClock()
        t = SleepTimer(clock=c)
        t.start(15 * 60)
        self.assertEqual(t.remaining(), 900)
        c.t += 899.4
        self.assertFalse(t.poll())
        c.t += 1
        self.assertTrue(t.poll())
        self.assertFalse(t.poll())
        self.assertFalse(t.active)

    def test_controls(self):
        c = FakeClock()
        t = SleepTimer(clock=c)
        t.start(5)                     # mínimo de 1 min
        self.assertEqual(t.remaining(), 60)
        t.start(30 * 60)
        c.t += 600
        t.extend(5 * 60)
        self.assertEqual(t.remaining(), 25 * 60)
        t.restart()
        self.assertEqual(t.remaining(), 30 * 60)
        t.cancel()
        self.assertFalse(t.poll())
        self.assertEqual(t.remaining(), 0)

    def test_suspend_does_not_delay(self):
        # o relógio de boot avança durante a suspensão: ao acordar o prazo já venceu
        c = FakeClock()
        t = SleepTimer(clock=c)
        t.start(45 * 60)
        c.t += 3 * 3600
        self.assertTrue(t.poll())


class UsageTests(unittest.TestCase):
    def test_session_and_today(self):
        with tempfile.TemporaryDirectory() as tdir:
            p = Path(tdir) / "usage.json"
            mono = FakeClock(100)
            now = [datetime(2026, 10, 22, 9, 0, 0)]
            u = UsageTracker(p, persist=True, mono=mono, now=lambda: now[0])
            mono.t += 120
            now[0] += timedelta(seconds=120)
            self.assertEqual(u.session_seconds(), 120)
            self.assertEqual(u.today_total(), 120)
            u.flush()
            # nova sessão no mesmo dia soma ao total do dia
            mono2 = FakeClock(5)
            u2 = UsageTracker(p, persist=True, mono=mono2, now=lambda: now[0])
            mono2.t += 30
            self.assertEqual(u2.session_seconds(), 30)
            self.assertEqual(u2.today_total(), 150)
            u2.reset_session()
            self.assertEqual(u2.session_seconds(), 0)
            self.assertEqual(u2.today_total(), 150)

    def test_midnight_rollover(self):
        with tempfile.TemporaryDirectory() as tdir:
            p = Path(tdir) / "usage.json"
            mono = FakeClock(0)
            now = [datetime(2026, 10, 22, 23, 59, 0)]
            u = UsageTracker(p, persist=True, mono=mono, now=lambda: now[0])
            mono.t += 120
            now[0] += timedelta(seconds=120)          # 00:01 do dia seguinte
            self.assertEqual(u.today_total(), 60)
            self.assertEqual(u.today.isoformat(), "2026-10-23")
            self.assertEqual(u.session_seconds(), 120)

    def test_old_day_and_disabled(self):
        with tempfile.TemporaryDirectory() as tdir:
            p = Path(tdir) / "usage.json"
            p.write_text(json.dumps({"date": "2020-01-01", "seconds": 999}))
            u = UsageTracker(p, persist=True, mono=FakeClock(), now=lambda: datetime(2026, 10, 22, 10))
            self.assertEqual(u.today_total(), 0)
            u.set_persist(False)
            self.assertFalse(p.exists())
            u.flush()
            self.assertFalse(p.exists())

    def test_formatting(self):
        self.assertEqual(format_duration(3725), "1h 02min 05s")
        self.assertEqual(format_duration(65), "1min 05s")
        self.assertEqual(format_clock(905), "15:05")
        self.assertEqual(format_clock(3725), "1:02:05")


# ---------------------------------------------------------- autostart/atalhos
class AutostartTests(unittest.TestCase):
    def test_enable_disable(self):
        with tempfile.TemporaryDirectory() as tdir:
            d = Path(tdir)
            self.assertFalse(autostart.is_enabled(d))
            path = autostart.enable(d, command="/home/u/.local/bin/lurdens")
            text = path.read_text()
            self.assertIn("Exec=/home/u/.local/bin/lurdens --autostart", text)
            self.assertTrue(autostart.is_enabled(d))
            path.write_text(text + "Hidden=true\n")       # desativado pelo KDE
            self.assertFalse(autostart.is_enabled(d))
            autostart.disable(d)
            autostart.disable(d)                          # idempotente
            self.assertFalse(autostart.is_enabled(d))


class ShortcutCodecTests(unittest.TestCase):
    def test_codec_and_text(self):
        k = META | ALT | 0x50
        self.assertEqual(decode_keys(encode_keys(k)), k)
        self.assertEqual(encode_keys(0), [])
        self.assertEqual(key_text(k), "Meta+Alt+P")
        self.assertEqual(key_text(0x04000000 | 0x01000014), "Ctrl+→")
        self.assertEqual(len({a.default for a in ACTIONS}), len(ACTIONS))


# --------------------------------------------------------------- integração
@unittest.skipUnless(_mocks_available(), "dbus-daemon ou dbus-python/GLib indisponíveis")
class DesktopIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.daemon = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1",
                                        f"--address=unix:dir={self.tmp.name}"],
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.address = self.daemon.stdout.readline().strip()
        self.env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=self.address)
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            p.kill()
            p.wait()
            p.stdout.close()
        self.daemon.kill()
        self.daemon.wait()
        self.daemon.stdout.close()
        self.tmp.cleanup()

    def start(self, script, *args):
        p = subprocess.Popen([MOCK_PY, str(ROOT / "tests" / script), *args], env=self.env,
                             stdout=subprocess.PIPE, text=True)
        self.assertIn("pronto", p.stdout.readline())
        self.procs.append(p)
        return p

    def ctl(self, dest, path, member, sig="", args=()):
        c = Connection(self.address)
        try:
            return c.call(dest, path, "org.lurdens.MockDesktop", member, sig, args)
        finally:
            c.close()

    def wait_until(self, pred, timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if pred():
                return True
            time.sleep(0.05)
        return False

    def test_notifications_replace_and_cover(self):
        from lurdens.notify import CoverCache, Notifier
        self.start("mock_desktop.py", "--no-kglobalaccel")
        cover = Path(self.tmp.name) / "capa.png"
        cover.write_bytes(b"\x89PNG fake")
        n = Notifier(address=self.address, covers=CoverCache(Path(self.tmp.name) / "cache"))
        n.track("Ludens", "Bring Me The Horizon", "Death Stranding: Timefall", cover.as_uri())
        n.wait_idle()
        n.track("Teardrops", "Bring Me The Horizon", "", "https://invalid.invalid/x.jpg")
        n.wait_idle()
        log = json.loads(self.ctl("org.freedesktop.Notifications", "/org/freedesktop/Notifications", "Log")[0])
        self.assertEqual(len(log), 2)
        self.assertEqual(log[0]["summary"], "Ludens")
        self.assertEqual(log[0]["image"], str(cover))
        self.assertEqual(log[0]["desktop"], "lurdens")
        self.assertEqual(log[1]["replaces"], log[0]["id"], "a nova notificação substitui a anterior")
        self.assertEqual(log[1]["image"], "")
        self.assertEqual(log[1]["icon"], "lurdens")
        n.stop()

    def test_notifications_coalesce_rapid_changes(self):
        from lurdens.notify import CoverCache, Notifier
        self.start("mock_desktop.py", "--no-kglobalaccel")
        n = Notifier(address=self.address, covers=CoverCache(Path(self.tmp.name) / "c"))
        n._q.put(("sync", threading.Event()))       # segura a fila para acumular
        for i in range(6):
            n.track(f"Faixa {i}", "A", "", "")
        n.wait_idle()
        log = json.loads(self.ctl("org.freedesktop.Notifications", "/org/freedesktop/Notifications", "Log")[0])
        self.assertLessEqual(len(log), 2)
        self.assertEqual(log[-1]["summary"], "Faixa 5")
        n.stop()

    def test_notifications_without_server(self):
        from lurdens.notify import Notifier
        n = Notifier(address=self.address)
        n.track("X", "Y", "", "")
        n.wait_idle()
        self.assertIn("ServiceUnknown", n.last_error)
        n.stop()

    def test_global_shortcuts(self):
        from lurdens.shortcuts import GlobalShortcuts
        taken = META | ALT | 0x42      # Meta+Alt+B já usado por "outro programa"
        self.start("mock_desktop.py", "--taken", str(taken))
        pressed, changes = [], []
        g = GlobalShortcuts(pressed.append, lambda: changes.append(1), address=self.address)
        g.start()
        g.wait_idle()
        self.assertTrue(g.available, g.status)
        self.assertEqual(g.keys["play-pause"], META | ALT | 0x50)
        self.assertEqual(g.keys["previous"], 0)
        self.assertIn("previous", g.conflicts)
        state = json.loads(self.ctl("org.kde.kglobalaccel", "/kglobalaccel", "State")[0])
        self.assertIn("lurdens/next", state["registered"])
        self.assertEqual(state["default"]["lurdens/next"], [META | ALT | 0x4E])

        self.ctl("org.kde.kglobalaccel", "/kglobalaccel", "Press", "ss", ("lurdens", "next"))
        self.ctl("org.kde.kglobalaccel", "/kglobalaccel", "Press", "ss", ("outroapp", "next"))
        self.assertTrue(self.wait_until(lambda: pressed == ["next"]))

        g.set_key("previous", META | ALT | 0x56)   # trocar no Lurdens
        g.wait_idle()
        self.assertEqual(g.keys["previous"], META | ALT | 0x56)
        self.assertNotIn("previous", g.conflicts)

        self.ctl("org.kde.kglobalaccel", "/kglobalaccel", "UserChange", "ssi", ("lurdens", "show", META | 0x4C))
        self.assertTrue(self.wait_until(lambda: g.keys["show"] == META | 0x4C), "troca feita no KDE é refletida")
        g.stop()

    def test_shortcuts_unavailable(self):
        from lurdens.shortcuts import GlobalShortcuts
        self.start("mock_desktop.py", "--no-kglobalaccel")
        g = GlobalShortcuts(lambda a: None, address=self.address)
        g.start()
        g.wait_idle()
        self.assertFalse(g.available)
        self.assertIn("kglobalaccel", g.status)
        g.stop()

    def test_sleep_timer_pauses_spotify(self):
        """Fluxo do temporizador: ao vencer, envia Pause pelo cliente MPRIS existente."""
        from lurdens.mpris import MprisClient
        self.start("mock_spotify.py", "--art-dir", "", "--play")
        states = []
        client = MprisClient(states.append, address=self.address)
        client.start()
        self.assertTrue(self.wait_until(lambda: states and states[-1].playing))
        c = FakeClock()
        timer = SleepTimer(clock=c)
        timer.start(15 * 60)
        c.t += 15 * 60
        if timer.poll():
            client.pause()
        self.assertTrue(self.wait_until(lambda: states[-1].status == "Paused"))
        calls = Connection(self.address)
        (log,) = calls.call("org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2",
                            "org.lurdens.MockControl", "Calls")
        calls.close()
        self.assertIn("Pause", log)
        self.assertNotIn("PlayPause", log)
        client.pause()                       # já pausado: não envia nada
        time.sleep(0.3)
        client.stop()

    def test_pause_with_spotify_closed(self):
        from lurdens.mpris import MprisClient
        client = MprisClient(lambda s: None, address=self.address)
        client.start()
        time.sleep(0.3)
        client.pause()                       # não pode travar nem lançar
        time.sleep(0.2)
        self.assertTrue(client._thread.is_alive())
        client.stop()


if __name__ == "__main__":
    unittest.main()
