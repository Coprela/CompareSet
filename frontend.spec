# -*- mode: python ; coding: utf-8 -*-


import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

a = Analysis(
    ['app.py'],
    pathex=[BASE_DIR],
    binaries=[],
    datas=[(os.path.join('Imagem', 'logo.png'), 'Imagem'),
           (os.path.join('Imagem', 'Icon janela.ico'), 'Imagem')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='frontend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join('Imagem', 'Icon arquivo.ico')],
)
