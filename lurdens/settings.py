"""Configurações persistentes (settings.json na pasta de configuração do sistema; veja paths.py)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import paths

DEFAULTS: dict = {
    "theme": "dark",              # dark | light | auto
    "alwaysOnTop": False,
    "launchSpotifyOnStart": False,
    "trayEnabled": True,
    "startMinimized": False,      # só tem efeito com a bandeja ativa
    "closeToTray": False,
    "compactMode": False,         # mini player horizontal
    "lastSeenVersion": "",        # última versão aberta em "Novidades"
    "notifyTracks": True,         # notificação do KDE ao trocar de faixa
    "historyPersist": False,      # histórico só em memória por padrão
    "usageTracking": True,        # registra o tempo de uso do dia (local)
    "window": {"width": 420, "height": 720, "x": None, "y": None, "maximized": False},
    "compactWindow": {"width": 420, "height": 184},
}

_VALID = {
    "theme": lambda v: v in ("dark", "light", "auto"),
    "alwaysOnTop": lambda v: isinstance(v, bool),
    "launchSpotifyOnStart": lambda v: isinstance(v, bool),
    "trayEnabled": lambda v: isinstance(v, bool),
    "startMinimized": lambda v: isinstance(v, bool),
    "closeToTray": lambda v: isinstance(v, bool),
    "compactMode": lambda v: isinstance(v, bool),
    "lastSeenVersion": lambda v: isinstance(v, str) and len(v) < 32,
    "notifyTracks": lambda v: isinstance(v, bool),
    "historyPersist": lambda v: isinstance(v, bool),
    "usageTracking": lambda v: isinstance(v, bool),
}

MIN_SIZE = (320, 160)


def config_dir() -> Path:
    return paths.config_dir()


def _clean_geometry(raw, default: dict) -> dict:
    out = dict(default)
    if not isinstance(raw, dict):
        return out
    for key in ("width", "height"):
        v = raw.get(key)
        if isinstance(v, int) and not isinstance(v, bool):
            out[key] = max(MIN_SIZE[0] if key == "width" else MIN_SIZE[1], min(v, 10000))
    for key in ("x", "y"):
        v = raw.get(key)
        out[key] = v if isinstance(v, int) and not isinstance(v, bool) and -20000 < v < 20000 else None
    if "maximized" in out:
        out["maximized"] = bool(raw.get("maximized", False))
    return out


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else config_dir() / "settings.json"
        self.data = json.loads(json.dumps(DEFAULTS))
        self.load_error = ""
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            self.load_error = f"configurações ilegíveis, usando padrões ({exc})"
            return
        if not isinstance(raw, dict):
            return
        for key, check in _VALID.items():
            if key in raw and check(raw[key]):
                self.data[key] = raw[key]
        self.data["window"] = _clean_geometry(raw.get("window"), DEFAULTS["window"])
        self.data["compactWindow"] = _clean_geometry(raw.get("compactWindow"), DEFAULTS["compactWindow"])

    def get(self, key: str):
        return self.data[key]

    def set(self, key: str, value) -> bool:
        if key in _VALID:
            if not _VALID[key](value):
                raise ValueError(f"valor inválido para {key}: {value!r}")
        elif key in ("window", "compactWindow"):
            value = _clean_geometry(value, DEFAULTS[key])
        else:
            raise KeyError(key)
        if self.data.get(key) == value:
            return False
        self.data[key] = value
        self.save()
        return True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".settings-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
