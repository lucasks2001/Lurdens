"""Integrações que variam por sistema: pastas, autostart e abertura do Spotify."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lurdens import autostart, paths  # noqa: E402
from lurdens.launcher import detect_spotify  # noqa: E402

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


# ------------------------------------------------------------------ autostart


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ, KEY_SET_VALUE, REG_SZ = 1, 2, 1

    def __init__(self):
        self.values = {}
        self.open_keys = 0

    def OpenKey(self, root, path, reserved, access):
        if path != autostart.RUN_KEY:
            raise FileNotFoundError(path)
        self.open_keys += 1
        return path

    def CreateKeyEx(self, root, path, reserved, access):
        self.open_keys += 1
        return path

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]

    def CloseKey(self, key):
        self.open_keys -= 1


class AutostartPlatformTests(unittest.TestCase):
    def test_windows_registry(self):
        reg = FakeWinreg()
        self.assertFalse(autostart._win_is_enabled(reg))
        cmd = autostart._win_enable(reg, argv=[r"C:\Program Files\Lurdens\Lurdens.exe"])
        self.assertEqual(cmd, r'"C:\Program Files\Lurdens\Lurdens.exe" --autostart')
        self.assertEqual(reg.values["Lurdens"], cmd)
        self.assertTrue(autostart._win_is_enabled(reg))
        autostart._win_disable(reg)
        autostart._win_disable(reg)                    # idempotente
        self.assertFalse(autostart._win_is_enabled(reg))
        self.assertEqual(reg.open_keys, 0)             # toda chave aberta foi fechada

    def test_macos_launch_agent(self):
        import plistlib
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            self.assertFalse(autostart._mac_is_enabled(home))
            path = autostart._mac_enable(home, argv=["/Applications/Lurdens.app/Contents/MacOS/Lurdens"])
            self.assertEqual(path, home / "Library/LaunchAgents/io.github.lucasks2001.lurdens.plist")
            with open(path, "rb") as fh:
                data = plistlib.load(fh)
            self.assertEqual(data["ProgramArguments"][-1], "--autostart")
            self.assertTrue(data["RunAtLoad"])
            self.assertTrue(autostart._mac_is_enabled(home))
            data["Disabled"] = True                     # desligado por fora
            with open(path, "wb") as fh:
                plistlib.dump(data, fh)
            self.assertFalse(autostart._mac_is_enabled(home))
            autostart._mac_disable(home)
            autostart._mac_disable(home)
            self.assertFalse(path.exists())

    def test_launcher_argv_from_source(self):
        with mock.patch.dict(os.environ, {"LURDENS_LAUNCHER": ""}), \
                mock.patch.object(autostart.shutil, "which", return_value=None):
            argv = autostart.launcher_argv()
        self.assertEqual(argv[1], "-c")
        self.assertIn("from lurdens.__main__ import run", argv[2])

    def test_launcher_argv_frozen(self):
        with mock.patch.dict(os.environ, {"LURDENS_LAUNCHER": ""}), \
                mock.patch.object(autostart.sys, "frozen", True, create=True), \
                mock.patch.object(autostart.sys, "executable", "/x/Lurdens"):
            self.assertEqual(autostart.launcher_argv(), ["/x/Lurdens"])

    def test_location(self):
        self.assertIn("CurrentVersion\\Run", autostart.location("windows"))
        self.assertTrue(autostart.location("macos").endswith(".plist"))
        self.assertTrue(autostart.location("linux").endswith("lurdens.desktop"))


# ------------------------------------------------------------ abrir o Spotify
class LauncherPlatformTests(unittest.TestCase):
    def test_windows_installer_then_store(self):
        with tempfile.TemporaryDirectory() as d:
            roaming, local = Path(d) / "Roaming", Path(d) / "Local"
            env = {"APPDATA": str(roaming), "LOCALAPPDATA": str(local)}
            self.assertEqual(detect_spotify(Path(d), os_name="windows", env=env).kind, "none")
            alias = local / "Microsoft" / "WindowsApps" / "Spotify.exe"
            alias.parent.mkdir(parents=True)
            alias.touch()
            store = detect_spotify(Path(d), os_name="windows", env=env)
            self.assertEqual((store.kind, store.command), ("store", (str(alias),)))
            exe = roaming / "Spotify" / "Spotify.exe"
            exe.parent.mkdir(parents=True)
            exe.touch()
            self.assertEqual(detect_spotify(Path(d), os_name="windows", env=env).kind, "windows")

    def test_macos(self):
        found = detect_spotify(Path("/Users/u"), os_name="macos", mac_finder=lambda h: "/Applications/Spotify.app")
        self.assertEqual(found.command, ("open", "-a", "/Applications/Spotify.app"))
        self.assertEqual(detect_spotify(Path("/Users/u"), os_name="macos", mac_finder=lambda h: "").kind, "none")


if __name__ == "__main__":
    unittest.main()
