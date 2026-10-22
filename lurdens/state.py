"""Estado de reprodução, independente de Qt e de D-Bus."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace

MPRIS_PREFIX = "org.mpris.MediaPlayer2."
SPOTIFY_NAME = MPRIS_PREFIX + "spotify"


def is_spotify_bus_name(name: str) -> bool:
    """Nome do Spotify no D-Bus (RPM, Flatpak e eventuais instâncias extras)."""
    return name == SPOTIFY_NAME or name.startswith(SPOTIFY_NAME + ".")


def normalize_art_url(url: str) -> str:
    """Versões antigas do Spotify publicavam um domínio que não serve imagens."""
    if not url:
        return ""
    url = url.strip()
    for old in ("https://open.spotify.com/image/", "http://open.spotify.com/image/"):
        if url.startswith(old):
            return "https://i.scdn.co/image/" + url[len(old):]
    if url.startswith(("http://", "https://", "file://")):
        return url
    if url.startswith("/"):
        return "file://" + url
    return ""


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [str(v) for v in value if v]


@dataclass(frozen=True)
class PlayerState:
    bus_available: bool = False
    connected: bool = False          # Spotify presente no barramento
    bus_name: str = ""
    identity: str = ""
    status: str = ""                 # Playing | Paused | Stopped | ""
    track_id: str = ""
    title: str = ""
    artists: tuple[str, ...] = ()
    album: str = ""
    art_url: str = ""
    length_us: int = 0
    position_us: int = 0
    position_ts: float = field(default_factory=time.monotonic)
    rate: float = 1.0
    can_control: bool = False
    can_play: bool = False
    can_pause: bool = False
    can_next: bool = False
    can_prev: bool = False
    can_seek: bool = False
    can_raise: bool = False
    volume: float | None = None      # None = não suportado
    shuffle: bool | None = None
    loop_status: str | None = None   # None | "None" | "Track" | "Playlist"

    @property
    def has_track(self) -> bool:
        return self.connected and bool(self.title or self.track_id)

    @property
    def playing(self) -> bool:
        return self.status == "Playing"

    def position_at(self, now: float | None = None) -> int:
        """Posição estimada (µs), interpolada enquanto toca."""
        pos = self.position_us
        if self.playing:
            now = time.monotonic() if now is None else now
            pos += int((now - self.position_ts) * 1_000_000 * (self.rate or 1.0))
        if self.length_us > 0:
            pos = min(pos, self.length_us)
        return max(0, pos)

    def with_position(self, position_us: int) -> "PlayerState":
        return replace(self, position_us=max(0, int(position_us)), position_ts=time.monotonic())


def apply_player_properties(state: PlayerState, props: dict) -> PlayerState:
    """Aplica propriedades de org.mpris.MediaPlayer2.Player ao estado."""
    changes: dict = {}
    if "PlaybackStatus" in props:
        changes["status"] = str(props["PlaybackStatus"])
    if "Metadata" in props:
        md = props["Metadata"] or {}
        changes.update(
            track_id=str(md.get("mpris:trackid", "") or ""),
            title=str(md.get("xesam:title", "") or ""),
            artists=tuple(_as_list(md.get("xesam:artist"))),
            album=str(md.get("xesam:album", "") or ""),
            art_url=normalize_art_url(str(md.get("mpris:artUrl", "") or "")),
            length_us=max(0, int(md.get("mpris:length", 0) or 0)),
        )
    for key, attr in (("CanControl", "can_control"), ("CanPlay", "can_play"),
                      ("CanPause", "can_pause"), ("CanGoNext", "can_next"),
                      ("CanGoPrevious", "can_prev"), ("CanSeek", "can_seek")):
        if key in props:
            changes[attr] = bool(props[key])
    if "Rate" in props:
        try:
            changes["rate"] = float(props["Rate"]) or 1.0
        except (TypeError, ValueError):
            pass
    if "Volume" in props:
        try:
            changes["volume"] = max(0.0, min(1.0, float(props["Volume"])))
        except (TypeError, ValueError):
            pass
    if "Shuffle" in props:
        changes["shuffle"] = bool(props["Shuffle"])
    if "LoopStatus" in props and str(props["LoopStatus"]) in ("None", "Track", "Playlist"):
        changes["loop_status"] = str(props["LoopStatus"])

    # Congela a posição interpolada antes de mudar status/taxa, para não saltar.
    if "status" in changes or "rate" in changes:
        state = state.with_position(state.position_at())
    new = replace(state, **changes)
    if "Position" in props:
        new = new.with_position(int(props["Position"] or 0))
    elif "track_id" in changes and changes["track_id"] != state.track_id:
        new = new.with_position(0)
    return new


def next_loop_status(current: str | None) -> str:
    order = ["None", "Playlist", "Track"]
    if current not in order:
        return "Playlist"
    return order[(order.index(current) + 1) % len(order)]


def format_time(us: int) -> str:
    total = max(0, int(us // 1_000_000))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
