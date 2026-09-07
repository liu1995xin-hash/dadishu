# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import PureWindowsPath


BUILD_NAME = os.environ.get("MOLE_GAME_BUILD_NAME", "药材打地鼠")
CONSOLE_BUILD = os.environ.get("MOLE_GAME_CONSOLE_BUILD") == "1"


QT_RUNTIME_FILES = {
    "pyside6\\qt6core.dll",
    "pyside6\\qt6gui.dll",
    "pyside6\\qt6widgets.dll",
    "pyside6\\qtcore.pyd",
    "pyside6\\qtgui.pyd",
    "pyside6\\qtwidgets.pyd",
    "pyside6\\pyside6.abi3.dll",
    "pyside6\\msvcp140.dll",
    "pyside6\\msvcp140_1.dll",
    "pyside6\\msvcp140_2.dll",
    "pyside6\\vcruntime140.dll",
    "pyside6\\vcruntime140_1.dll",
    "pyside6\\plugins\\platforms\\qwindows.dll",
    "pyside6\\plugins\\styles\\qmodernwindowsstyle.dll",
}

# The build environment puts Poppler's versioned ICU compatibility DLLs on
# PATH. They do not provide the unversioned Windows ICU exports Qt expects.
# Excluding them lets Qt use the matching ICU supplied by Windows 10/11.
INCOMPATIBLE_BUILD_DLLS = {"icudt78.dll", "icuuc.dll"}


def normalized_destination(entry):
    return str(PureWindowsPath(entry[0])).lower()


def keep_binary(entry):
    destination = normalized_destination(entry)
    if destination in INCOMPATIBLE_BUILD_DLLS:
        return False
    if not destination.startswith("pyside6\\"):
        return True
    return destination in QT_RUNTIME_FILES


a = Analysis(
    ["mole_game.py"],
    pathex=[],
    binaries=[],
    datas=[("素材", "素材")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtMultimedia",
        "PySide6.QtNetwork",
        "PySide6.QtOpenGL",
        "PySide6.QtPdf",
        "PySide6.QtPrintSupport",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtSql",
        "PySide6.QtSvg",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ],
    noarchive=False,
    optimize=2,
)

# QtGui's general-purpose hook discovers plugins for features this game never
# uses. Keep only the three imported Qt modules, the Windows platform/style
# plugins, and their C++ runtime. The six PNG assets are retained in a.datas.
a.binaries = [entry for entry in a.binaries if keep_binary(entry)]
a.datas = [
    entry
    for entry in a.datas
    if not normalized_destination(entry).startswith("pyside6\\translations\\")
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=BUILD_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=CONSOLE_BUILD,
    disable_windowed_traceback=False,
)
