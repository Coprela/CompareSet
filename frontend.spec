# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['frontend.py'],
    pathex=[],
    binaries=[],
    datas=[('Imagem\\logo.png', 'Imagem'), ('Imagem\\Icon janela.ico', 'Imagem')],
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
    icon=['C:\\Users\\doliveira12\\source\\repos\\CR - Comparador de Revisões\\Imagem\\Icon arquivo.ico'],
)
