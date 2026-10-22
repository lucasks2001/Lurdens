"""Backend do macOS (AppleScript) com o osascript simulado.

Roda em qualquer sistema: o executor de scripts é substituído por uma
função que devolve respostas no formato de READ_SCRIPT e registra os
comandos enviados.
"""

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lurdens.backends.applescript import (SEP, AppleScriptBackend, READ_SCRIPT,  # noqa: E402
                                          find_spotify_app, parse_state)

PLAYING = SEP.join(["playing", "83,5", "64", "false", "true", "spotify:track:abc", "Ludens",
                    "Bring Me The Horizon", "Death Stranding: Timefall",
                    "https://i.scdn.co/image/ab67616d0000b273", "272000"])


class ParseTests(unittest.TestCase):
    def test_full_state(self):
        st = parse_state(PLAYING)
        self.assertEqual(st.status, "Playing")
        self.assertEqual(st.title, "Ludens")
        self.assertEqual(st.artists, ("Bring Me The Horizon",))
        self.assertEqual(st.track_id, "spotify:track:abc")
        self.assertEqual(st.length_us, 272_000_000)
        self.assertEqual(st.position_us, 83_500_000)     # vírgula decimal (locale pt_BR)
        self.assertAlmostEqual(st.volume, 0.64)
        self.assertIs(st.shuffle, False)
        self.assertEqual(st.loop_status, "Playlist")
        self.assertTrue(st.art_url.startswith("https://i.scdn.co/"))
        self.assertTrue(st.can_seek and st.can_next and st.can_raise)

    def test_dot_decimal_and_paused(self):
        out = PLAYING.replace("playing", "paused").replace("83,5", "12.25")
        st = parse_state(out)
        self.assertEqual(st.status, "Paused")
        self.assertEqual(st.position_us, 12_250_000)

    def test_not_running(self):
        self.assertIsNone(parse_state("NOT_RUNNING"))

    def test_no_current_track(self):
        st = parse_state(SEP.join(["stopped", "0", "50", "false", "false"]))
        self.assertEqual(st.status, "Stopped")
        self.assertFalse(st.title)
        self.assertFalse(st.can_play or st.can_seek)
        self.assertEqual(st.loop_status, "None")

    def test_missing_values(self):
        st = parse_state(SEP.join(["playing", "missing value", "missing value", "?", "?"]))
        self.assertIsNone(st.volume)
        self.assertIsNone(st.shuffle)
        self.assertIsNone(st.loop_status)
        self.assertEqual(st.position_us, 0)

    def test_position_clamped_to_length(self):
        st = parse_state(PLAYING.replace("83,5", "999"))
        self.assertEqual(st.position_us, 272_000_000)

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            parse_state("algo estranho")


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.scripts = []
        self.reply = PLAYING
        self.installed = "/Applications/Spotify.app"

        def runner(script):
            self.scripts.append(script)
            return self.reply if script == READ_SCRIPT else ""

        self.backend = AppleScriptBackend(lambda s: None, runner=runner, finder=lambda: self.installed)

    def test_not_installed(self):
        self.installed = ""
        with self.assertRaises(RuntimeError):
            self.backend._open()
        self.assertEqual(self.scripts, [])      # nenhum script sem o app (evita o diálogo do macOS)

    def test_read(self):
        self.backend._open()
        self.assertEqual(self.backend._read().title, "Ludens")
        self.reply = "NOT_RUNNING"
        self.assertIsNone(self.backend._read())

    def test_commands_are_guarded(self):
        b = self.backend
        for cmd, args, expected in [
            ("PlayPause", (), "to playpause"),
            ("Pause", (), "to pause"),
            ("Next", (), "to next track"),
            ("Previous", (), "to previous track"),
            ("SetPosition", (90_500_000,), "to set player position to 90.500"),
            ("SetVolume", (0.42,), "to set sound volume to 42"),
            ("SetShuffle", (True,), "to set shuffling to true"),
            ("SetLoop", ("Playlist",), "to set repeating to true"),
            ("SetLoop", ("None",), "to set repeating to false"),
            ("Raise", (), "to activate"),
        ]:
            b._send(cmd, *args)
            script = self.scripts[-1]
            self.assertIn(expected, script)
            self.assertTrue(script.startswith('if application id "com.spotify.client" is running'),
                            "comandos nunca podem abrir o Spotify sozinhos")
        with self.assertRaises(ValueError):
            b._send("Desconhecido")

    def test_loop_cycle_is_on_off(self):
        self.assertEqual(self.backend.loop_modes, ("None", "Playlist"))

    def test_background_thread(self):
        states = []
        b = AppleScriptBackend(states.append, runner=lambda s: PLAYING if s == READ_SCRIPT else "",
                               finder=lambda: "/Applications/Spotify.app", interval=0.05, settle=0.05)
        b.start()
        try:
            for _ in range(200):
                if b.state.connected:
                    break
                time.sleep(0.01)
            self.assertTrue(b.state.connected)
            self.assertEqual(b.state.title, "Ludens")
        finally:
            b.stop()


class FinderTests(unittest.TestCase):
    def test_user_applications_folder(self):
        with tempfile.TemporaryDirectory() as d:
            app = Path(d) / "Applications" / "Spotify.app"
            app.mkdir(parents=True)

            def no_mdfind(*a, **k):
                raise AssertionError("não deveria consultar o Spotlight")
            found = find_spotify_app(home=Path(d), run=no_mdfind)
            if not Path("/Applications/Spotify.app").exists():
                self.assertEqual(found, str(app))

    def test_spotlight_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            def mdfind(*a, **k):
                return subprocess.CompletedProcess(a, 0, stdout="/Volumes/X/Spotify.app\n", stderr="")
            if not Path("/Applications/Spotify.app").exists():
                self.assertEqual(find_spotify_app(home=Path(d), run=mdfind), "/Volumes/X/Spotify.app")

    def test_nothing_found(self):
        with tempfile.TemporaryDirectory() as d:
            def missing(*a, **k):
                raise FileNotFoundError("mdfind")
            if not Path("/Applications/Spotify.app").exists():
                self.assertEqual(find_spotify_app(home=Path(d), run=missing), "")


if __name__ == "__main__":
    unittest.main()
