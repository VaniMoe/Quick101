# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['Quick101.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('Quick101.ico', '.'),
        ('Quick101.png', '.'),
        ('pets_data.json', '.'),
        ('pet_data.py', '.')
    ],
    hiddenimports=['PyQt6.QtSvg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5'],
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
    name='Quick101',
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
    icon=['Quick101.ico'],
)
