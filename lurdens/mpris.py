"""Cliente MPRIS do Spotify.

Mantém uma conexão com o barramento de sessão, descobre o Spotify (antes ou
depois de o Lurdens abrir), acompanha as mudanças por sinais
(PropertiesChanged, Seeked, NameOwnerChanged) e envia comandos.

Toda a lógica roda em uma única thread de trabalho com fila de eventos. A
interface recebe instantâneos imutáveis de PlayerState pelo callback
``on_state`` e nunca bloqueia esperando o D-Bus.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import replace
from typing import Callable

from .backends.base import PlayerBackend
from .dbus.wire import Connection, DBusError, Message, ObjectPath, Variant
from .state import (PlayerState, SPOTIFY_NAME, apply_player_properties,
                    is_spotify_bus_name, next_loop_status)

log = logging.getLogger("lurdens.mpris")

BUS = "org.freedesktop.DBus"
BUS_PATH = "/org/freedesktop/DBus"
PROPS = "org.freedesktop.DBus.Properties"
PATH = "/org/mpris/MediaPlayer2"
ROOT = "org.mpris.MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"

MATCH_RULES = (
    "type='signal',sender='org.freedesktop.DBus',interface='org.freedesktop.DBus',"
    "member='NameOwnerChanged',arg0namespace='org.mpris.MediaPlayer2'",
    "type='signal',interface='org.freedesktop.DBus.Properties',member='PropertiesChanged',"
    "path='/org/mpris/MediaPlayer2'",
    "type='signal',interface='org.mpris.MediaPlayer2.Player',member='Seeked',"
    "path='/org/mpris/MediaPlayer2'",
)
FALLBACK_NAME_RULE = ("type='signal',sender='org.freedesktop.DBus',"
                      "interface='org.freedesktop.DBus',member='NameOwnerChanged'")


class MprisClient(PlayerBackend):
    kind = "mpris"
    label = "MPRIS (D-Bus)"

    def __init__(self, on_state: Callable[[PlayerState], None], address: str | None = None,
                 reconnect_delay: float = 3.0, resync_interval: float = 5.0):
        self._on_state = on_state
        self._address = address
        self._reconnect_delay = reconnect_delay
        self._resync_interval = resync_interval
        self._q: queue.Queue = queue.Queue()
        self._conn: Connection | None = None
        self._owner = ""            # nome único (:1.42) do Spotify
        self._state = PlayerState()
        self._refresh_at: float | None = None
        self._resync_at: float | None = None
        self._thread = threading.Thread(target=self._run, name="lurdens-mpris", daemon=True)
        self.last_error = ""

    # ------------------------------------------------------------------ API
    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._q.put(("stop",))
        self._thread.join(timeout)

    @property
    def state(self) -> PlayerState:
        return self._state

    def play_pause(self):
        self._command(self._do_simple, "PlayPause")

    def pause(self):
        """Pausa (sem alternar): usado pelo temporizador para dormir."""
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
        self._command(self._discover)

    def _command(self, fn, *args):
        self._q.put(("call", fn, args))

    # ----------------------------------------------------------- loop principal
    def _run(self) -> None:
        while True:
            if self._conn is None:
                if not self._connect():
                    if self._wait_stop(self._reconnect_delay):
                        break
                    continue
            try:
                item = self._q.get(timeout=self._next_timeout())
            except queue.Empty:
                self._on_timer()
                continue
            kind = item[0]
            if kind == "stop":
                break
            try:
                if kind == "signal":
                    self._handle_signal(item[1])
                elif kind == "disconnected":
                    self._handle_bus_lost()
                elif kind == "call":
                    if self._conn is not None:
                        item[1](*item[2])
            except DBusError as exc:
                self.last_error = str(exc)
                log.debug("erro D-Bus: %s", exc)
            except Exception:  # nunca deixar a thread morrer
                log.exception("erro inesperado no cliente MPRIS")
        if self._conn is not None:
            self._conn.close()

    def _wait_stop(self, delay: float) -> bool:
        """Espera reconectar; retorna True se pediram para parar."""
        deadline = time.monotonic() + delay
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            try:
                item = self._q.get(timeout=remaining)
            except queue.Empty:
                return False
            if item[0] == "stop":
                return True
            # comandos sem conexão são descartados

    def _next_timeout(self) -> float:
        now = time.monotonic()
        deadlines = [d for d in (self._refresh_at, self._resync_at) if d is not None]
        if not deadlines:
            return 30.0
        return max(0.0, min(deadlines) - now)

    def _on_timer(self) -> None:
        now = time.monotonic()
        try:
            if self._refresh_at is not None and now >= self._refresh_at:
                self._refresh_at = None
                if self._owner:
                    self._load_all()
                else:
                    self._discover()
            if self._resync_at is not None and now >= self._resync_at:
                self._resync_at = None
                self._resync_position()
        except DBusError as exc:
            self.last_error = str(exc)

    # -------------------------------------------------------------- conexão
    def _connect(self) -> bool:
        try:
            conn = Connection(self._address)
        except (DBusError, OSError) as exc:
            self.last_error = str(exc)
            if self._state.bus_available or self._state.connected:
                self._emit(PlayerState(bus_available=False))
            return False
        conn.add_signal_handler(lambda m: self._q.put(("signal", m)))
        conn.add_disconnect_handler(lambda: self._q.put(("disconnected",)))
        try:
            for rule in MATCH_RULES:
                try:
                    conn.add_match(rule)
                except DBusError:
                    if "NameOwnerChanged" in rule:
                        conn.add_match(FALLBACK_NAME_RULE)
                    else:
                        raise
            self._conn = conn
            self.last_error = ""
            self._emit(PlayerState(bus_available=True))
            self._discover()
            return True
        except DBusError as exc:
            self.last_error = str(exc)
            conn.close()
            self._conn = None
            return False

    def _handle_bus_lost(self) -> None:
        if self._conn is not None and not self._conn.closed:
            return  # aviso atrasado de uma conexão antiga
        self._conn = None
        self._owner = ""
        self._refresh_at = self._resync_at = None
        self._emit(PlayerState(bus_available=False))

    def _call(self, dest, path, iface, member, sig="", args=(), timeout=3.0):
        if self._conn is None:
            raise DBusError("org.lurdens.Disconnected", "sem barramento")
        return self._conn.call(dest, path, iface, member, sig, args, timeout=timeout)

    # ------------------------------------------------------------- descoberta
    def _discover(self) -> None:
        (names,) = self._call(BUS, BUS_PATH, BUS, "ListNames")
        candidates = sorted((n for n in names if is_spotify_bus_name(n)),
                            key=lambda n: (n != SPOTIFY_NAME, n))
        for name in candidates:
            try:
                self._attach(name)
                return
            except DBusError as exc:
                self.last_error = str(exc)
        self._detach()

    def _attach(self, name: str) -> None:
        (owner,) = self._call(BUS, BUS_PATH, BUS, "GetNameOwner", "s", (name,))
        self._owner = owner
        self._state = PlayerState(bus_available=True, connected=True, bus_name=name)
        self._load_all()

    def _load_all(self) -> None:
        dest = self._owner
        state = replace(self._state, bus_available=True, connected=True)
        try:
            (props,) = self._call(dest, PATH, PROPS, "GetAll", "s", (PLAYER,))
        except DBusError as exc:
            # Spotify recém-aberto às vezes ainda não responde: tenta de novo.
            self.last_error = str(exc)
            self._refresh_at = time.monotonic() + 1.0
            self._emit(state)
            return
        state = apply_player_properties(state, props)
        if "Position" not in props:
            state = self._with_fetched_position(state)
        try:
            (root,) = self._call(dest, PATH, PROPS, "GetAll", "s", (ROOT,))
            state = replace(state, identity=str(root.get("Identity", "") or ""),
                            can_raise=bool(root.get("CanRaise", False)))
        except DBusError:
            pass
        self._emit(state)

    def _detach(self) -> None:
        self._owner = ""
        self._refresh_at = self._resync_at = None
        self._emit(PlayerState(bus_available=self._conn is not None))

    def _with_fetched_position(self, state: PlayerState) -> PlayerState:
        try:
            (pos,) = self._call(self._owner, PATH, PROPS, "Get", "ss", (PLAYER, "Position"))
            return state.with_position(int(pos))
        except (DBusError, TypeError, ValueError):
            return state

    def _resync_position(self) -> None:
        if self._owner and self._state.connected:
            self._emit(self._with_fetched_position(self._state))

    # ----------------------------------------------------------------- sinais
    def _handle_signal(self, msg: Message) -> None:
        if msg.member == "NameOwnerChanged" and msg.interface == BUS:
            name, _old, new = msg.body
            if not is_spotify_bus_name(name):
                return
            if new:
                if not self._owner or name == self._state.bus_name or name == SPOTIFY_NAME:
                    self._attach(name)
            elif name == self._state.bus_name:
                self._discover()  # pode haver outra instância
            return
        if not self._owner or msg.sender != self._owner:
            return
        if msg.member == "PropertiesChanged" and msg.interface == PROPS:
            iface, changed, invalidated = msg.body
            if iface == PLAYER:
                old = self._state
                state = apply_player_properties(old, changed)
                for prop in invalidated:
                    if prop == "Position":
                        continue
                    try:
                        (val,) = self._call(self._owner, PATH, PROPS, "Get", "ss", (PLAYER, prop))
                        state = apply_player_properties(state, {prop: val})
                    except DBusError:
                        pass
                if "Position" not in changed and (state.track_id != old.track_id or state.status != old.status):
                    # O Spotify nem sempre envia a posição junto da troca de faixa/estado.
                    self._resync_at = time.monotonic() + 0.3
                self._emit(state)
            elif iface == ROOT:
                state = self._state
                if "Identity" in changed:
                    state = replace(state, identity=str(changed["Identity"]))
                if "CanRaise" in changed:
                    state = replace(state, can_raise=bool(changed["CanRaise"]))
                self._emit(state)
        elif msg.member == "Seeked" and msg.interface == PLAYER:
            (pos,) = msg.body
            self._emit(self._state.with_position(int(pos)))

    # --------------------------------------------------------------- comandos
    def _player_call(self, member, sig="", args=(), optimistic: PlayerState | None = None):
        if not self._owner:
            return
        conn = self._conn

        def done(err, _result):
            if err is not None:
                self.last_error = str(err)
                self._q.put(("call", self._resync_position, ()))
        conn.call_async(self._owner, PATH, PLAYER, member, sig, args, callback=done)
        if optimistic is not None:
            self._emit(optimistic)

    def _set_prop(self, name, variant: Variant, optimistic: PlayerState):
        if not self._owner:
            return
        owner = self._owner

        def done(err, _result):
            if err is not None:
                self.last_error = str(err)
                self._q.put(("call", self._reload_if, (owner,)))
        self._conn.call_async(owner, PATH, PROPS, "Set", "ssv", (PLAYER, name, variant), callback=done)
        self._emit(optimistic)

    def _reload_if(self, owner):
        if owner == self._owner:
            self._load_all()

    def _do_simple(self, member):
        s = self._state
        allowed = {"PlayPause": s.can_play or s.can_pause, "Next": s.can_next,
                   "Previous": s.can_prev, "Pause": s.can_pause and s.playing}.get(member, True)
        if allowed:
            self._player_call(member)

    def _do_seek_to(self, position_us: int):
        s = self._state
        if not s.can_seek:
            return
        target = max(0, position_us)
        if s.length_us:
            target = min(target, s.length_us - 1)
        if s.track_id.startswith("/"):
            self._player_call("SetPosition", "ox", (ObjectPath(s.track_id), target),
                              optimistic=s.with_position(target))
        else:
            self._player_call("Seek", "x", (target - s.position_at(),),
                              optimistic=s.with_position(target))
        self._resync_at = time.monotonic() + 0.6

    def _do_seek_by(self, offset_us: int):
        self._do_seek_to(self._state.position_at() + offset_us)

    def _do_set_volume(self, volume: float):
        s = self._state
        if s.volume is None:
            return
        v = max(0.0, min(1.0, volume))
        self._set_prop("Volume", Variant("d", v), replace(s, volume=v))

    def _do_toggle_shuffle(self):
        s = self._state
        if s.shuffle is None:
            return
        self._set_prop("Shuffle", Variant("b", not s.shuffle), replace(s, shuffle=not s.shuffle))

    def _do_cycle_loop(self):
        s = self._state
        if s.loop_status is None:
            return
        nxt = next_loop_status(s.loop_status)
        self._set_prop("LoopStatus", Variant("s", nxt), replace(s, loop_status=nxt))

    def _do_raise(self):
        if self._owner and self._state.can_raise:
            self._conn.call_async(self._owner, PATH, ROOT, "Raise")

    # ------------------------------------------------------------------ saída
    def _emit(self, state: PlayerState) -> None:
        self._state = state
        if state.playing and self._owner:
            if self._resync_at is None:
                self._resync_at = time.monotonic() + self._resync_interval
        try:
            self._on_state(state)
        except Exception:
            log.exception("callback de estado falhou")
