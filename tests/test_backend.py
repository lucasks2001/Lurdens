"""Testes do backend (sem interface gráfica).

Executar:  python3 -m unittest discover -s tests -v

Os testes de integração sobem um dbus-daemon privado e um Spotify simulado
(tests/mock_spotify.py). Eles não tocam no barramento real da sessão.
O interpretador do mock pode ser trocado com LURDENS_MOCK_PYTHON.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lurdens.dbus.wire import (Connection, DBusError, Message, ObjectPath, Variant,  # noqa: E402
                               marshal_body, parse_signature, unmarshal_body, METHOD_CALL)
from lurdens.state import (PlayerState, apply_player_properties, format_time,  # noqa: E402
                           is_spotify_bus_name, next_loop_status, normalize_art_url)
from lurdens.settings import SettingsStore  # noqa: E402
from lurdens.launcher import detect_spotify  # noqa: E402
from lurdens.kwin import build_script  # noqa: E402

MOCK = ROOT / "tests" / "mock_spotify.py"
MOCK_PY = os.environ.get("LURDENS_MOCK_PYTHON", sys.executable)


def _mock_available() -> bool:
    if not shutil.which("dbus-daemon"):
        return False
    r = subprocess.run([MOCK_PY, "-c", "import dbus, dbus.service, dbus.mainloop.glib; from gi.repository import GLib"],
                       capture_output=True)
    return r.returncode == 0


# ---------------------------------------------------------------- unidades
class WireTests(unittest.TestCase):
    def test_signature_parsing(self):
        self.assertEqual(parse_signature("sa{sv}as"), ["s", ("a", ("{", "s", "v")), ("a", "s")])
        self.assertEqual(parse_signature("(ix)"), [("(", ["i", "x"])])
        with self.assertRaises(ValueError):
            parse_signature("a{sv")

    def test_roundtrip_complex(self):
        sig = "sa{sv}asbdxtuyo"
        args = ["org.mpris.MediaPlayer2.Player",
                {"Volume": Variant("d", 0.5), "Shuffle": Variant("b", True),
                 "Metadata": Variant("a{sv}", {"xesam:artist": Variant("as", ["A", "B"]),
                                               "mpris:length": Variant("t", 2**40)})},
                ["x", "yz"], True, 3.25, -7, 2**63, 42, 255, ObjectPath("/com/spotify/track/1")]
        data = marshal_body(sig, args)
        out = unmarshal_body(sig, data)
        self.assertEqual(out[0], args[0])
        self.assertEqual(out[1], {"Volume": 0.5, "Shuffle": True,
                                  "Metadata": {"xesam:artist": ["A", "B"], "mpris:length": 2**40}})
        self.assertEqual(out[2:], args[2:])

    def test_empty_array_alignment(self):
        # array vazio de structs ainda precisa do padding até 8
        data = marshal_body("ya(xx)", [1, []])
        self.assertEqual(len(data), 8)
        self.assertEqual(unmarshal_body("ya(xx)", data), [1, []])

    def test_message_roundtrip(self):
        m = Message(METHOD_CALL, serial=7, destination="org.x", path="/a/b", interface="i.f",
                    member="M", signature="sv", body=["k", Variant("i", 3)])
        enc = m.encode()
        self.assertEqual(len(enc) % 8, 0 if not m.body else len(enc) % 8)
        dec = Message.decode(enc)
        self.assertEqual((dec.serial, dec.destination, dec.path, dec.member, dec.body),
                         (7, "org.x", "/a/b", "M", ["k", 3]))

    def test_big_endian_decode(self):
        import struct
        body = struct.pack(">I", 3) + b"abc\0"
        field = bytes([8, 1]) + b"g\0" + bytes([1]) + b"s\0"   # (SIGNATURE, variant g "s")
        head = b"B" + bytes([4, 0, 1]) + struct.pack(">III", len(body), 9, len(field))
        data = head + field + b"\0" + body                    # padding até 24
        msg = Message.decode(data)
        self.assertEqual((msg.serial, msg.signature, msg.body), (9, "s", ["abc"]))


class StateTests(unittest.TestCase):
    def test_art_url_normalization(self):
        self.assertEqual(normalize_art_url("https://open.spotify.com/image/abc"), "https://i.scdn.co/image/abc")
        self.assertEqual(normalize_art_url("/tmp/x.png"), "file:///tmp/x.png")
        self.assertEqual(normalize_art_url("spotify:image:x"), "")
        self.assertEqual(normalize_art_url(""), "")

    def test_bus_names(self):
        self.assertTrue(is_spotify_bus_name("org.mpris.MediaPlayer2.spotify"))
        self.assertTrue(is_spotify_bus_name("org.mpris.MediaPlayer2.spotify.instance123"))
        self.assertFalse(is_spotify_bus_name("org.mpris.MediaPlayer2.spotifyd"))
        self.assertFalse(is_spotify_bus_name("org.mpris.MediaPlayer2.vlc"))

    def test_apply_and_interpolate(self):
        s = PlayerState(connected=True)
        s = apply_player_properties(s, {
            "PlaybackStatus": "Playing", "Position": 10_000_000,
            "Metadata": {"mpris:trackid": "/t/1", "xesam:title": "T", "xesam:artist": ["A", "B"],
                         "mpris:length": 20_000_000, "mpris:artUrl": "https://open.spotify.com/image/z"},
            "CanSeek": True, "Volume": 1.4})
        self.assertEqual(s.artists, ("A", "B"))
        self.assertEqual(s.art_url, "https://i.scdn.co/image/z")
        self.assertEqual(s.volume, 1.0)
        self.assertIsNone(s.shuffle)
        self.assertTrue(s.has_track)
        later = s.position_ts + 2.5
        self.assertAlmostEqual(s.position_at(later), 12_500_000, delta=1000)
        self.assertEqual(s.position_at(s.position_ts + 100), 20_000_000)  # limitado à duração
        paused = apply_player_properties(s, {"PlaybackStatus": "Paused"})
        self.assertGreaterEqual(paused.position_us, 10_000_000)
        t2 = apply_player_properties(paused, {"Metadata": {"mpris:trackid": "/t/2", "xesam:title": "U"}})
        self.assertEqual(t2.position_us, 0)
        self.assertEqual(t2.artists, ())

    def test_loop_cycle_and_time(self):
        self.assertEqual(next_loop_status("None"), "Playlist")
        self.assertEqual(next_loop_status("Playlist"), "Track")
        self.assertEqual(next_loop_status("Track"), "None")
        self.assertEqual(format_time(65_000_000), "1:05")
        self.assertEqual(format_time(3_725_000_000), "1:02:05")


class SettingsTests(unittest.TestCase):
    def test_persist_and_validate(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "settings.json"
            s = SettingsStore(p)
            self.assertEqual(s.get("theme"), "dark")
            self.assertEqual(s.get("window")["width"], 420)
            s.set("theme", "light")
            s.set("alwaysOnTop", True)
            s.set("window", {"width": 100, "height": 900, "x": 10, "y": "bad", "maximized": True})
            with self.assertRaises(ValueError):
                s.set("theme", "neon")
            s2 = SettingsStore(p)
            self.assertEqual(s2.get("theme"), "light")
            self.assertTrue(s2.get("alwaysOnTop"))
            self.assertEqual(s2.get("window"), {"width": 320, "height": 900, "x": 10, "y": None, "maximized": True})

    def test_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text("{oops")
            s = SettingsStore(p)
            self.assertEqual(s.get("theme"), "dark")
            self.assertTrue(s.load_error)
            p.write_text(json.dumps({"theme": 5, "trayEnabled": False}))
            s = SettingsStore(p)
            self.assertEqual(s.get("theme"), "dark")
            self.assertFalse(s.get("trayEnabled"))


class LauncherTests(unittest.TestCase):
    def test_detection_order(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            which = {"spotify": "/usr/bin/spotify", "flatpak": "/usr/bin/flatpak"}.get
            self.assertEqual(detect_spotify(home, which).kind, "rpm")
            (home / ".local/share/flatpak/app/com.spotify.Client").mkdir(parents=True)
            only_flatpak = {"flatpak": "/usr/bin/flatpak",
                            "spotify": str(home / ".local/share/flatpak/exports/bin/spotify")}.get
            inst = detect_spotify(home, only_flatpak)
            self.assertEqual(inst.kind, "flatpak")
            self.assertEqual(inst.command, ("flatpak", "run", "com.spotify.Client"))
        self.assertEqual(detect_spotify(Path("/nonexistent"), lambda _n: None).kind, "none")

    def test_kwin_script(self):
        js = build_script(1234, True)
        self.assertIn("w.pid === 1234", js)
        self.assertIn("keepAbove = true", js)


class VersionTests(unittest.TestCase):
    def test_changelog_matches_version(self):
        from lurdens import __version__
        from lurdens.changelog import CHANGELOG
        self.assertEqual(CHANGELOG[0]["version"], __version__,
                         "atualize lurdens/changelog.py ao mudar a versão")
        for entry in CHANGELOG:
            self.assertTrue(entry["changes"] and entry["date"])

    def test_last_seen_version_persists(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            s = SettingsStore(p)
            self.assertEqual(s.get("lastSeenVersion"), "")
            s.set("lastSeenVersion", "1.1.0")
            self.assertEqual(SettingsStore(p).get("lastSeenVersion"), "1.1.0")


# ------------------------------------------------------------- integração
@unittest.skipUnless(_mock_available(), "dbus-daemon ou dbus-python/GLib indisponíveis para o mock")
class MprisIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.daemon = subprocess.Popen(
            ["dbus-daemon", "--session", "--nofork", "--print-address=1",
             f"--address=unix:dir={self.tmp.name}"],
            stdout=subprocess.PIPE, text=True)
        self.address = self.daemon.stdout.readline().strip()
        self.env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=self.address)
        self.mocks = []
        self.states = []
        self.cv = threading.Condition()

    def tearDown(self):
        if getattr(self, "client", None):
            self.client.stop()
        for m in self.mocks:
            m.kill()
            m.wait()
            m.stdout.close()
        self.daemon.kill()
        self.daemon.wait()
        self.daemon.stdout.close()
        self.tmp.cleanup()

    # -- auxiliares -------------------------------------------------------
    def start_mock(self, *args):
        p = subprocess.Popen([MOCK_PY, str(MOCK), "--art-dir", "", *args], env=self.env,
                             stdout=subprocess.PIPE, text=True)
        line = p.stdout.readline()
        self.assertIn("mock pronto", line)
        self.mocks.append(p)
        return p

    def start_client(self):
        from lurdens.mpris import MprisClient

        def on_state(st):
            with self.cv:
                self.states.append(st)
                self.cv.notify_all()
        self.client = MprisClient(on_state, address=self.address, reconnect_delay=0.3, resync_interval=0.5)
        self.client.start()

    def wait_for(self, pred, timeout=5.0, what="estado"):
        deadline = time.monotonic() + timeout
        with self.cv:
            while True:
                if self.states and pred(self.states[-1]):
                    return self.states[-1]
                left = deadline - time.monotonic()
                if left <= 0:
                    last = self.states[-1] if self.states else None
                    self.fail(f"tempo esgotado esperando {what}; último: {last}")
                self.cv.wait(left)

    def ctl(self, member, sig="", args=()):
        c = Connection(self.address)
        try:
            return c.call("org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2",
                          "org.lurdens.MockControl", member, sig, args)
        finally:
            c.close()

    def calls(self):
        return self.ctl("Calls")[0]

    # -- testes -------------------------------------------------------------
    def test_wire_against_real_daemon(self):
        c = Connection(self.address)
        self.assertTrue(c.unique_name.startswith(":"))
        (names,) = c.call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames")
        self.assertIn("org.freedesktop.DBus", names)
        with self.assertRaises(DBusError) as cm:
            c.call("org.nao.existe", "/", "x.y", "Z")
        self.assertIn("ServiceUnknown", cm.exception.name)
        c.close()

    def test_full_flow(self):
        self.start_mock()
        self.start_client()
        st = self.wait_for(lambda s: s.has_track, what="faixa inicial")
        self.assertEqual(st.title, "Hachura em Diagonal")
        self.assertEqual(st.artists, ("Trio Nanquim",))
        self.assertEqual(st.length_us, 185_000_000)
        self.assertEqual(st.identity, "Spotify")
        self.assertEqual(st.status, "Paused")
        self.assertEqual(st.volume, 0.7)
        self.assertFalse(st.shuffle)
        self.assertEqual(st.loop_status, "None")

        self.client.play_pause()
        self.wait_for(lambda s: s.status == "Playing", what="tocando")
        self.client.next()
        st = self.wait_for(lambda s: s.track_id.endswith("0002"), what="próxima faixa")
        self.assertEqual(st.artists, ("Pontilhismo", "Cruzada Feat. Trama"))
        self.client.previous()
        self.wait_for(lambda s: s.track_id.endswith("0001"), what="faixa anterior")

        self.client.seek_to(60_000_000)
        st = self.wait_for(lambda s: abs(s.position_at() - 60_000_000) < 2_000_000, what="seek")
        time.sleep(0.8)
        real = self.ctl("RealPosition")[0]
        self.assertLess(abs(real - 60_000_000), 3_000_000)
        self.assertLess(abs(self.client.state.position_at() - real), 1_500_000)

        self.client.set_volume(0.25)
        self.wait_for(lambda s: s.volume == 0.25, what="volume")
        self.client.toggle_shuffle()
        self.wait_for(lambda s: s.shuffle is True, what="shuffle")
        self.client.cycle_loop()
        self.wait_for(lambda s: s.loop_status == "Playlist", what="repeat")
        time.sleep(0.3)
        c = self.calls()
        for expected in ("PlayPause", "Next", "Previous", "SetPosition:/com/spotify/track/0001:60000000",
                         "Set:Volume:0.25", "Set:Shuffle:1", "Set:LoopStatus:Playlist"):
            self.assertIn(expected, c)

    def test_external_changes_are_reflected(self):
        self.start_mock()
        self.start_client()
        self.wait_for(lambda s: s.has_track)
        self.ctl("SetStatus", "s", ("Playing",))
        self.wait_for(lambda s: s.status == "Playing", what="play externo")
        self.ctl("ExternalNext")
        self.wait_for(lambda s: s.track_id.endswith("0002"), what="troca externa")
        self.ctl("ExternalSeek", "x", (90_000_000,))
        self.wait_for(lambda s: abs(s.position_at() - 90_000_000) < 2_000_000, what="seek externo")

    def test_spotify_started_later_and_restarted(self):
        self.start_client()
        st = self.wait_for(lambda s: s.bus_available, what="barramento")
        self.assertFalse(st.connected)
        mock = self.start_mock()
        self.wait_for(lambda s: s.has_track, what="Spotify aberto depois")
        mock.kill()
        mock.wait()
        self.wait_for(lambda s: s.bus_available and not s.connected, what="Spotify fechado")
        self.start_mock("--play")
        st = self.wait_for(lambda s: s.has_track and s.playing, what="Spotify reiniciado")

    def test_legacy_player_without_optional_features(self):
        self.start_mock("--legacy")
        self.start_client()
        st = self.wait_for(lambda s: s.has_track)
        self.assertIsNone(st.volume)
        self.assertIsNone(st.shuffle)
        self.assertIsNone(st.loop_status)
        self.client.set_volume(0.1)
        self.client.toggle_shuffle()
        self.client.cycle_loop()
        self.client.play_pause()
        self.wait_for(lambda s: s.playing)
        self.assertFalse([c for c in self.calls() if c.startswith("Set:")])

    def test_instance_suffix_name(self):
        self.start_mock("--name", "instance4242")
        self.start_client()
        st = self.wait_for(lambda s: s.has_track)
        self.assertEqual(st.bus_name, "org.mpris.MediaPlayer2.spotify.instance4242")

    def test_bus_loss_and_reconnect(self):
        self.start_mock()
        self.start_client()
        self.wait_for(lambda s: s.has_track)
        self.daemon.kill()
        self.daemon.wait()
        self.wait_for(lambda s: not s.bus_available, what="perda do barramento")
        # comandos sem barramento não podem travar nem lançar exceções
        self.client.play_pause()
        self.client.seek_to(1)
        self.assertTrue(self.client._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
