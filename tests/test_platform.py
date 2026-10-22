"""Integrações que variam por sistema: pastas, autostart e abertura do Spotify."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lurdens import paths  # noqa: E402

XDG = ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME")


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in XDG + ("APPDATA", "LOCALAPPDATA")}
    env.update(extra)
    return mock.patch.dict(os.environ, env, clear=True)


class PathTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.gettempdir()) / "casa"
        p = mock.patch.object(paths, "_home", return_value=self.home)
        p.start()
        self.addCleanup(p.stop)

    def test_linux(self):
        with clean_env():
            self.assertEqual(paths.config_dir("linux"), self.home / ".config" / "lurdens")
            self.assertEqual(paths.state_dir("linux"), self.home / ".local" / "state" / "lurdens")
            self.assertEqual(paths.cache_dir("linux"), self.home / ".cache" / "lurdens")

    def test_windows(self):
        with clean_env(APPDATA=r"C:\U\AppData\Roaming", LOCALAPPDATA=r"C:\U\AppData\Local"):
            self.assertEqual(paths.config_dir("windows"), Path(r"C:\U\AppData\Roaming") / "Lurdens")
            self.assertEqual(paths.state_dir("windows"), Path(r"C:\U\AppData\Local") / "Lurdens" / "state")
            self.assertEqual(paths.cache_dir("windows"), Path(r"C:\U\AppData\Local") / "Lurdens" / "cache")
        with clean_env():          # sem as variáveis: cai no perfil do usuário
            self.assertEqual(paths.config_dir("windows"), self.home / "AppData" / "Roaming" / "Lurdens")

    def test_macos(self):
        with clean_env():
            support = self.home / "Library" / "Application Support" / "Lurdens"
            self.assertEqual(paths.config_dir("macos"), support)
            self.assertEqual(paths.state_dir("macos"), support / "state")
            self.assertEqual(paths.cache_dir("macos"), self.home / "Library" / "Caches" / "Lurdens")

    def test_xdg_overrides_everywhere(self):
        with clean_env(XDG_CONFIG_HOME="/t/c", XDG_STATE_HOME="/t/s", XDG_CACHE_HOME="/t/k"):
            for os_name in ("linux", "windows", "macos"):
                self.assertEqual(paths.config_dir(os_name), Path("/t/c/lurdens"))
                self.assertEqual(paths.state_dir(os_name), Path("/t/s/lurdens"))
                self.assertEqual(paths.cache_dir(os_name), Path("/t/k/lurdens"))


if __name__ == "__main__":
    unittest.main()
