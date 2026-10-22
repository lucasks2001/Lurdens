"""Backend do Windows (SMTC) com uma sessão de mídia simulada.

Roda em qualquer sistema: o pacote winrt não é necessário, porque o
gerenciador, a sessão e a leitura da capa são substituídos por objetos falsos
com a mesma forma da API projetada pelo PyWinRT.
"""

import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lurdens.backends.smtc import SmtcBackend, is_spotify_app_id  # noqa: E402

NOW = datetime(2026, 10, 22, 15, 0, 0, tzinfo=timezone.utc)


class FakeSession:
    def __init__(self, app_id="Spotify.exe"):
        self.source_app_user_model_id = app_id
        self.calls = []
        self.accept = True
        self.props = SimpleNamespace(title="Ludens", artist="Bring Me The Horizon",
                                     album_title="Death Stranding: Timefall", thumbnail=object())
        self.info = SimpleNamespace(
            playback_status=4, playback_rate=1.0, is_shuffle_active=False, auto_repeat_mode=2,
            controls=SimpleNamespace(is_play_enabled=True, is_pause_enabled=True, is_next_enabled=True,
                                     is_previous_enabled=True, is_playback_position_enabled=True))
        self.timeline = SimpleNamespace(start_time=timedelta(0), end_time=timedelta(minutes=4, seconds=32),
                                        position=timedelta(seconds=30), last_updated_time=NOW - timedelta(seconds=2))

    async def try_get_media_properties_async(self):
        return self.props

    def get_playback_info(self):
        return self.info

    def get_timeline_properties(self):
        return self.timeline

    def _op(self, name, *args):
        self.calls.append((name, *args))

        async def result():
            return self.accept
        return result()

    def try_toggle_play_pause_async(self):
        return self._op("toggle")

    def try_pause_async(self):
        return self._op("pause")

    def try_skip_next_async(self):
        return self._op("next")

    def try_skip_previous_async(self):
        return self._op("previous")

    def try_change_playback_position_async(self, ticks):
        return self._op("position", ticks)

    def try_change_shuffle_active_async(self, on):
        return self._op("shuffle", on)

    def try_change_auto_repeat_mode_async(self, mode):
        return self._op("repeat", int(mode))


class FakeManager:
    def __init__(self, sessions):
        self.sessions = sessions

    def get_sessions(self):
        return list(self.sessions)


class SmtcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.spotify = FakeSession()
        self.manager = FakeManager([FakeSession("Chrome"), self.spotify])
        self.thumb_reads = 0
        self.raised = 0

        async def factory():
            return self.manager

        async def thumbs(_ref):
            self.thumb_reads += 1
            return b"\xff\xd8capa"

        def raise_():
            self.raised += 1

        self.backend = SmtcBackend(lambda s: None, manager_factory=factory, thumbnail_reader=thumbs,
                                   open_uri=raise_, art_dir=Path(self.tmp.name), now=lambda: NOW)
        self.backend._open()

    def tearDown(self):
        self.backend._close()
        self.tmp.cleanup()

    def test_app_ids(self):
        self.assertTrue(is_spotify_app_id("Spotify.exe"))
        self.assertTrue(is_spotify_app_id("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"))
        self.assertFalse(is_spotify_app_id("Microsoft.ZuneMusic"))
        self.assertFalse(is_spotify_app_id(None))

    def test_reads_spotify_session_only(self):
        st = self.backend._read()
        self.assertEqual(st.title, "Ludens")
        self.assertEqual(st.artists, ("Bring Me The Horizon",))
        self.assertEqual(st.album, "Death Stranding: Timefall")
        self.assertEqual(st.status, "Playing")
        self.assertEqual(st.length_us, 272_000_000)
        self.assertEqual(st.bus_name, "Spotify.exe")
        self.assertIsNone(st.volume)                 # SMTC não tem volume
        self.assertIs(st.shuffle, False)
        self.assertEqual(st.loop_status, "Playlist")
        self.assertTrue(st.can_seek and st.can_raise)

    def test_position_is_advanced_from_last_update(self):
        st = self.backend._read()
        self.assertAlmostEqual(st.position_us, 32_000_000, delta=50_000)
        self.spotify.info.playback_status = 5          # pausado: não avança
        self.assertAlmostEqual(self.backend._read().position_us, 30_000_000, delta=50_000)
        self.spotify.info.playback_status = 4
        self.spotify.timeline.last_updated_time = datetime(1601, 1, 1, tzinfo=timezone.utc)
        self.assertAlmostEqual(self.backend._read().position_us, 30_000_000, delta=50_000)

    def test_cover_saved_once_per_track(self):
        st = self.backend._read()
        self.assertTrue(st.art_url.startswith("file:"))
        path = Path(self.tmp.name) / Path(st.art_url).name
        self.assertEqual(path.read_bytes(), b"\xff\xd8capa")
        self.backend._read()
        self.assertEqual(self.thumb_reads, 1)
        self.spotify.props = SimpleNamespace(title="Outra", artist="A", album_title="B", thumbnail=object())
        self.assertNotEqual(self.backend._read().art_url, st.art_url)
        self.assertEqual(self.thumb_reads, 2)

    def test_cover_arriving_late_is_retried(self):
        self.spotify.props.thumbnail = None
        self.assertEqual(self.backend._read().art_url, "")
        self.spotify.props.thumbnail = object()
        self.assertTrue(self.backend._read().art_url)

    def test_optional_fields_missing(self):
        self.spotify.info.is_shuffle_active = None
        self.spotify.info.auto_repeat_mode = None
        self.spotify.props.artist = ""
        st = self.backend._read()
        self.assertIsNone(st.shuffle)
        self.assertIsNone(st.loop_status)
        self.assertEqual(st.artists, ())

    def test_spotify_closed(self):
        self.manager.sessions = [FakeSession("Chrome")]
        self.assertIsNone(self.backend._read())

    def test_commands(self):
        b = self.backend
        b._send("PlayPause")
        b._send("Pause")
        b._send("Next")
        b._send("Previous")
        b._send("SetPosition", 45_000_000)
        b._send("SetShuffle", True)
        b._send("SetLoop", "Track")
        b._send("Raise")
        self.assertEqual(self.spotify.calls, [
            ("toggle",), ("pause",), ("next",), ("previous",), ("position", 450_000_000),
            ("shuffle", True), ("repeat", 1)])
        self.assertEqual(self.raised, 1)

    def test_rejected_command_raises(self):
        self.spotify.accept = False
        with self.assertRaises(RuntimeError):
            self.backend._send("Next")
        with self.assertRaises(ValueError):
            self.backend._send("SetVolume", 0.5)

    def test_runs_in_background_thread(self):
        states = []

        async def factory():
            return self.manager

        async def thumbs(_ref):
            return b""

        b = SmtcBackend(states.append, manager_factory=factory, thumbnail_reader=thumbs,
                        art_dir=Path(self.tmp.name), interval=0.05, settle=0.05)
        b.start()
        try:
            for _ in range(200):
                if b.state.connected:
                    break
                time.sleep(0.01)
            self.assertTrue(b.state.connected)
            self.assertEqual(b.state.title, "Ludens")
            b.next()
            for _ in range(200):
                if ("next",) in self.spotify.calls:
                    break
                time.sleep(0.01)
            self.assertIn(("next",), self.spotify.calls)
        finally:
            b.stop()


if __name__ == "__main__":
    unittest.main()
