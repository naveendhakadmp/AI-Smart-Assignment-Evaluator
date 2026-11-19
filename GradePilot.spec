import os

from PyInstaller.utils.hooks import collect_all

project_root = os.path.abspath(SPECPATH)
pymupdf_datas, pymupdf_binaries, pymupdf_hiddenimports = collect_all("pymupdf")

analysis = Analysis(
    ["launcher.py"],
    pathex=[project_root],
    binaries=pymupdf_binaries,
    datas=[
        (os.path.join(project_root, "templates"), "templates"),
        (os.path.join(project_root, "static"), "static"),
        *pymupdf_datas,
    ],
    hiddenimports=[
        *pymupdf_hiddenimports,
        "pytesseract.pytesseract",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="GradePilot",
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
    icon=os.path.join(project_root, "static", "gradepilot.ico"),
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GradePilot",
)
