"""Cliente D-Bus mínimo em Python puro.

Implementa apenas o necessário para o Lurdens conversar com players MPRIS e
com o KWin: autenticação EXTERNAL via socket Unix, serialização dos tipos
básicos/compostos da especificação D-Bus, chamadas de método (bloqueantes e
assíncronas) e recepção de sinais.

Não depende de Qt nem de bibliotecas externas, o que permite testá-lo
isoladamente e mantém a interface gráfica livre de bloqueios: toda a leitura
do socket acontece em uma thread dedicada.
"""

from __future__ import annotations

import itertools
import os
import socket
import struct
import threading
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import unquote

# --------------------------------------------------------------------------
# Tipos e assinaturas
# --------------------------------------------------------------------------

METHOD_CALL, METHOD_RETURN, ERROR, SIGNAL = 1, 2, 3, 4
FLAG_NO_REPLY_EXPECTED = 0x1

_FIXED = {
    "y": ("B", 1), "b": ("I", 4), "n": ("h", 2), "q": ("H", 2),
    "i": ("i", 4), "u": ("I", 4), "x": ("q", 8), "t": ("Q", 8),
    "d": ("d", 8), "h": ("I", 4),
}
_ALIGN = {**{k: v[1] for k, v in _FIXED.items()},
          "s": 4, "o": 4, "g": 1, "v": 1, "a": 4, "(": 8, "{": 8}


class DBusError(Exception):
    """Erro devolvido por um serviço D-Bus ou falha de comunicação."""

    def __init__(self, name: str, message: str = ""):
        super().__init__(f"{name}: {message}" if message else name)
        self.name = name
        self.message = message


class Variant:
    """Valor variante com assinatura explícita (usado ao serializar)."""

    __slots__ = ("signature", "value")

    def __init__(self, signature: str, value: Any):
        self.signature = signature
        self.value = value

    def __repr__(self) -> str:
        return f"Variant({self.signature!r}, {self.value!r})"


class ObjectPath(str):
    """Marca uma string como caminho de objeto D-Bus."""


def _parse_one(sig: str, i: int):
    c = sig[i]
    if c == "a":
        sub, j = _parse_one(sig, i + 1)
        return ("a", sub), j
    if c == "(":
        fields, i = [], i + 1
        while sig[i] != ")":
            t, i = _parse_one(sig, i)
            fields.append(t)
        if not fields:
            raise ValueError("struct vazio na assinatura")
        return ("(", fields), i + 1
    if c == "{":
        k, i = _parse_one(sig, i + 1)
        v, i = _parse_one(sig, i)
        if sig[i] != "}":
            raise ValueError(f"dict entry inválido em {sig!r}")
        return ("{", k, v), i + 1
    if c in _FIXED or c in "sogv":
        return c, i + 1
    raise ValueError(f"tipo D-Bus desconhecido {c!r} em {sig!r}")


def parse_signature(sig: str) -> list:
    """Converte uma assinatura em uma lista de árvores de tipo completas."""
    types, i = [], 0
    try:
        while i < len(sig):
            t, i = _parse_one(sig, i)
            types.append(t)
    except IndexError:
        raise ValueError(f"assinatura incompleta: {sig!r}") from None
    return types


def _code(t) -> str:
    return t if isinstance(t, str) else t[0]


def guess_signature(value: Any) -> str:
    """Infere a assinatura de valores Python simples (para variantes)."""
    if isinstance(value, Variant):
        return "v"
    if isinstance(value, bool):
        return "b"
    if isinstance(value, int):
        return "x"
    if isinstance(value, float):
        return "d"
    if isinstance(value, ObjectPath):
        return "o"
    if isinstance(value, str):
        return "s"
    if isinstance(value, (bytes, bytearray)):
        return "ay"
    if isinstance(value, dict):
        return "a{sv}"
    if isinstance(value, (list, tuple)):
        if value and all(isinstance(v, str) for v in value):
            return "as"
        return "av"
    raise TypeError(f"não sei serializar {type(value).__name__} como variante")


