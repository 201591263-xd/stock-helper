# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('server', 'server'), ('client', 'client')],
    hiddenimports=[
                   'client', 'client.api', 'client.dashboard', 'client.login', 'client.chat', 'client.styles',
                   'flask', 'flask.json', 'flask_cors', 'requests', 'urllib3', 'charset_normalizer',
                   'sqlite3', 'pandas'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['server', 'server.server', 'server.db', 'server.ashare_quote', 'ashare_quote'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='推票助手_v4',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='推票助手_v4',
)
