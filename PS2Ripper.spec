# -*- mode: python ; coding: utf-8 -*-
import importlib.metadata
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

project_root = SPECPATH
source_root = os.path.join(project_root, "src")
python_license = os.path.join(sys.base_prefix, "LICENSE.txt")
pyinstaller_distribution = importlib.metadata.distribution("pyinstaller")
pyinstaller_license = next(
    str(pyinstaller_distribution.locate_file(item))
    for item in pyinstaller_distribution.files or ()
    if str(item).replace("\\", "/").endswith("licenses/COPYING.txt")
)

a = Analysis(
    [os.path.join(source_root, "ps2ripper", "app.py")],
    pathex=[source_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, "THIRD_PARTY_NOTICES.md"), "."),
        (os.path.join(project_root, "README.md"), "."),
        (os.path.join(project_root, "LICENSE.txt"), "."),
        (os.path.join(project_root, "licenses"), "licenses"),
        (python_license, "licenses/python"),
        (pyinstaller_license, "licenses/pyinstaller"),
    ],
    hiddenimports=collect_submodules("FATtools"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(project_root, "packaging", "runtime_dll_path.py")],
    excludes=["tkinter", "unittest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PS2OPLRipper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
    manifest=os.path.join(project_root, "packaging", "PS2Ripper.manifest"),
    version=os.path.join(project_root, "packaging", "version_info.txt"),
    uac_admin=True,
)
