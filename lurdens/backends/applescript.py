"""Backend do macOS: Spotify pelo dicionário AppleScript do próprio app.

O Spotify para macOS publica um dicionário AppleScript com o estado do
player, a faixa atual (inclusive a URL da capa) e os comandos de
reprodução. O Lurdens executa scripts curtos com ``osascript`` (que já vem
no sistema), sem conta, login nem dependências extras.

Na primeira vez o macOS pede permissão para o Lurdens controlar o Spotify
(Ajustes do Sistema › Privacidade e Segurança › Automação). Se o pedido for
negado, os scripts falham com o erro -1743 e a interface mostra o motivo.

Limitações do dicionário do Spotify: a repetição é só liga/desliga (repete
a lista; não há "repetir faixa") e não há sinais de mudança, por isso o
estado é lido periodicamente.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..state import PlayerState, normalize_art_url
from .polling import PollingBackend

BUNDLE_ID = "com.spotify.client"
SEP = "\x1f"
NOT_RUNNING = "NOT_RUNNING"
AUTOMATION_DENIED = "-1743"

_TELL = f'tell application id "{BUNDLE_ID}"'

READ_SCRIPT = f"""\
if application id "{BUNDLE_ID}" is running then
    {_TELL}
        set sep to character id 31
        set out to (player state as string) & sep & (player position as string) & sep ¬
            & (sound volume as string) & sep & (shuffling as string) & sep & (repeating as string)
        try
            set t to current track
            set out to out & sep & (id of t) & sep & (name of t) & sep & (artist of t) & sep ¬
                & (album of t) & sep & (artwork url of t) & sep & ((duration of t) as string)
        end try
        return out
    end tell
else
    return "{NOT_RUNNING}"
end if
"""

_STATUS = {"playing": "Playing", "paused": "Paused", "stopped": "Stopped"}


def find_spotify_app(home: Path | None = None, run=subprocess.run) -> str:
    """Caminho do Spotify.app instalado ("" se não houver).

    Necessário antes de qualquer script: o macOS abre um diálogo "Onde está
    o Spotify?" ao compilar um script para um aplicativo inexistente.
    """
    home = home or Path.home()
    for p in (Path("/Applications/Spotify.app"), home / "Applications" / "Spotify.app"):
        if p.exists():
            return str(p)
    try:
        r = run(["mdfind", f"kMDItemCFBundleIdentifier == '{BUNDLE_ID}'"],
                capture_output=True, text=True, timeout=5)
        for line in (r.stdout or "").splitlines():
            if line.endswith(".app"):
                return line
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def run_osascript(script: str, timeout: float = 5.0) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        msg = (r.stderr or "").strip() or f"osascript saiu com código {r.returncode}"
        if AUTOMATION_DENIED in msg:
            msg = ("sem permissão para controlar o Spotify — libere em Ajustes do Sistema › "
                   "Privacidade e Segurança › Automação › Lurdens")
        raise RuntimeError(msg)
    return r.stdout.rstrip("\n")


def _number(text: str) -> float:
    """Número do AppleScript convertido em texto (aceita vírgula decimal do locale)."""
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return 0.0


def _bool(text: str) -> bool | None:
    t = text.strip().lower()
    return True if t == "true" else False if t == "false" else None


def parse_state(output: str) -> PlayerState | None:
    """Converte a saída de READ_SCRIPT em PlayerState (None = Spotify fechado)."""
    if output.strip() == NOT_RUNNING:
        return None
    f = output.split(SEP)
    if len(f) < 5:
        raise ValueError(f"resposta inesperada do Spotify: {output[:80]!r}")
    status = _STATUS.get(f[0].strip().lower(), "")
    position_us = int(_number(f[1]) * 1_000_000)
    volume_raw = f[2].strip()
    volume = None if not volume_raw or volume_raw == "missing value" else max(0.0, min(1.0, _number(volume_raw) / 100))
    shuffle = _bool(f[3])
    repeat = _bool(f[4])
    track = dict(track_id="", title="", artists=(), album="", art_url="", length_us=0)
    if len(f) >= 11:
        track.update(track_id=f[5].strip(), title=f[6], artists=(f[7],) if f[7] else (), album=f[8],
                     art_url=normalize_art_url(f[9]), length_us=int(_number(f[10]) * 1000))   # ms → µs
    has_track = bool(track["title"] or track["track_id"])
    length_us = track["length_us"]
    if length_us:
        position_us = min(position_us, length_us)
    state = PlayerState(
        identity="Spotify",
        bus_name=BUNDLE_ID,
        status=status,
        can_control=True,
        can_play=has_track,
        can_pause=has_track,
        can_next=has_track,
        can_prev=has_track,
        can_seek=has_track and length_us > 0,
        can_raise=True,
        volume=volume,
        shuffle=shuffle,
        loop_status=None if repeat is None else ("Playlist" if repeat else "None"),
        **track,
    )
    return state.with_position(position_us)


def _guarded(command: str) -> str:
    # Nunca abre o Spotify sem querer: só envia o comando se ele já estiver aberto.
    return (f'if application id "{BUNDLE_ID}" is running then\n'
            f'    {_TELL} to {command}\n'
            f'end if')


def _as_bool(v) -> str:
    return "true" if v else "false"


class AppleScriptBackend(PollingBackend):
    kind = "applescript"
    label = "AppleScript do Spotify (macOS)"
    loop_modes = ("None", "Playlist")     # o Spotify só repete a lista via AppleScript

    def __init__(self, on_state, *, runner=run_osascript, finder=find_spotify_app, **kw):
        kw.setdefault("interval", 1.0)
        super().__init__(on_state, **kw)
        self._runner = runner
        self._finder = finder

    def _open(self) -> None:
        if not self._finder():
            raise RuntimeError("Spotify não está instalado (Spotify.app não encontrado)")

    def _read(self) -> PlayerState | None:
        return parse_state(self._runner(READ_SCRIPT))

    def _send(self, command: str, *args) -> None:
        if command == "PlayPause":
            body = "playpause"
        elif command == "Pause":
            body = "pause"
        elif command == "Next":
            body = "next track"
        elif command == "Previous":
            body = "previous track"
        elif command == "SetPosition":
            body = f"set player position to {int(args[0]) / 1_000_000:.3f}"
        elif command == "SetVolume":
            body = f"set sound volume to {round(float(args[0]) * 100)}"
        elif command == "SetShuffle":
            body = f"set shuffling to {_as_bool(args[0])}"
        elif command == "SetLoop":
            body = f"set repeating to {_as_bool(args[0] != 'None')}"
        elif command == "Raise":
            body = "activate"
        else:
            raise ValueError(f"comando não suportado no macOS: {command}")
        self._runner(_guarded(body))
