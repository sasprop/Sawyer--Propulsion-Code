# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build for Propellant Analyzer.

Run from the repository root (build.bat does this for you):

    pyinstaller --noconfirm --clean packaging/PropellantAnalyzer.spec

Output: dist/PropellantAnalyzer/PropellantAnalyzer.exe  (one-folder build).
Set ONEFILE=1 in the environment for a single self-extracting .exe instead
(slower start-up, but just one file to hand around).
"""

import glob
import os
import re
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(ROOT, "src")
PKG = os.path.join(SRC, "propellant_analyzer")
sys.path.insert(0, SRC)

APP_NAME = "PropellantAnalyzer"
ONEFILE = os.environ.get("ONEFILE", "0") == "1"

with open(os.path.join(PKG, "__init__.py"), encoding="utf-8") as fh:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read()).group(1)

# --- Windows file-version resource (shows in Explorer > Properties > Details) ---
version_file = None
if sys.platform == "win32":
    nums = [int(x) for x in re.findall(r"\d+", VERSION)[:3]] + [0, 0, 0, 0]
    v4 = tuple(nums[:4])
    version_file = os.path.join(SPECPATH, "version_info.txt")
    with open(version_file, "w", encoding="utf-8") as fh:
        fh.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v4}, prodvers={v4}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('ProductName', 'Propellant Analyzer'),
      StringStruct('FileDescription', 'Propellant Analyzer (RocketCEA)'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('ProductVersion', '{VERSION}'),
      StringStruct('OriginalFilename', '{APP_NAME}.exe'),
      StringStruct('InternalName', '{APP_NAME}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")

# --- Data -----------------------------------------------------------------------
datas = [
    (os.path.join(PKG, "data", "*.json"), "propellant_analyzer/data"),
    (os.path.join(PKG, "data", "*.txt"), "propellant_analyzer/data"),
]
# RocketCEA copies thermo.lib, trans.lib, f.inp, f.out and temp.dat from its
# package folder into ~/RocketCEA on first use, and reads its own _version.py
# as a text file at import time. The *.inp/*.out library sources are not needed.
datas += collect_data_files("rocketcea", excludes=[
    "examples/**", "tests/**", "**/*.f",
    "thermo.inp", "trans.inp", "thermo.out", "trans.out",
])
import rocketcea  # noqa: E402

RCEA_DIR = os.path.dirname(rocketcea.__file__)
datas.append((os.path.join(RCEA_DIR, "_version.py"), "rocketcea"))

# Compiled CEA Fortran module + its gfortran runtime DLLs (Windows wheels keep
# them in rocketcea/.libs or a sibling rocketcea.libs folder).
binaries = collect_dynamic_libs("rocketcea")
for libdir, dest in [
    (os.path.join(RCEA_DIR, ".libs"), "rocketcea/.libs"),
    (os.path.join(os.path.dirname(RCEA_DIR), "rocketcea.libs"), "rocketcea.libs"),
]:
    for dll in glob.glob(os.path.join(libdir, "*")):
        binaries.append((dll, dest))

icon = os.path.join(SPECPATH, "icon.ico")
icon = icon if os.path.isfile(icon) else None

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=["rocketcea.py_cea"],
    excludes=[
        # Pulled in by rocketcea's optional extras, never used by this app
        "scipy", "tkinter", "PyQt5", "PySide2", "PySide6", "IPython", "pandas",
        "rocketcea.biprop_utils", "rocketcea.xlChart", "rocketcea.xlChFormula",
        "rocketcea.examples", "rocketcea.tests",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe_kwargs = dict(
    name=APP_NAME,
    console=False,
    icon=icon,
    version=version_file,
    upx=False,
)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **exe_kwargs)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_kwargs)
    coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)
