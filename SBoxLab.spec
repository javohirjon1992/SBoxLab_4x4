# PyInstaller one-file build specification for SBoxLab 4x4 Experimental Platform.
from pathlib import Path

project = Path(SPEC).resolve().parent if 'SPEC' in globals() else Path.cwd()

a = Analysis(
    ['desktop_app.py'],
    pathex=[str(project)],
    binaries=[],
    datas=[
        (str(project / 'sboxlab' / 'data'), 'sboxlab/data'),
        (str(project / 'assets'), 'assets'),
    ],
    hiddenimports=['PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['streamlit'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SBoxLab',
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
    icon=str(project / 'assets' / 'sboxlab.ico'),
)
