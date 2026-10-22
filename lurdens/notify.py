"""Notificações de troca de faixa pelo serviço do desktop (org.freedesktop.Notifications).

O Plasma exibe, agrupa e respeita "Não perturbe" e as preferências por
aplicativo (Configurações do Sistema › Notificações › Lurdens). Cada
notificação substitui a anterior (replaces_id), então trocas rápidas não
empilham avisos. A capa é baixada para um cache local, porque o servidor de
notificações só aceita arquivos locais.
"""

from __future__ import annotations

import hashlib
import logging
import os
import queue
import threading
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import paths
from .dbus.wire import Connection, DBusError

log = logging.getLogger("lurdens.notify")

NOTIFY = ("org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications")


def cache_dir() -> Path:
    return paths.cache_dir() / "covers"


class CoverCache:
    MAX_FILES = 120

    def __init__(self, directory: Path | None = None, timeout: float = 4.0):
        self.dir = directory or cache_dir()
        self.timeout = timeout

    def local_path(self, url: str) -> str:
        """Caminho local da capa ("" se indisponível). Pode bloquear: use fora da UI."""
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.scheme == "file":
            p = unquote(parsed.path)
            return p if os.path.isfile(p) else ""
        if parsed.scheme not in ("http", "https"):
            return ""
        target = self.dir / (hashlib.sha1(url.encode()).hexdigest() + ".img")
        if target.exists() and target.stat().st_size > 0:
            return str(target)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "Lurdens"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read(5_000_000)
            if not data:
                return ""
            tmp = target.with_suffix(".part")
            tmp.write_bytes(data)
            os.replace(tmp, target)
            self._prune()
            return str(target)
        except (OSError, ValueError) as exc:
            log.debug("capa indisponível para notificação: %s", exc)
            return ""

    def _prune(self) -> None:
        try:
            files = sorted(self.dir.glob("*.img"), key=lambda p: p.stat().st_mtime)
            for p in files[: max(0, len(files) - self.MAX_FILES)]:
                p.unlink(missing_ok=True)
        except OSError:
            pass


class Notifier:
    """Envia notificações numa thread própria; só a mais recente pendente é enviada."""

    def __init__(self, address: str | None = None, covers: CoverCache | None = None):
        self._address = address
        self._covers = covers or CoverCache()
        self._q: queue.Queue = queue.Queue()
        self._conn: Connection | None = None
        self._last_id = 0
        self.last_error = ""
        self.sent = 0
        self._thread = threading.Thread(target=self._run, name="lurdens-notify", daemon=True)
        self._thread.start()

    def track(self, title: str, artist: str, album: str, art_url: str) -> None:
        self._q.put(("track", title, artist, album, art_url))

    def message(self, summary: str, body: str = "") -> None:
        self._q.put(("message", summary, body))

    def stop(self) -> None:
        self._q.put(None)

    def wait_idle(self, timeout: float = 5.0) -> None:
        """Para testes: espera a fila esvaziar."""
        done = threading.Event()
        self._q.put(("sync", done))
        done.wait(timeout)

    # ------------------------------------------------------------------
    def _run(self) -> None:
        while True:
            item = self._q.get()
            # descarta pedidos de faixa já superados por outro mais novo
            while item and item[0] == "track":
                try:
                    nxt = self._q.get_nowait()
                except queue.Empty:
                    break
                if nxt is None or nxt[0] != "track":
                    self._q.put(nxt)  # reenfileira e processa depois
                    break
                item = nxt
            if item is None:
                break
            try:
                if item[0] == "sync":
                    item[1].set()
                elif item[0] == "track":
                    _, title, artist, album, art = item
                    body = artist + (f"\n{album}" if album else "")
                    self._send(title, body, self._covers.local_path(art), replace=True)
                else:
                    self._send(item[1], item[2], "", replace=False)
            except Exception as exc:  # notificação nunca derruba o app
                self.last_error = str(exc)
                log.debug("falha ao notificar: %s", exc)
        if self._conn:
            self._conn.close()

    def _send(self, summary: str, body: str, image: str, replace: bool) -> None:
        hints = {"desktop-entry": "lurdens", "urgency": _byte(1), "transient": True}
        if image:
            hints["image-path"] = image
        args = ("Lurdens", self._last_id if replace else 0, "" if image else "lurdens",
                summary, body, [], hints, 5000)
        for attempt in (1, 2):
            try:
                if self._conn is None or self._conn.closed:
                    self._conn = Connection(self._address)
                (nid,) = self._conn.call(*NOTIFY, "Notify", "susssasa{sv}i", args, timeout=3)
                if replace:
                    self._last_id = int(nid)
                self.sent += 1
                self.last_error = ""
                return
            except DBusError as exc:
                self.last_error = str(exc)
                if self._conn is not None and self._conn.closed and attempt == 1:
                    continue
                return


def _byte(v: int):
    from .dbus.wire import Variant
    return Variant("y", v)
