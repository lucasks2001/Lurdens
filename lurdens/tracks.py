"""Detecção de novas reproduções e histórico da sessão.

Um único detector, alimentado pelo mesmo PlayerState que a interface usa,
decide quando começou uma nova reprodução. Histórico e notificações consomem
o mesmo evento, evitando mecanismos paralelos de acompanhamento.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .state import PlayerState

REPLAY_END_MARGIN_US = 8_000_000     # "estava no fim" = últimos 8 s
REPLAY_START_MARGIN_US = 4_000_000   # "voltou ao começo" = primeiros 4 s


def is_ad(state: PlayerState) -> bool:
    tid = state.track_id or ""
    return "/ad/" in tid or tid.startswith("spotify:ad:")


@dataclass(frozen=True)
class PlayEvent:
    track_id: str
    title: str
    artist: str
    album: str
    art_url: str
    started_at: float           # epoch (s)
    initial: bool               # já tocava quando o Lurdens conectou

    def time_label(self) -> str:
        return datetime.fromtimestamp(self.started_at).strftime("%H:%M")


class PlayDetector:
    """Emite um PlayEvent por entrada de reprodução.

    - Nova entrada quando o track_id muda (inclusive voltando a uma faixa já ouvida).
    - Repetição da mesma faixa (repetir faixa) conta quando a posição salta do
      fim para o começo.
    - Atualizações de posição, pausa/retomada e metadados repetidos não contam.
    - Ao (re)conectar, a faixa atual vira evento ``initial=True`` uma vez —
      o histórico registra, as notificações ignoram. Se a faixa for a mesma de
      antes da reconexão, nada é emitido.
    - Anúncios e metadados incompletos (sem título) são ignorados.
    """

    def __init__(self, clock=time.time):
        self._clock = clock
        self._last_id = ""
        self._connected = False
        self._last_pos = 0
        self._last_len = 0

    def update(self, state: PlayerState) -> PlayEvent | None:
        if not state.connected:
            self._connected = False
            return None
        if state.has_track and (not state.title or not state.track_id):
            return None              # metadados incompletos: espera a próxima atualização
        was_connected, self._connected = self._connected, True
        if not state.has_track or is_ad(state):
            return None
        pos = state.position_at()
        replay = (state.track_id == self._last_id and self._last_len > 0
                  and self._last_pos >= self._last_len - REPLAY_END_MARGIN_US
                  and pos <= REPLAY_START_MARGIN_US)
        new_track = state.track_id != self._last_id
        self._last_pos, self._last_len = pos, state.length_us
        if not (new_track or replay):
            return None
        self._last_id = state.track_id
        return PlayEvent(state.track_id, state.title, ", ".join(state.artists), state.album,
                         state.art_url, self._clock(), initial=not was_connected)


@dataclass
class HistoryEntry:
    track_id: str
    title: str
    artist: str
    album: str
    art_url: str
    started_at: float

    def as_qml(self) -> dict:
        return {"title": self.title, "artist": self.artist, "album": self.album,
                "artUrl": self.art_url,
                "time": datetime.fromtimestamp(self.started_at).strftime("%H:%M"),
                "day": datetime.fromtimestamp(self.started_at).strftime("%d/%m")}


class History:
    """Histórico em memória (mais recente primeiro), com persistência opcional."""

    MAX = 300

    def __init__(self, path: Path | None = None, persist: bool = False):
        self.path = path
        self.persist = persist
        self.entries: list[HistoryEntry] = []
        self.error = ""
        if persist:
            self._load()

    def add(self, ev: PlayEvent) -> HistoryEntry:
        e = HistoryEntry(ev.track_id, ev.title, ev.artist, ev.album, ev.art_url, ev.started_at)
        self.entries.insert(0, e)
        del self.entries[self.MAX:]
        self._save()
        return e

    def clear(self) -> None:
        self.entries.clear()
        self._save()

    def set_persist(self, on: bool) -> None:
        self.persist = on
        if on:
            self._save()
        elif self.path and self.path.exists():
            try:
                self.path.unlink()   # desligar apaga o arquivo; a sessão continua em memória
            except OSError as exc:
                self.error = str(exc)

    def _load(self) -> None:
        if not self.path:
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw.get("entries", [])[: self.MAX]:
                self.entries.append(HistoryEntry(
                    str(item["track_id"]), str(item["title"]), str(item.get("artist", "")),
                    str(item.get("album", "")), str(item.get("art_url", "")), float(item["started_at"])))
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            self.error = f"histórico salvo ilegível, ignorado ({exc})"
            self.entries.clear()

    def _save(self) -> None:
        if not (self.persist and self.path):
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".history-", dir=self.path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "entries": [asdict(e) for e in self.entries]}, fh, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError as exc:
            self.error = str(exc)
