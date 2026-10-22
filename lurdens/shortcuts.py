"""Atalhos globais pelo serviço de atalhos do KDE (kglobalaccel).

No Plasma 6 — em Wayland e em X11 — aplicativos não capturam o teclado
globalmente; o caminho suportado é registrar ações no kglobalacceld via
D-Bus. As ações aparecem em Configurações do Sistema › Atalhos › Lurdens,
onde o usuário pode trocá-las; a escolha feita lá é carregada aqui.
Se o serviço não existir (outro ambiente), o Lurdens informa a limitação e
os atalhos dentro da janela continuam funcionando.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable

from .dbus.wire import Connection, DBusError, Message

log = logging.getLogger("lurdens.shortcuts")

SVC = "org.kde.kglobalaccel"
PATH = "/kglobalaccel"
IFACE = "org.kde.KGlobalAccel"
COMPONENT_IFACE = "org.kde.kglobalaccel.Component"
COMPONENT = "lurdens"
COMPONENT_NAME = "Lurdens"

# kglobalacceld: SetShortcutFlag
SET_PRESENT, NO_AUTOLOADING, IS_DEFAULT = 2, 4, 8

# Códigos de tecla do Qt (Qt::Key | Qt::KeyboardModifier)
META, CTRL, ALT, SHIFT = 0x10000000, 0x04000000, 0x08000000, 0x02000000
MOD_MASK = META | CTRL | ALT | SHIFT | 0x20000000  # + KeypadModifier


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    default: int


# Padrões com Meta+Alt+letra: combinação pouco usada no Plasma. Se mesmo assim
# houver conflito, o kglobalacceld recusa e a ação fica sem tecla (informado na UI).
ACTIONS = (
    Action("play-pause", "Reproduzir / pausar", META | ALT | 0x50),    # Meta+Alt+P
    Action("next", "Próxima música", META | ALT | 0x4E),               # Meta+Alt+N
    Action("previous", "Música anterior", META | ALT | 0x42),          # Meta+Alt+B
    Action("show", "Mostrar / ocultar o Lurdens", META | ALT | 0x4C),  # Meta+Alt+L
)
ACTION_IDS = {a.id for a in ACTIONS}


def action_id(a: Action) -> list[str]:
    return [COMPONENT, a.id, COMPONENT_NAME, a.label]


def encode_keys(key: int) -> list:
    """QList<QKeySequence> como a(ai): cada sequência leva até 4 combinações."""
    return [([int(key), 0, 0, 0],)] if key else []


def decode_keys(value) -> int:
    for seq in value or []:
        ints = seq[0] if isinstance(seq, tuple) else seq
        for k in ints:
            if k:
                return int(k)
    return 0


def key_text(key: int) -> str:
    """Texto legível sem depender do Qt (a UI usa QKeySequence quando disponível)."""
    if not key:
        return ""
    parts = []
    for flag, name in ((META, "Meta"), (CTRL, "Ctrl"), (ALT, "Alt"), (SHIFT, "Shift")):
        if key & flag:
            parts.append(name)
    code = key & ~MOD_MASK
    named = {0x20: "Espaço", 0x01000012: "←", 0x01000013: "↑", 0x01000014: "→", 0x01000015: "↓",
             0x01000000: "Esc", 0x01000004: "Enter"}
    if code in named:
        parts.append(named[code])
    elif 0x01000030 <= code <= 0x01000052:
        parts.append(f"F{code - 0x01000030 + 1}")
    elif 0x20 < code < 0x7F:
        parts.append(chr(code).upper())
    else:
        parts.append(hex(code))
    return "+".join(parts)


class GlobalShortcuts:
    """Registra as ações e chama ``on_action(id)`` quando o atalho é pressionado.

    ``on_change()`` é chamado (em outra thread) quando o estado/teclas mudam.
    """

    def __init__(self, on_action: Callable[[str], None], on_change: Callable[[], None] = lambda: None,
                 address: str | None = None):
        self._on_action = on_action
        self._on_change = on_change
        self._address = address
        self._q: queue.Queue = queue.Queue()
        self._conn: Connection | None = None
        self.available = False
        self.status = "iniciando…"
        self.keys: dict[str, int] = {a.id: 0 for a in ACTIONS}
        self.conflicts: set[str] = set()
        self._legacy = False
        self._thread = threading.Thread(target=self._run, name="lurdens-shortcuts", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._q.put(None)

    def set_key(self, action: str, key: int) -> None:
        self._q.put(("set", action, int(key)))

    def reset_defaults(self) -> None:
        self._q.put(("reset",))

    def wait_idle(self, timeout: float = 5.0) -> None:
        ev = threading.Event()
        self._q.put(("sync", ev))
        ev.wait(timeout)

    # ------------------------------------------------------------------
    def _run(self):
        try:
            self._setup()
        except (DBusError, OSError) as exc:
            self.available = False
            self.status = self._explain(exc)
            log.debug("atalhos globais indisponíveis: %s", exc)
        self._changed()
        while True:
            item = self._q.get()
            if item is None:
                break
            try:
                kind = item[0]
                if kind == "sync":
                    item[1].set()
                elif kind == "pressed":
                    self._on_action(item[1])
                elif kind == "keys-changed":
                    self._refresh()
                elif kind == "set" and self.available and item[1] in ACTION_IDS:
                    self._apply(item[1], item[2])
                elif kind == "reset" and self.available:
                    for a in ACTIONS:
                        self._apply(a.id, a.default)
            except (DBusError, OSError) as exc:
                self.status = self._explain(exc)
                self._changed()
            except Exception:
                log.exception("erro nos atalhos globais")
        if self._conn:
            self._conn.close()

    @staticmethod
    def _explain(exc) -> str:
        name = getattr(exc, "name", "")
        if "ServiceUnknown" in name or "NameHasNoOwner" in name:
            return "serviço de atalhos do KDE (kglobalaccel) não encontrado nesta sessão"
        if "NoBus" in name:
            return "D-Bus de sessão indisponível"
        return f"falha ao registrar atalhos ({exc})"

    def _call(self, member, sig="", args=()):
        return self._conn.call(SVC, PATH, IFACE, member, sig, args, timeout=4)

    def _setup(self):
        self._conn = Connection(self._address)
        self._conn.add_signal_handler(self._on_signal)
        self._conn.add_match(f"type='signal',interface='{COMPONENT_IFACE}',member='globalShortcutPressed',"
                             f"path='/component/{COMPONENT}'")
        self._conn.add_match(f"type='signal',interface='{IFACE}',member='yourShortcutsChanged'")
        for a in ACTIONS:
            aid = action_id(a)
            self._call("doRegister", "as", (aid,))
            self._set(aid, a.default, IS_DEFAULT)          # padrão (para "restaurar padrão" do KDE)
            got = self._set(aid, a.default, SET_PRESENT)    # ativo: mantém o que o usuário salvou
            self.keys[a.id] = got
            if not got:
                self.conflicts.add(a.id)
        self.available = True
        self.status = "ativos (Configurações do Sistema › Atalhos › Lurdens)"
        if self.conflicts:
            self.status = "ativos, mas alguns atalhos estavam em uso por outro programa"

    def _set(self, aid, key, flags) -> int:
        if not self._legacy:
            try:
                (res,) = self._call("setShortcutKeys", "asa(ai)u", (aid, encode_keys(key), flags))
                return decode_keys(res)
            except DBusError as exc:
                if "UnknownMethod" not in exc.name:
                    raise
                self._legacy = True   # kglobalaccel antigo (KF5)
        (res,) = self._call("setShortcut", "asaiu", (aid, [key] if key else [], flags))
        return next((int(k) for k in res if k), 0)

    def _apply(self, action: str, key: int):
        a = next(x for x in ACTIONS if x.id == action)
        got = self._set(action_id(a), key, SET_PRESENT | NO_AUTOLOADING)
        self.keys[action] = got
        if key and not got:
            self.conflicts.add(action)
        else:
            self.conflicts.discard(action)
        self._changed()

    def _refresh(self):
        for a in ACTIONS:
            try:
                (res,) = self._call("shortcutKeys", "as", (action_id(a),))
                self.keys[a.id] = decode_keys(res)
            except DBusError:
                if not self._legacy:
                    raise
                (res,) = self._call("shortcut", "as", (action_id(a),))
                self.keys[a.id] = next((int(k) for k in res if k), 0)
        self._changed()

    def _on_signal(self, msg: Message):
        # roda na thread leitora: só enfileira
        if msg.member == "globalShortcutPressed" and msg.interface == COMPONENT_IFACE:
            comp, action = msg.body[0], msg.body[1]
            if comp == COMPONENT and action in ACTION_IDS:
                self._q.put(("pressed", action))
        elif msg.member == "yourShortcutsChanged" and msg.interface == IFACE:
            if msg.body and msg.body[0] and msg.body[0][0] == COMPONENT:
                self._q.put(("keys-changed",))

    def _changed(self):
        try:
            self._on_change()
        except Exception:
            pass
