# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['python_version/ui/main_gui.py'],
    pathex=['python_version'],
    binaries=[],
    datas=[],
    hiddenimports=['PIL', 'PIL._tkinter_finder', 'python_version.core', 'python_version.hardware', 'python_version.utils', 'python_version.ui'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'pandas', 'tkinter.test', 'unittest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='R1_BIOS_Programmer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['python_version/ui/assets/logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='R1_BIOS_Programmer',
)
