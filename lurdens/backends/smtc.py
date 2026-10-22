"""Backend do Windows: Spotify pelos controles de mídia do sistema (SMTC).

O Spotify Desktop publica a sessão de mídia no Windows 10/11 — é ela que
aparece no painel de volume e responde às teclas de mídia. O Lurdens lê e
controla essa sessão pela API GlobalSystemMediaTransportControls, sem conta
nem login, usando o pacote ``winrt`` (PyWinRT).

O que o SMTC expõe: título, artista, álbum, capa (imagem, não URL), estado,
posição, tocar/pausar, anterior/próxima, busca, aleatório e repetição. Não
há controle de volume por aplicativo; o controle fica esmaecido, como
acontece no Linux quando o Spotify não expõe o volume.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..state import PlayerState
from .polling import PollingBackend

log = logging.getLogger("lurdens.smtc")

WINRT_PACKAGES = ("winrt-runtime winrt-Windows.Foundation winrt-Windows.Media "
                  "winrt-Windows.Media.Control winrt-Windows.Storage.Streams")

# GlobalSystemMediaTransportControlsSessionPlaybackStatus
_STATUS = {0: "Stopped", 1: "Stopped", 2: "Paused", 3: "Stopped", 4: "Playing", 5: "Paused"}
# Windows.Media.MediaPlaybackAutoRepeatMode
_REPEAT = {0: "None", 1: "Track", 2: "Playlist"}
_REPEAT_VALUE = {v: k for k, v in _REPEAT.items()}

MAX_ART_BYTES = 5_000_000
ART_FILES_KEPT = 24


def is_spotify_app_id(app_id: str | None) -> bool:
    """AppUserModelId do Spotify: "Spotify.exe" (instalador) ou "SpotifyAB.SpotifyMusic_…" (Microsoft Store)."""
    return "spotify" in (app_id or "").lower()


def default_art_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base) / "Lurdens" / "cache" / "art"


def _us(value) -> int:
    """TimeSpan do WinRT (timedelta no PyWinRT) em microssegundos."""
    if value is None:
        return 0
    if isinstance(value, timedelta):
        return max(0, int(value / timedelta(microseconds=1)))
    return max(0, int(value) // 10)        # ticks de 100 ns


async def _request_manager():
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as Manager)
    except ImportError as exc:
        raise RuntimeError(f"pacote winrt ausente ({exc.name}); instale: pip install {WINRT_PACKAGES}") from exc
    return await Manager.request_async()


async def _read_thumbnail(ref) -> bytes:
    from winrt.windows.storage.streams import Buffer, InputStreamOptions
    stream = await ref.open_read_async()
    size = min(int(getattr(stream, "size", 0) or MAX_ART_BYTES), MAX_ART_BYTES)
    result = await stream.read_async(Buffer(size), size, InputStreamOptions.READ_AHEAD)
    length = int(result.length)
    try:
        return bytes(memoryview(result))[:length]
    except TypeError:       # PyWinRT sem protocolo de buffer no IBuffer
        from winrt.windows.storage.streams import DataReader
        out = bytearray(length)
        DataReader.from_buffer(result).read_bytes(out)
        return bytes(out)


def _repeat_enum(mode: str):
    value = _REPEAT_VALUE[mode]
    try:
        from winrt.windows.media import MediaPlaybackAutoRepeatMode
    except ImportError:
        return value
    return MediaPlaybackAutoRepeatMode(value)


def _open_spotify_uri() -> None:
    os.startfile("spotify:")      # type: ignore[attr-defined]  # traz o Spotify para frente


class SmtcBackend(PollingBackend):
    kind = "smtc"
    label = "Controles de mídia do Windows (SMTC)"

    def __init__(self, on_state, *, manager_factory=_request_manager, thumbnail_reader=_read_thumbnail,
                 open_uri=_open_spotify_uri, art_dir: Path | None = None, now=None, **kw):
        super().__init__(on_state, **kw)
        self._manager_factory = manager_factory
        self._thumbnail_reader = thumbnail_reader
        self._open_uri = open_uri
        self._art_dir = art_dir or default_art_dir()
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._loop: asyncio.AbstractEventLoop | None = None
        self._manager = None
        self._art_key = ""
        self._art_url = ""

    # ------------------------------------------------------------- ciclo de vida
    def _await(self, awaitable):
        async def wrap():
            return await awaitable
        return self._loop.run_until_complete(wrap())

    def _open(self) -> None:
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        self._manager = self._await(self._manager_factory())

    def _close(self) -> None:
        if self._loop is not None:
            self._loop.close()
            self._loop = None

    def _session(self):
        if self._manager is None:
            return None
        for session in self._manager.get_sessions():
            if is_spotify_app_id(session.source_app_user_model_id):
                return session
        return None

    # ------------------------------------------------------------------ leitura
    def _read(self) -> PlayerState | None:
        session = self._session()
        if session is None:
            return None
        props = self._await(session.try_get_media_properties_async())
        info = session.get_playback_info()
        timeline = session.get_timeline_properties()
        controls = info.controls

        status = _STATUS.get(int(info.playback_status), "") if info.playback_status is not None else ""
        title = str(props.title or "")
        artist = str(props.artist or "")
        album = str(props.album_title or "")
        track_id = ("smtc:" + "\x1f".join((title, artist, album))) if title else ""

        start_us = _us(timeline.start_time)
        length_us = max(0, _us(timeline.end_time) - start_us)
        position_us = max(0, _us(timeline.position) - start_us)
        rate = float(info.playback_rate or 1.0) or 1.0
        updated = timeline.last_updated_time
        if status == "Playing" and isinstance(updated, datetime) and updated.year > 1601:
            # A posição do SMTC é a do instante da última atualização: avança até agora.
            elapsed = (self._now() - updated).total_seconds()
            if elapsed > 0:
                position_us += int(elapsed * 1_000_000 * rate)
        if length_us:
            position_us = min(position_us, length_us)

        shuffle = info.is_shuffle_active
        repeat = info.auto_repeat_mode
        state = PlayerState(
            bus_name=str(session.source_app_user_model_id or ""),
            identity="Spotify",
            status=status,
            track_id=track_id,
            title=title,
            artists=(artist,) if artist else (),
            album=album,
            art_url=self._art_for(track_id, props.thumbnail),
            length_us=length_us,
            rate=rate,
            can_control=True,
            can_play=bool(controls.is_play_enabled),
            can_pause=bool(controls.is_pause_enabled),
            can_next=bool(controls.is_next_enabled),
            can_prev=bool(controls.is_previous_enabled),
            can_seek=bool(controls.is_playback_position_enabled),
            can_raise=True,
            volume=None,
            shuffle=None if shuffle is None else bool(shuffle),
            loop_status=None if repeat is None else _REPEAT.get(int(repeat)),
        )
        return state.with_position(position_us)

    def _art_for(self, track_id: str, thumbnail) -> str:
        """Salva a capa da faixa num arquivo local (o QML só carrega URLs)."""
        if not track_id:
            return ""
        if track_id == self._art_key:
            return self._art_url
        if thumbnail is None:
            return ""       # o Spotify às vezes publica a capa logo depois do título: tenta de novo
        self._art_key, self._art_url = track_id, ""
        try:
            data = self._await(self._thumbnail_reader(thumbnail))
            if not data:
                return ""
            self._art_dir.mkdir(parents=True, exist_ok=True)
            target = self._art_dir / (hashlib.sha1(track_id.encode()).hexdigest() + ".img")
            tmp = target.with_suffix(".part")
            tmp.write_bytes(data)
            os.replace(tmp, target)
            self._art_url = target.as_uri()
            self._prune_art()
        except Exception as exc:
            log.debug("capa indisponível: %s", exc)
        return self._art_url

    def _prune_art(self) -> None:
        try:
            files = sorted(self._art_dir.glob("*.img"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in files[ART_FILES_KEPT:]:
                old.unlink(missing_ok=True)
        except OSError:
            pass

    # ---------------------------------------------------------------- comandos
    def _send(self, command: str, *args) -> None:
        if command == "Raise":
            self._open_uri()
            return
        session = self._session()
        if session is None:
            raise RuntimeError("sessão do Spotify não encontrada")
        if command == "PlayPause":
            op = session.try_toggle_play_pause_async()
        elif command == "Pause":
            op = session.try_pause_async()
        elif command == "Next":
            op = session.try_skip_next_async()
        elif command == "Previous":
            op = session.try_skip_previous_async()
        elif command == "SetPosition":
            op = session.try_change_playback_position_async(int(args[0]) * 10)   # µs → 100 ns
        elif command == "SetShuffle":
            op = session.try_change_shuffle_active_async(bool(args[0]))
        elif command == "SetLoop":
            op = session.try_change_auto_repeat_mode_async(_repeat_enum(args[0]))
        else:
            raise ValueError(f"comando não suportado no Windows: {command}")
        if not self._await(op):
            raise RuntimeError(f"o Spotify recusou o comando {command}")
