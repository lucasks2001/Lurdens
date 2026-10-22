#!/usr/bin/env python3
"""Spotify simulado no D-Bus (somente para testes e desenvolvimento).

Publica o nome org.mpris.MediaPlayer2.spotify com as interfaces MPRIS e
uma interface extra de controle (org.lurdens.MockControl) usada pelos testes
automatizados. É uma implementação independente (dbus-python + GLib), para
que o cliente do Lurdens seja testado contra outro código.

ATENÇÃO: não rode junto com o Spotify verdadeiro — os nomes colidem.

Dependências no Fedora: python3-dbus e python3-gobject.
Uso:  python3 tests/mock_spotify.py [--legacy] [--name sufixo] [--art-dir pasta]
"""

import argparse
import os
import sys
import time

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

ROOT = "org.mpris.MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
PROPS = "org.freedesktop.DBus.Properties"
CTRL = "org.lurdens.MockControl"
PATH = "/org/mpris/MediaPlayer2"


def make_tracks(art_dir):
    def art(name):
        if not art_dir:
            return ""
        p = os.path.join(art_dir, name)
        return "file://" + os.path.abspath(p) if os.path.exists(p) else ""
    return [
        dict(id="/com/spotify/track/0001", title="Hachura em Diagonal", artist=["Trio Nanquim"],
             album="Técnicas de Sombra", length=185_000_000, art=art("capa1.png")),
        dict(id="/com/spotify/track/0002",
             title="Um Título Propositalmente Muito Longo Para Testar a Rolagem do Texto na Interface",
             artist=["Pontilhismo", "Cruzada Feat. Trama"], album="Esferas", length=242_000_000,
             art=art("capa2.png")),
        dict(id="/com/spotify/track/0003", title="Sem Capa", artist=["Artista Desconhecido"],
             album="", length=61_000_000, art=""),
    ]


