"""Base para backends que consultam o Spotify periodicamente.

No Windows (SMTC) e no macOS (AppleScript) não há um fluxo de sinais tão
completo quanto o MPRIS, então o estado é lido em intervalos curtos. Esta
classe cuida do que é igual nos dois casos:

- uma única thread com fila de comandos (a interface nunca espera);
- leitura a cada ``interval`` segundos com o Spotify aberto e a cada
  ``idle_interval`` com ele fechado;
- publicação só quando algo muda de verdade. A posição é interpolada pela
  própria interface, então desvios pequenos não geram atualizações;
- atualização otimista após comandos e uma pausa curta antes da próxima
  leitura, para o sistema refletir o comando sem a interface "piscar".

As subclasses implementam ``_read`` e ``_send`` (e, se precisarem,
``_open``/``_close``).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from abc import abstractmethod
from dataclasses import replace

from ..state import PlayerState
from .base import PlayerBackend, StateCallback, next_loop_mode

log = logging.getLogger("lurdens.backends")

#: diferença de posição (µs) a partir da qual uma leitura conta como mudança
POSITION_TOLERANCE_US = 1_500_000
#: leituras com erro seguidas antes de considerar o Spotify indisponível
MAX_READ_ERRORS = 2


class PollingBackend(PlayerBackend):
    def __init__(self, on_state: StateCallback, *, interval: float = 1.0,
                 idle_interval: float = 3.0, settle: float = 0.8, clock=time.monotonic):
        self._on_state = on_state
        self._interval = interval
        self._idle_interval = idle_interval
        self._settle = settle
        self._clock = clock
        self._q: queue.Queue = queue.Queue()
        self._state = PlayerState()
        self._opened = False
        self._read_errors = 0
        self._poll_at = 0.0
        self._thread = threading.Thread(target=self._run, name=f"lurdens-{self.kind or 'poll'}",
                                        daemon=True)
        self.last_error = ""

    # ----------------------------------------------------- ganchos (subclasses)
    def _open(self) -> None:
        """Prepara o acesso ao serviço do sistema. Exceção = indisponível agora."""

    def _close(self) -> None:
        """Libera recursos ao encerrar."""

    @abstractmethod
    def _read(self) -> PlayerState | None:
        """Estado atual do Spotify, ou None se ele não estiver aberto.

        O estado devolvido deve trazer a posição já medida no instante da
        leitura (``with_position``); ``connected``/``bus_available`` são
        preenchidos aqui.
        """

    @abstractmethod
    def _send(self, command: str, *args) -> None:
        """Executa um comando no Spotify.

        Comandos: ``PlayPause``, ``Pause``, ``Next``, ``Previous``,
        ``SetPosition`` (µs), ``SetVolume`` (0.0–1.0), ``SetShuffle`` (bool),
        ``SetLoop`` ("None" | "Playlist" | "Track") e ``Raise``.
        """

    # -------------------------------------------------------------------- API
    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._q.put(("stop",))
        if self._thread.is_alive():
            self._thread.join(timeout)

    @property
    def state(self) -> PlayerState:
        return self._state

    def play_pause(self):
        self._command(self._do_simple, "PlayPause")

    def pause(self):
        self._command(self._do_simple, "Pause")

    def next(self):
        self._command(self._do_simple, "Next")

    def previous(self):
        self._command(self._do_simple, "Previous")

    def seek_to(self, position_us: int):
        self._command(self._do_seek_to, int(position_us))

    def seek_by(self, offset_us: int):
        self._command(self._do_seek_by, int(offset_us))

    def set_volume(self, volume: float):
        self._command(self._do_set_volume, float(volume))

    def toggle_shuffle(self):
        self._command(self._do_toggle_shuffle)

    def cycle_loop(self):
        self._command(self._do_cycle_loop)

    def raise_player(self):
        self._command(self._do_raise)

    def refresh(self):
        self._command(self._poll)

    def _command(self, fn, *args):
        self._q.put(("call", fn, args))

    # ------------------------------------------------------------- laço principal
    def _run(self) -> None:
        while True:
            if not self._opened and not self._try_open():
                if self._wait_stop(self._idle_interval):
                    break
                continue
            try:
                item = self._q.get(timeout=max(0.0, self._poll_at - self._clock()))
            except queue.Empty:
                self._poll()
                continue
            if item[0] == "stop":
                break
            try:
                item[1](*item[2])
            except Exception as exc:  # nunca deixar a thread morrer
                self.last_error = str(exc) or exc.__class__.__name__
                log.debug("comando falhou: %s", exc, exc_info=True)
                self._poll_at = self._clock()
        try:
            self._close()
        except Exception:
            log.debug("erro ao encerrar o backend", exc_info=True)

    def _try_open(self) -> bool:
        try:
            self._open()
        except Exception as exc:
            self.last_error = str(exc) or exc.__class__.__name__
            log.debug("serviço de mídia indisponível: %s", exc)
            if self._state.bus_available or self._state.connected:
                self._emit(PlayerState(bus_available=False))
            return False
        self._opened = True
        self.last_error = ""
        self._poll()
        return True

    def _wait_stop(self, delay: float) -> bool:
        """Espera até tentar de novo; True se pediram para parar."""
        deadline = self._clock() + delay
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                return False
            try:
                item = self._q.get(timeout=remaining)
            except queue.Empty:
                return False
            if item[0] == "stop":
                return True
            # comandos sem serviço disponível são descartados

    # ------------------------------------------------------------------ leitura
    def _poll(self) -> None:
        try:
            snap = self._read()
            self._read_errors = 0
        except Exception as exc:
            self._read_errors += 1
            self.last_error = str(exc) or exc.__class__.__name__
            log.debug("leitura falhou (%d): %s", self._read_errors, exc)
            if self._read_errors < MAX_READ_ERRORS:
                self._poll_at = self._clock() + self._interval
                return
            snap = None
        if snap is None:
            new = PlayerState(bus_available=True)
        else:
            new = replace(snap, bus_available=True, connected=True)
        self._poll_at = self._clock() + (self._interval if new.connected else self._idle_interval)
        if self._differs(self._state, new):
            self._emit(new)

    @staticmethod
    def _differs(old: PlayerState, new: PlayerState) -> bool:
        def strip(s: PlayerState) -> PlayerState:
            return replace(s, position_us=0, position_ts=0.0)
        if strip(old) != strip(new):
            return True
        if not new.connected:
            return False
        return abs(new.position_at() - old.position_at()) > POSITION_TOLERANCE_US

    # ---------------------------------------------------------------- comandos
    def _after_command(self, optimistic: PlayerState | None = None) -> None:
        if optimistic is not None:
            self._emit(optimistic)
        # dá tempo ao sistema de refletir o comando antes de ler de novo
        self._poll_at = self._clock() + self._settle

    def _do_simple(self, command: str) -> None:
        s = self._state
        if not s.connected:
            return
        allowed = {"PlayPause": s.can_play or s.can_pause, "Next": s.can_next,
                   "Previous": s.can_prev, "Pause": s.can_pause and s.playing}[command]
        if not allowed:
            return
        self._send(command)
        optimistic = None
        if command == "PlayPause" and s.status in ("Playing", "Paused"):
            frozen = s.with_position(s.position_at())
            optimistic = replace(frozen, status="Paused" if s.playing else "Playing")
        elif command == "Pause":
            optimistic = replace(s.with_position(s.position_at()), status="Paused")
        self._after_command(optimistic)

    def _do_seek_to(self, position_us: int) -> None:
        s = self._state
        if not (s.connected and s.can_seek):
            return
        target = max(0, int(position_us))
        if s.length_us:
            target = min(target, s.length_us - 1)
        self._send("SetPosition", target)
        self._after_command(s.with_position(target))

    def _do_seek_by(self, offset_us: int) -> None:
        self._do_seek_to(self._state.position_at() + offset_us)

    def _do_set_volume(self, volume: float) -> None:
        s = self._state
        if not s.connected or s.volume is None:
            return
        v = max(0.0, min(1.0, volume))
        self._send("SetVolume", v)
        self._after_command(replace(s, volume=v))

    def _do_toggle_shuffle(self) -> None:
        s = self._state
        if not s.connected or s.shuffle is None:
            return
        self._send("SetShuffle", not s.shuffle)
        self._after_command(replace(s, shuffle=not s.shuffle))

    def _do_cycle_loop(self) -> None:
        s = self._state
        if not s.connected or s.loop_status is None:
            return
        nxt = next_loop_mode(s.loop_status, self.loop_modes)
        self._send("SetLoop", nxt)
        self._after_command(replace(s, loop_status=nxt))

    def _do_raise(self) -> None:
        if self._state.connected and self._state.can_raise:
            self._send("Raise")

    # ------------------------------------------------------------------ saída
    def _emit(self, state: PlayerState) -> None:
        self._state = state
        try:
            self._on_state(state)
        except Exception:
            log.exception("callback de estado falhou")