# --------------------------------------------------------------------------
# Serialização
# --------------------------------------------------------------------------

class _Writer:
    def __init__(self, start_offset: int = 0):
        self.buf = bytearray()
        self.base = start_offset

    def _align(self, n: int) -> None:
        pad = (-(self.base + len(self.buf))) % n
        if pad:
            self.buf += b"\0" * pad

    def write(self, t, v) -> None:
        c = _code(t)
        self._align(_ALIGN[c])
        if c in _FIXED:
            fmt = _FIXED[c][0]
            if c == "b":
                v = 1 if v else 0
            elif c == "d":
                v = float(v)
            else:
                v = int(v)
            self.buf += struct.pack("<" + fmt, v)
        elif c in "so":
            raw = str(v).encode("utf-8")
            self.buf += struct.pack("<I", len(raw)) + raw + b"\0"
        elif c == "g":
            raw = v.encode("ascii")
            self.buf += bytes([len(raw)]) + raw + b"\0"
        elif c == "v":
            if isinstance(v, Variant):
                sig, val = v.signature, v.value
            else:
                sig, val = guess_signature(v), v
            inner = parse_signature(sig)
            if len(inner) != 1:
                raise ValueError("variante precisa de um único tipo completo")
            self.write("g", sig)
            self.write(inner[0], val)
        elif c == "a":
            elem = t[1]
            len_pos = len(self.buf)
            self.buf += b"\0\0\0\0"
            self._align(_ALIGN[_code(elem)])
            start = len(self.buf)
            if _code(elem) == "{" and isinstance(v, dict):
                items = v.items()
            elif _code(elem) == "y" and isinstance(v, (bytes, bytearray)):
                self.buf += bytes(v)
                items = ()
            else:
                items = v
            for item in items:
                self.write(elem, item)
            struct.pack_into("<I", self.buf, len_pos, len(self.buf) - start)
        elif c == "(":
            fields = t[1]
            if len(v) != len(fields):
                raise ValueError("struct com número de campos incorreto")
            for ft, fv in zip(fields, v):
                self.write(ft, fv)
        elif c == "{":
            self.write(t[1], v[0])
            self.write(t[2], v[1])
        else:  # pragma: no cover - protegido por parse_signature
            raise ValueError(c)


class _Reader:
    def __init__(self, data: bytes, little: bool, offset: int = 0):
        self.data = data
        self.pos = offset
        self.e = "<" if little else ">"

    def _align(self, n: int) -> None:
        self.pos += (-self.pos) % n

    def read(self, t):
        c = _code(t)
        self._align(_ALIGN[c])
        if c in _FIXED:
            fmt, size = _FIXED[c]
            (v,) = struct.unpack_from(self.e + fmt, self.data, self.pos)
            self.pos += size
            return bool(v) if c == "b" else v
        if c in "so":
            (n,) = struct.unpack_from(self.e + "I", self.data, self.pos)
            self.pos += 4
            s = self.data[self.pos:self.pos + n].decode("utf-8", "replace")
            self.pos += n + 1
            return ObjectPath(s) if c == "o" else s
        if c == "g":
            n = self.data[self.pos]
            s = self.data[self.pos + 1:self.pos + 1 + n].decode("ascii")
            self.pos += n + 2
            return s
        if c == "v":
            sig = self.read("g")
            inner = parse_signature(sig)
            return self.read(inner[0])
        if c == "a":
            (n,) = struct.unpack_from(self.e + "I", self.data, self.pos)
            self.pos += 4
            elem = t[1]
            self._align(_ALIGN[_code(elem)])
            end = self.pos + n
            if _code(elem) == "y":
                out = bytes(self.data[self.pos:end])
                self.pos = end
                return out
            if _code(elem) == "{":
                d = {}
                while self.pos < end:
                    k, val = self.read(elem)
                    d[k] = val
                return d
            items = []
            while self.pos < end:
                items.append(self.read(elem))
            return items
        if c == "(":
            return tuple(self.read(ft) for ft in t[1])
        if c == "{":
            return (self.read(t[1]), self.read(t[2]))
        raise ValueError(c)  # pragma: no cover


