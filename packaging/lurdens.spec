# -*- mode: python ; coding: utf-8 -*-
# Empacotamento do Lurdens com o PyInstaller (Windows e macOS).
#
#   python -m pip install -r requirements.txt pyinstaller pillow
#   python -m PyInstaller packaging/lurdens.spec --noconfirm
#
# Resultado: dist/Lurdens/ (Windows, pasta com Lurdens.exe) ou
# dist/Lurdens.app (macOS). No Linux o caminho recomendado continua sendo
# ./install.sh; este arquivo também funciona lá, para testes.

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent          # noqa: F821 - definido pelo PyInstaller
PKG = ROOT / "lurdens"
VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', (PKG / "__init__.py").read_text(encoding="utf-8")).group(1)
ICON = str(PKG / "resources" / "icons" / "lurdens-512.png")   # o PyInstaller converte (precisa do Pillow)

datas = [(str(PKG / "qml"), "lurdens/qml"), (str(PKG / "resources"), "lurdens/resources")]
binaries = []
hiddenimports = [
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickControls2", "PySide6.QtNetwork",
    "PySide6.QtSvg",
    # backends importados sob demanda por create_backend()
    "lurdens.mpris", "lurdens.backends.smtc", "lurdens.backends.applescript",
]

if sys.platform == "win32":
    # O PyWinRT é importado só dentro das funções do backend; coleta tudo explicitamente.
    d, b, h = collect_all("winrt")
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Lurdens",
    console=False,
    icon=ICON,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="Lurdens", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Lurdens.app",
        icon=ICON,
        bundle_identifier="io.github.lucasks2001.lurdens",
        version=VERSION,
        info_plist={
            "CFBundleName": "Lurdens",
            "CFBundleDisplayName": "Lurdens",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            # Texto do pedido de permissão de Automação (controlar o Spotify).
            "NSAppleEventsUsageDescription":
                "O Lurdens controla o Spotify (tocar, pausar, trocar de música) e mostra o que está tocando.",
        },
    )
