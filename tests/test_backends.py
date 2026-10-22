"""Testes dos backends de reprodução (independentes de Qt e do sistema)."""

import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lurdens.backends import PlayerBackend, create_backend, current_os, next_loop_mode  # noqa: E402
from lurdens.backends.polling import PollingBackend  # noqa: E402
from lurdens.mpris import MprisClient  # noqa: E402
from lurdens.state import PlayerState  # noqa: E402


class FactoryTests(unittest.TestCase):
    def test_current_os(self):
        self.assertEqual(current_os("linux"), "linux")
        self.assertEqual(current_os("freebsd14"), "linux")
        self.assertEqual(current_os("win32"), "windows")
        self.assertEqual(current_os("darwin"), "macos")
        self.assertEqual(current_os("sunos5"), "other")

    def test_linux_uses_mpris(self):
        backend = create_backend(lambda s: None, platform="linux", address="unix:path=/nao/existe")
        self.assertIsInstance(backend, MprisClient)
        self.assertIsInstance(backend, PlayerBackend)
        self.assertEqual(backend.kind, "mpris")
        self.assertTrue(backend.label)


class LoopModeTests(unittest.TestCase):
    def test_full_cycle(self):
        modes = ("None", "Playlist", "Track")
        self.assertEqual(next_loop_mode("None", modes), "Playlist")
        self.assertEqual(next_loop_mode("Playlist", modes), "Track")
        self.assertEqual(next_loop_mode("Track", modes), "None")

    def test_reduced_cycle(self):
        modes = ("None", "Playlist")
        self.assertEqual(next_loop_mode("Playlist", modes), "None")
        # "Track" não existe neste backend: volta para o primeiro modo ativo
        self.assertEqual(next_loop_mode("Track", modes), "Playlist")
        self.assertEqual(next_loop_mode(None, modes), "Playlist")


# ------------------------------------------------------- PollingBackend
def playing_state(**kw) -> PlayerState:
    base = dict(status="Playing", track_id="t1", title="Faixa", artists=("Artista",), album="Álbum",
                length_us=200_000_000, can_control=True, can_play=True, can_pause=True,
                can_next=True, can_prev=True, can_seek=True, can_raise=True,
                volume=0.5, shuffle=False, loop_status="None")
    base.update(kw)
    return PlayerState(**base).with_position(kw.get("position_us", 10_000_000))


class FakePolling(PollingBackend):
    kind = "fake"
    label = "Falso"

    def __init__(self, on_state, **kw):
        super().__init__(on_state, interval=0.05, idle_interval=0.05, settle=0.05, **kw)
        self.snapshot = playing_state()
        self.open_error = None
        self.read_error = None
        self.sent = []
        self.lock = threading.Lock()

    def _open(self):
        if self.open_error:
            raise self.open_error

    def _read(self):
        if self.read_error:
            raise self.read_error
        snap = self.snapshot
        return None if snap is None else snap.with_position(snap.position_at())

    def _send(self, command, *args):
        with self.lock:
            self.sent.append((command, *args))


