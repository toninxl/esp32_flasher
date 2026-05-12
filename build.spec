# -*- mode: python ; coding: utf-8 -*-
"""Configuração PyInstaller para gerar executável do ESP32 Flasher GUI."""

import os
import importlib

# Localizar pacote customtkinter para incluir como data
ctk_path = os.path.dirname(importlib.import_module("customtkinter").__file__)

a = Analysis(
    ['esp32_flasher/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        (ctk_path, 'customtkinter'),
    ],
    hiddenimports=[
        'esptool',
        'esptool.__init__',
        'esptool.cmds',
        'esptool.targets',
        'esptool.loader',
        'esptool.util',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'serial.tools.list_ports_common',
        'serial.tools.list_ports_windows',
        'serial.tools.list_ports_linux',
        'serial.tools.list_ports_osx',
        'customtkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ESP32_Flasher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
