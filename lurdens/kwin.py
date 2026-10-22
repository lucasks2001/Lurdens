"""'Sempre no topo' no KDE Plasma em Wayland.

O Wayland não oferece a aplicações comuns um protocolo para pedir "manter
acima". No Plasma, a forma suportada é um script do KWin, carregado pela API
D-Bus de scripting do próprio KWin (org.kde.KWin /Scripting). O script
procura a janela pelo PID do Lurdens e ajusta keepAbove. No X11 basta a
dica de janela do Qt, então este módulo não é usado.
"""

from __future__ import annotations

import os
import tempfile
import threading
import time

from .dbus.wire import Connection, DBusError

PLUGIN = "lurdens-keepabove"

SCRIPT_TEMPLATE = """\
(function () {
    var wins = workspace.windowList ? workspace.windowList() : workspace.clientList();
    for (var i = 0; i < wins.length; ++i) {
        var w = wins[i];
        if (w.pid === %(pid)d || w.resourceClass === "lurdens") {
            w.keepAbove = %(above)s;
        }
    }
})();
"""


def build_script(pid: int, above: bool) -> str:
    return SCRIPT_TEMPLATE % {"pid": int(pid), "above": "true" if above else "false"}


def set_keep_above(above: bool, pid: int | None = None, address: str | None = None) -> str:
    """Aplica keepAbove via KWin. Retorna "" em caso de sucesso ou a mensagem de erro."""
    pid = pid or os.getpid()
    fd, path = tempfile.mkstemp(prefix="lurdens-kwin-", suffix=".js")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(build_script(pid, above))
        conn = Connection(address)
        try:
            svc, obj, iface = "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting"
            try:
                conn.call(svc, obj, iface, "unloadScript", "s", (PLUGIN,))
            except DBusError:
                pass
            (script_id,) = conn.call(svc, obj, iface, "loadScript", "ss", (path, PLUGIN))
            if int(script_id) < 0:
                return "o KWin recusou o script"
            ran = False
            for script_path in (f"/Scripting/Script{int(script_id)}", f"/{int(script_id)}"):
                try:
                    conn.call(svc, script_path, "org.kde.kwin.Script", "run")
                    ran = True
                    break
                except DBusError:
                    continue
            if not ran:
                conn.call(svc, obj, iface, "start")
            time.sleep(1.0)  # dá tempo ao KWin de executar antes de descarregar
            try:
                conn.call(svc, obj, iface, "unloadScript", "s", (PLUGIN,))
            except DBusError:
                pass
            return ""
        finally:
            conn.close()
    except DBusError as exc:
        return f"KWin indisponível ({exc.name})"
    except OSError as exc:
        return str(exc)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def set_keep_above_async(above: bool, done=None) -> None:
    def run():
        err = set_keep_above(above)
        if done:
            done(err)
    threading.Thread(target=run, name="lurdens-kwin", daemon=True).start()