class PollingTests(unittest.TestCase):
    def setUp(self):
        self.states = []
        self.backend = FakePolling(self.states.append)

    def tearDown(self):
        self.backend.stop()

    def wait_for(self, cond, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cond():
                return True
            time.sleep(0.01)
        self.fail("condição não atingida a tempo")

    def test_connects_and_reads(self):
        self.backend.start()
        self.wait_for(lambda: self.backend.state.connected)
        st = self.backend.state
        self.assertTrue(st.bus_available)
        self.assertEqual(st.title, "Faixa")

    def test_position_drift_does_not_spam(self):
        self.backend.start()
        self.wait_for(lambda: self.backend.state.connected)
        before = len(self.states)
        time.sleep(0.4)          # várias leituras com a posição só avançando
        self.assertEqual(len(self.states), before)

    def test_external_seek_is_published(self):
        self.backend.start()
        self.wait_for(lambda: self.backend.state.connected)
        self.backend.snapshot = self.backend.snapshot.with_position(120_000_000)
        self.wait_for(lambda: abs(self.backend.state.position_at() - 120_000_000) < 1_000_000)

    def test_track_change_and_close(self):
        self.backend.start()
        self.wait_for(lambda: self.backend.state.connected)
        self.backend.snapshot = playing_state(track_id="t2", title="Outra")
        self.wait_for(lambda: self.backend.state.title == "Outra")
        self.backend.snapshot = None
        self.wait_for(lambda: not self.backend.state.connected)
        self.assertTrue(self.backend.state.bus_available)

    def test_service_unavailable_then_recovers(self):
        self.backend.open_error = OSError("sem serviço")
        self.backend.start()
        time.sleep(0.2)
        self.assertFalse(self.backend.state.connected)
        self.assertIn("sem serviço", self.backend.last_error)
        self.backend.open_error = None
        self.wait_for(lambda: self.backend.state.connected)
        self.assertEqual(self.backend.last_error, "")

    def test_transient_read_error_keeps_state(self):
        self.backend.start()
        self.wait_for(lambda: self.backend.state.connected)
        self.backend._read_errors = 0
        self.backend.read_error = RuntimeError("falha momentânea")
        self.wait_for(lambda: self.backend.last_error == "falha momentânea")
        self.backend.read_error = None
        time.sleep(0.2)
        self.assertTrue(self.backend.state.connected)

    def test_commands_are_sent_with_optimistic_state(self):
        self.backend.start()
        self.wait_for(lambda: self.backend.state.connected)
        self.backend.play_pause()
        self.wait_for(lambda: ("PlayPause",) in self.backend.sent)
        self.assertEqual(self.states[-1].status, "Paused")      # otimista
        self.backend.seek_to(30_000_000)
        self.backend.set_volume(1.7)
        self.backend.toggle_shuffle()
        self.backend.cycle_loop()
        self.backend.next()
        self.backend.raise_player()
        self.wait_for(lambda: ("Raise",) in self.backend.sent)
        self.assertIn(("SetPosition", 30_000_000), self.backend.sent)
        self.assertIn(("SetVolume", 1.0), self.backend.sent)
        self.assertIn(("SetShuffle", True), self.backend.sent)
        self.assertIn(("SetLoop", "Playlist"), self.backend.sent)
        self.assertIn(("Next",), self.backend.sent)

    def test_unsupported_features_send_nothing(self):
        self.backend.snapshot = playing_state(volume=None, shuffle=None, loop_status=None,
                                              can_seek=False, can_raise=False, status="Paused")
        self.backend.start()
        self.wait_for(lambda: self.backend.state.connected)
        for cmd in (lambda: self.backend.set_volume(0.3), self.backend.toggle_shuffle,
                    self.backend.cycle_loop, lambda: self.backend.seek_to(5), self.backend.raise_player,
                    self.backend.pause):      # pause só vale tocando
            cmd()
        self.backend.next()
        self.wait_for(lambda: ("Next",) in self.backend.sent)
        self.assertEqual(self.backend.sent, [("Next",)])

    def test_reduced_loop_modes(self):
        class TwoModes(FakePolling):
            loop_modes = ("None", "Playlist")
        b = TwoModes(self.states.append)
        b.snapshot = playing_state(loop_status="Playlist")
        b.start()
        try:
            self.wait_for(lambda: b.state.connected)
            b.cycle_loop()
            self.wait_for(lambda: b.sent)
            self.assertEqual(b.sent, [("SetLoop", "None")])
        finally:
            b.stop()

    def test_commands_without_spotify_are_ignored(self):
        self.backend.snapshot = None
        self.backend.start()
        self.wait_for(lambda: self.backend.state.bus_available)
        self.backend.play_pause()
        self.backend.next()
        time.sleep(0.15)
        self.assertEqual(self.backend.sent, [])

    def test_stop_without_start(self):
        b = FakePolling(lambda s: None)
        b.stop(timeout=0.1)       # não deve travar nem lançar


if __name__ == "__main__":
    unittest.main()