def marshal_body(signature: str, args) -> bytes:
    w = _Writer()
    types = parse_signature(signature)
    if len(types) != len(args):
        raise ValueError(f"assinatura {signature!r} espera {len(types)} argumentos, recebeu {len(args)}")
    for t, a in zip(types, args):
        w.write(t, a)
    return bytes(w.buf)


def unmarshal_body(signature: str, data: bytes, little: bool = True) -> list:
    r = _Reader(data, little)
    return [r.read(t) for t in parse_signature(signature)]


# --------------------------------------------------------------------------
# Mensagens
# --------------------------------------------------------------------------

_HEADER_FIELDS = {1: "path", 2: "interface", 3: "member", 4: "error_name",
                  5: "reply_serial", 6: "destination", 7: "sender", 8: "signature"}
_FIELD_SIG = {1: "o", 2: "s", 3: "s", 4: "s", 5: "u", 6: "s", 7: "s", 8: "g"}
_HDR_TYPE = parse_signature("a(yv)")[0]


@dataclass
class Message:
    type: int
    serial: int = 0
    flags: int = 0
    path: str | None = None
    interface: str | None = None
    member: str | None = None
    error_name: str | None = None
    reply_serial: int | None = None
    destination: str | None = None
    sender: str | None = None
    signature: str = ""
    body: list = field(default_factory=list)

    def encode(self) -> bytes:
        body = marshal_body(self.signature, self.body) if self.signature else b""
        fields = []
        for code, name in _HEADER_FIELDS.items():
            val = getattr(self, name)
            if name == "signature":
                if not val:
                    continue
            elif val is None:
                continue
            fields.append((code, Variant(_FIELD_SIG[code], val)))
        w = _Writer()
        w.buf += struct.pack("<cBBBII", b"l", self.type, self.flags, 1, len(body), self.serial)
        w.write(_HDR_TYPE, fields)
        w._align(8)
        return bytes(w.buf) + body

    @classmethod
    def decode(cls, data: bytes) -> "Message":
        little = data[0:1] == b"l"
        e = "<" if little else ">"
        mtype, flags, _ver = data[1], data[2], data[3]
        body_len, serial = struct.unpack_from(e + "II", data, 4)
        r = _Reader(data, little, 12)
        fields = r.read(_HDR_TYPE)
        r._align(8)
        msg = cls(type=mtype, serial=serial, flags=flags)
        for code, val in fields:
            name = _HEADER_FIELDS.get(code)
            if name:
                setattr(msg, name, val)
        if msg.signature:
            body = data[r.pos:r.pos + body_len]
            msg.body = unmarshal_body(msg.signature, body, little)
        return msg


def _message_length(head: bytes) -> int:
    """Tamanho total da mensagem a partir dos 16 primeiros bytes."""
    e = "<" if head[0:1] == b"l" else ">"
    body_len, _serial, fields_len = struct.unpack_from(e + "III", head, 4)
    header_len = 16 + fields_len
    header_len += (-header_len) % 8
    return header_len + body_len


# --------------------------------------------------------------------------
# Conexão
# --------------------------------------------------------------------------

def session_bus_address() -> str:
    addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    if addr:
        return addr
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return f"unix:path={runtime}/bus"


