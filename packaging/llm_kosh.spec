# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['../llm_kosh_cli.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'llm_kosh.mcp_server',
        'llm_kosh.service',
        'llm_kosh.daemon',
        'mcp.server.fastmcp',
        'watchdog.events',
        'watchdog.observers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The standalone desktop sidecar ships the offline TF-IDF backend. Large
    # ML stacks remain available to pip users through the `semantic` extra.
    excludes=[
        'sentence_transformers',
        'transformers',
        'torch',
        'torchvision',
        'torchaudio',
        'tensorflow',
        'numpy',
        'scipy',
        'sklearn',
        'pandas',
        'matplotlib',
    ],
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
    name='llm-kosh',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
