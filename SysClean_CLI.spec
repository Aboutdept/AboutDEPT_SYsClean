# -*- mode: python ; coding: utf-8 -*-
"""
SysClean CLI - PyInstaller 单文件打包配置（带控制台）

用途：命令行 / Windows 任务计划程序的静默定时清理。
      python main.py --auto --yes 的等价可执行文件。

构建：
  pyinstaller SysClean_CLI.spec --noconfirm --clean
输出：
  dist\\SysClean_CLI.exe
"""

import os

datas = []
for f in ("Winapp2.ini", "icon.ico"):
    if os.path.isfile(f):
        datas.append((f, "."))
for d in ("Databases", "Custom"):
    if os.path.isdir(d):
        datas.append((d, d))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'scipy', 'PIL', 'PyQt5', 'PySide6', 'matplotlib', 'pandas'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SysClean_CLI',
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
    icon='icon.ico',
    version=None,
)