def _connect_socket(address: str) -> socket.socket:
    errors = []
    for entry in address.split(";"):
        if not entry.startswith("unix:"):
            continue
        params = dict(p.split("=", 1) for p in entry[5:].split(",") if "=" in p)
        if "path" in params:
            target = unquote(params["path"])
        elif "abstract" in params:
            target = "\0" + unquote(params["abstract"])
        else:
            continue
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.settimeout(5)
            s.connect(target)
            return s
        except OSError as exc:
            errors.append(str(exc))
            s.close()
    raise DBusError("org.lurdens.NoBus", f"não foi possível conectar ao barramento ({'; '.join(errors) or address})")


def _authenticate(sock: socket.socket) -> None:
    uid_hex = str(os.getuid()).encode().hex()
    sock.sendall(b"\0AUTH EXTERNAL " + uid_hex.encode() + b"\r\n")
    buf = b""
    while b"\r\n" not in buf:
        chunk = sock.recv(256)
        if not chunk:
            raise DBusError("org.lurdens.AuthFailed", "conexão encerrada durante a autenticação")
        buf += chunk
    line = buf.split(b"\r\n", 1)[0]
    if not line.startswith(b"OK"):
        raise DBusError("org.lurdens.AuthFailed", line.decode(errors="replace"))
    sock.sendall(b"BEGIN\r\n")


class _Pending:
    __slots__ = ("event", "reply", "callback")

    def __init__(self, callback=None):
        self.event = threading.Event()
        self.reply: Message | None = None
        self.callback = callback


