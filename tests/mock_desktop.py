#!/usr/bin/env python3
"""Serviços do desktop simulados para testes: notificações e kglobalaccel.

Implementa só o que o Lurdens usa, seguindo a interface D-Bus publicada do
KDE (kglobalacceld.h / org.kde.kglobalaccel.Component.xml). Não substitui o
teste no Plasma real. Requer python3-dbus e python3-gobject.
Uso: python3 tests/mock_desktop.py [--no-kglobalaccel] [--taken TECLA_INT]
"""

import argparse
import sys

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

CTRL = "org.lurdens.MockDesktop"


class Notifications(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(bus, "/org/freedesktop/Notifications")
        self.log = []
        self.next_id = 1

    @dbus.service.method("org.freedesktop.Notifications", in_signature="susssasa{sv}i", out_signature="u")
    def Notify(self, app, replaces, icon, summary, body, actions, hints, timeout):
        nid = int(replaces) or self.next_id
        if not int(replaces):
            self.next_id += 1
        self.log.append({"app": str(app), "replaces": int(replaces), "id": nid, "icon": str(icon),
                         "summary": str(summary), "body": str(body),
                         "image": str(hints.get("image-path", "")),
                         "desktop": str(hints.get("desktop-entry", ""))})
        return dbus.UInt32(nid)

    @dbus.service.method("org.freedesktop.Notifications", out_signature="as")
    def GetCapabilities(self):
        return ["body", "icon-static"]

    @dbus.service.method(CTRL, out_signature="s")
    def Log(self):
        import json
        return json.dumps(self.log)


class Component(dbus.service.Object):
    def __init__(self, bus, name):
        super().__init__(bus, f"/component/{name}")
        self.name = name

    @dbus.service.signal("org.kde.kglobalaccel.Component", signature="ssx")
    def globalShortcutPressed(self, component, action, timestamp):
        pass


class KGlobalAccel(dbus.service.Object):
    def __init__(self, bus, taken):
        super().__init__(bus, "/kglobalaccel")
        self.bus = bus
        self.registered = {}
        self.active = {}
        self.default = {}
        self.taken = set(taken)        # teclas já usadas por "outro programa"
        self.components = {}

    def _key(self, aid):
        return (str(aid[0]), str(aid[1]))

    @dbus.service.method("org.kde.KGlobalAccel", in_signature="as")
    def doRegister(self, aid):
        self.registered[self._key(aid)] = [str(x) for x in aid]
        comp = str(aid[0])
        if comp not in self.components:
            self.components[comp] = Component(self.bus, comp)

    @dbus.service.method("org.kde.KGlobalAccel", in_signature="asa(ai)u", out_signature="a(ai)")
    def setShortcutKeys(self, aid, keys, flags):
        k = self._key(aid)
        wanted = [int(x) for seq in keys for x in seq[0] if int(x)]
        if flags & 8:   # IsDefault
            self.default[k] = wanted
            return dbus.Array([], signature="(ai)")
        if (flags & 2) and not (flags & 4) and k in self.active:   # SetPresent + autoload
            got = self.active[k]
        else:
            got = [x for x in wanted if x not in self.taken
                   and all(v != [x] or kk == k for kk, v in self.active.items())]
            self.active[k] = got
        return dbus.Array([dbus.Struct((dbus.Array(got + [0] * (4 - len(got)), signature="i"),))
                           for _ in [0] if got], signature="(ai)")

    @dbus.service.method("org.kde.KGlobalAccel", in_signature="as", out_signature="a(ai)")
    def shortcutKeys(self, aid):
        got = self.active.get(self._key(aid), [])
        return dbus.Array([dbus.Struct((dbus.Array(got + [0] * (4 - len(got)), signature="i"),))
                           for _ in [0] if got], signature="(ai)")

    @dbus.service.signal("org.kde.KGlobalAccel", signature="asa(ai)")
    def yourShortcutsChanged(self, aid, keys):
        pass

    # -- controle -----------------------------------------------------------
    @dbus.service.method(CTRL, in_signature="ss")
    def Press(self, component, action):
        if component not in self.components:
            self.components[component] = Component(self.bus, component)
        self.components[component].globalShortcutPressed(component, action, dbus.Int64(0))

    @dbus.service.method(CTRL, in_signature="ssi")
    def UserChange(self, component, action, key):
        """Simula o usuário trocando a tecla em Configurações do Sistema."""
        k = (component, action)
        self.active[k] = [int(key)]
        aid = self.registered[k]
        self.yourShortcutsChanged(aid, dbus.Array([dbus.Struct((dbus.Array([int(key), 0, 0, 0], signature="i"),))],
                                                  signature="(ai)"))

    @dbus.service.method(CTRL, out_signature="s")
    def State(self):
        import json
        return json.dumps({"registered": ["/".join(k) for k in self.registered],
                           "active": {"/".join(k): v for k, v in self.active.items()},
                           "default": {"/".join(k): v for k, v in self.default.items()}})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-kglobalaccel", action="store_true")
    ap.add_argument("--taken", type=int, action="append", default=[])
    args = ap.parse_args()
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    keep = [Notifications(bus), dbus.service.BusName("org.freedesktop.Notifications", bus)]
    if not args.no_kglobalaccel:
        keep += [KGlobalAccel(bus, args.taken), dbus.service.BusName("org.kde.kglobalaccel", bus)]
    print("desktop pronto", flush=True)
    GLib.MainLoop().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