class MockPlayer(dbus.service.Object):
    def __init__(self, bus, path, legacy, art_dir):
        super().__init__(bus, path)
        self.legacy = legacy
        self.tracks = make_tracks(art_dir)
        self.index = 0
        self.status = "Paused"
        self.position = 0
        self.started = None
        self.volume = 0.7
        self.shuffle = False
        self.loop = "None"
        self.calls = []

    # -- utilidades --------------------------------------------------------
    def pos(self):
        if self.status == "Playing" and self.started is not None:
            return min(self.position + int((time.monotonic() - self.started) * 1e6),
                       self.tracks[self.index]["length"])
        return self.position

    def freeze(self):
        self.position = self.pos()
        self.started = time.monotonic() if self.status == "Playing" else None

    def metadata(self):
        t = self.tracks[self.index]
        md = {
            "mpris:trackid": dbus.ObjectPath(t["id"]),
            "mpris:length": dbus.UInt64(t["length"]),  # Spotify usa 't'
            "xesam:title": dbus.String(t["title"]),
            "xesam:artist": dbus.Array(t["artist"], signature="s"),
            "xesam:album": dbus.String(t["album"]),
            "xesam:url": dbus.String("https://open.spotify.com/track/" + t["id"][-4:]),
        }
        if t["art"]:
            md["mpris:artUrl"] = dbus.String(t["art"])
        return dbus.Dictionary(md, signature="sv")

    def player_props(self):
        p = {
            "PlaybackStatus": dbus.String(self.status),
            "Metadata": self.metadata(),
            "Rate": dbus.Double(1.0),
            "Position": dbus.Int64(self.pos()),
            "CanGoNext": True, "CanGoPrevious": True, "CanPlay": True,
            "CanPause": True, "CanSeek": True, "CanControl": True,
        }
        if not self.legacy:
            p["Volume"] = dbus.Double(self.volume)
            p["Shuffle"] = dbus.Boolean(self.shuffle)
            p["LoopStatus"] = dbus.String(self.loop)
        return p

    def root_props(self):
        return {"Identity": dbus.String("Spotify"), "DesktopEntry": dbus.String("spotify"),
                "CanQuit": True, "CanRaise": False, "HasTrackList": False}

    def changed(self, iface, props):
        self.PropertiesChanged(iface, dbus.Dictionary(props, signature="sv"), dbus.Array([], signature="s"))

    def change_track(self, delta):
        self.index = (self.index + delta) % len(self.tracks)
        self.position = 0
        self.started = time.monotonic() if self.status == "Playing" else None
        # Como o Spotify real: manda metadados, mas não a posição.
        self.changed(PLAYER, {"Metadata": self.metadata()})

    def set_status(self, status):
        self.freeze()
        self.status = status
        self.started = time.monotonic() if status == "Playing" else None
        self.changed(PLAYER, {"PlaybackStatus": status})

    # -- org.mpris.MediaPlayer2 ---------------------------------------------
    @dbus.service.method(ROOT)
    def Raise(self):
        self.calls.append("Raise")

    @dbus.service.method(ROOT)
    def Quit(self):
        self.calls.append("Quit")
        GLib.idle_add(loop.quit)

    # -- org.mpris.MediaPlayer2.Player --------------------------------------
    @dbus.service.method(PLAYER)
    def PlayPause(self):
        self.calls.append("PlayPause")
        self.set_status("Paused" if self.status == "Playing" else "Playing")

    @dbus.service.method(PLAYER)
    def Play(self):
        self.calls.append("Play")
        self.set_status("Playing")

    @dbus.service.method(PLAYER)
    def Pause(self):
        self.calls.append("Pause")
        self.set_status("Paused")

    @dbus.service.method(PLAYER)
    def Stop(self):
        self.calls.append("Stop")
        self.set_status("Stopped")

    @dbus.service.method(PLAYER)
    def Next(self):
        self.calls.append("Next")
        self.change_track(+1)

    @dbus.service.method(PLAYER)
    def Previous(self):
        self.calls.append("Previous")
        self.change_track(-1)

    @dbus.service.method(PLAYER, in_signature="x")
    def Seek(self, offset):
        self.calls.append(f"Seek:{int(offset)}")
        self.freeze()
        self.position = max(0, self.position + int(offset))
        self.Seeked(dbus.Int64(self.position))

    @dbus.service.method(PLAYER, in_signature="ox")
    def SetPosition(self, track_id, position):
        self.calls.append(f"SetPosition:{track_id}:{int(position)}")
        if str(track_id) != self.tracks[self.index]["id"]:
            return
        self.freeze()
        self.position = int(position)
        self.Seeked(dbus.Int64(self.position))

    @dbus.service.method(PLAYER, in_signature="s")
    def OpenUri(self, uri):
        self.calls.append(f"OpenUri:{uri}")

    @dbus.service.signal(PLAYER, signature="x")
    def Seeked(self, position):
        pass

    # -- org.freedesktop.DBus.Properties ------------------------------------
    @dbus.service.method(PROPS, in_signature="ss", out_signature="v")
    def Get(self, iface, prop):
        props = self.player_props() if iface == PLAYER else self.root_props()
        if prop not in props:
            raise dbus.exceptions.DBusException(
                f"sem a propriedade {prop}", name="org.freedesktop.DBus.Error.InvalidArgs")
        return props[prop]

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, iface):
        if iface == PLAYER:
            return self.player_props()
        if iface == ROOT:
            return self.root_props()
        return {}

    @dbus.service.method(PROPS, in_signature="ssv")
    def Set(self, iface, prop, value):
        self.calls.append(f"Set:{prop}:{value}")
        if self.legacy and prop in ("Volume", "Shuffle", "LoopStatus"):
            raise dbus.exceptions.DBusException(
                "não suportado", name="org.freedesktop.DBus.Error.NotSupported")
        if prop == "Volume":
            self.volume = max(0.0, min(1.0, float(value)))
            self.changed(PLAYER, {"Volume": dbus.Double(self.volume)})
        elif prop == "Shuffle":
            self.shuffle = bool(value)
            self.changed(PLAYER, {"Shuffle": dbus.Boolean(self.shuffle)})
        elif prop == "LoopStatus":
            self.loop = str(value)
            self.changed(PLAYER, {"LoopStatus": dbus.String(self.loop)})

    @dbus.service.signal(PROPS, signature="sa{sv}as")
    def PropertiesChanged(self, iface, changed, invalidated):
        pass

    # -- controle para testes ------------------------------------------------
    @dbus.service.method(CTRL, out_signature="as")
    def Calls(self):
        return self.calls

    @dbus.service.method(CTRL, in_signature="s")
    def SetStatus(self, status):
        self.set_status(str(status))

    @dbus.service.method(CTRL)
    def ExternalNext(self):
        """Simula troca de faixa feita fora do Lurdens (atalho, KDE, celular)."""
        self.change_track(+1)

    @dbus.service.method(CTRL, in_signature="x")
    def ExternalSeek(self, position):
        self.freeze()
        self.position = int(position)
        self.Seeked(dbus.Int64(self.position))

    @dbus.service.method(CTRL, out_signature="x")
    def RealPosition(self):
        return dbus.Int64(self.pos())

    @dbus.service.method(CTRL)
    def Exit(self):
        GLib.idle_add(loop.quit)


def main():
    global loop
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--legacy", action="store_true",
                    help="simula Spotify antigo, sem Volume/Shuffle/LoopStatus")
    ap.add_argument("--name", default="", help="sufixo do nome (ex.: instance123)")
    ap.add_argument("--art-dir", default=os.path.join(os.path.dirname(__file__), "assets"))
    ap.add_argument("--play", action="store_true", help="começa tocando")
    args = ap.parse_args()

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = "org.mpris.MediaPlayer2.spotify" + (("." + args.name) if args.name else "")
    player = MockPlayer(bus, PATH, args.legacy, args.art_dir)
    if args.play:
        player.status = "Playing"
        player.started = time.monotonic()
    bus_name = dbus.service.BusName(name, bus, do_not_queue=True)  # noqa: F841
    print(f"mock pronto: {name}", flush=True)
    loop = GLib.MainLoop()
    loop.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