class Connection:
    """Conexão com o barramento de sessão.

    Uma thread leitora recebe todas as mensagens. Respostas são entregues às
    chamadas pendentes; sinais são repassados aos assinantes. Os callbacks
    rodam na thread leitora e, por isso, não devem fazer chamadas
    bloqueantes — o cliente MPRIS os encaminha para sua própria fila.
    """

    def __init__(self, address: str | None = None):
        self._sock = _connect_socket(address or session_bus_address())
        try:
            _authenticate(self._sock)
        except (OSError, DBusError) as exc:
            self._sock.close()
            if isinstance(exc, DBusError):
                raise
            raise DBusError("org.lurdens.AuthFailed", str(exc)) from exc
        self._sock.settimeout(None)
        self._serials = itertools.count(1)
        self._send_lock = threading.Lock()
        self._pending: dict[int, _Pending] = {}
        self._pending_lock = threading.RLock()
        self._signal_handlers: list[Callable[[Message], None]] = []
        self._disconnect_handlers: list[Callable[[], None]] = []
        self._closed = False
        self._reader = threading.Thread(target=self._read_loop, name="lurdens-dbus-reader", daemon=True)
        self._reader.start()
        (self.unique_name,) = self.call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                        "org.freedesktop.DBus", "Hello")

    # -- envio -------------------------------------------------------------
    def _send(self, msg: Message) -> int:
        if self._closed:
            raise DBusError("org.lurdens.Disconnected", "conexão encerrada")
        msg.serial = next(self._serials)
        data = msg.encode()
        with self._send_lock:
            try:
                self._sock.sendall(data)
            except OSError as exc:
                self._mark_closed()
                raise DBusError("org.lurdens.Disconnected", str(exc)) from exc
        return msg.serial

    def _call_msg(self, dest, path, iface, member, signature, args) -> Message:
        return Message(METHOD_CALL, destination=dest, path=path, interface=iface,
                       member=member, signature=signature, body=list(args))

    def call(self, dest: str, path: str, iface: str, member: str,
             signature: str = "", args=(), timeout: float = 5.0) -> list:
        """Chamada bloqueante. Não use na thread leitora nem na interface."""
        if threading.current_thread() is self._reader:
            raise RuntimeError("chamada bloqueante na thread leitora causaria deadlock")
        msg = self._call_msg(dest, path, iface, member, signature, args)
        pending = _Pending()
        with self._pending_lock:
            serial = self._send_reserve(msg, pending)
        if not pending.event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(serial, None)
            raise DBusError("org.freedesktop.DBus.Error.Timeout", f"{member} não respondeu em {timeout:.0f}s")
        return self._result(pending.reply)

    def call_async(self, dest, path, iface, member, signature="", args=(),
                   callback: Callable[[Exception | None, list | None], None] | None = None) -> None:
        """Chamada não bloqueante; o callback roda na thread leitora."""
        msg = self._call_msg(dest, path, iface, member, signature, args)
        if callback is None:
            msg.flags |= FLAG_NO_REPLY_EXPECTED
            self._send(msg)
            return
        pending = _Pending(callback)
        with self._pending_lock:
            self._send_reserve(msg, pending)

    def _send_reserve(self, msg: Message, pending: _Pending) -> int:
        # chamado com _pending_lock adquirido para registrar antes da resposta chegar
        serial = self._send(msg)
        self._pending[serial] = pending
        return serial

    @staticmethod
    def _result(reply: Message | None) -> list:
        if reply is None:
            raise DBusError("org.lurdens.Disconnected", "conexão encerrada antes da resposta")
        if reply.type == ERROR:
            text = reply.body[0] if reply.body and isinstance(reply.body[0], str) else ""
            raise DBusError(reply.error_name or "org.freedesktop.DBus.Error.Failed", text)
        return reply.body

    # -- sinais --------------------------------------------------------------
    def add_signal_handler(self, handler: Callable[[Message], None]) -> None:
        self._signal_handlers.append(handler)

    def add_disconnect_handler(self, handler: Callable[[], None]) -> None:
        self._disconnect_handlers.append(handler)

    def add_match(self, rule: str) -> None:
        self.call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                  "AddMatch", "s", (rule,))

    # -- leitura -------------------------------------------------------------
    def _recv_exact(self, n: int) -> bytes:
        chunks, got = [], 0
        while got < n:
            chunk = self._sock.recv(n - got)
            if not chunk:
                raise ConnectionError("barramento fechou a conexão")
            chunks.append(chunk)
            got += len(chunk)
        return b"".join(chunks)

    def _read_loop(self) -> None:
        try:
            while not self._closed:
                head = self._recv_exact(16)
                rest = self._recv_exact(_message_length(head) - 16)
                try:
                    msg = Message.decode(head + rest)
                except Exception:  # mensagem que não sabemos decodificar: ignora
                    continue
                self._dispatch(msg)
        except (OSError, ConnectionError):
            pass
        finally:
            self._mark_closed()

    def _dispatch(self, msg: Message) -> None:
        if msg.type in (METHOD_RETURN, ERROR) and msg.reply_serial is not None:
            with self._pending_lock:
                pending = self._pending.pop(msg.reply_serial, None)
            if pending is None:
                return
            pending.reply = msg
            pending.event.set()
            if pending.callback:
                try:
                    pending.callback(None, self._result(msg))
                except DBusError as exc:
                    pending.callback(exc, None)
                except Exception:
                    pass
        elif msg.type == SIGNAL:
            for h in list(self._signal_handlers):
                try:
                    h(msg)
                except Exception:
                    pass
        elif msg.type == METHOD_CALL and not (msg.flags & FLAG_NO_REPLY_EXPECTED):
            # Não exportamos objetos: responde com erro para não deixar o chamador esperando.
            err = Message(ERROR, error_name="org.freedesktop.DBus.Error.UnknownMethod",
                          reply_serial=msg.serial, destination=msg.sender,
                          signature="s", body=["Lurdens não exporta objetos"])
            try:
                self._send(err)
            except DBusError:
                pass

    def _mark_closed(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._sock.close()
        except OSError:
            pass
        with self._pending_lock:
            pending, self._pending = self._pending, {}
        for p in pending.values():
            p.event.set()
            if p.callback:
                try:
                    p.callback(DBusError("org.lurdens.Disconnected", "conexão encerrada"), None)
                except Exception:
                    pass
        for h in list(self._disconnect_handlers):
            try:
                h()
            except Exception:
                pass

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._mark_closed()
