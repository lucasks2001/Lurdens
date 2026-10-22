"""Testes dos backends de reprodução (independentes de Qt e do sistema)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lurdens.backends import PlayerBackend, create_backend, current_os, next_loop_mode  # noqa: E402
from lurdens.mpris import MprisClient  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
