# -*- mode: python ; coding: utf-8 -*-
"""
SysClean - PyInstaller 单文件（onefile）打包配置

说明：
  - console=False  : GUI 模式，双击无黑窗（CLI 参数在此模式下不可用，
                     需要命令行/计划任务请用 SysClean_CLI.spec）。
  - datas          : Winapp2.ini / Databases/ / Custom/ / icon.ico 必须内嵌，
                     否则打包后规则库全部失效。
  - upx            : 若本机无 UPX 会自动跳过（只影响体积，不影响功能）。

构建：
  pyinstaller SysClean.spec --noconfirm --clean
输出：
  dist\\SysClean.exe
"""

import os

# ---- 需要内嵌的数据文件（缺失则自动跳过，避免构建中断）----
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
    excludes=[
        # 减小体积：本项目不使用
        'numpy', 'scipy', 'PIL', 'PyQt5', 'PySide6', 'matplotlib', 'pandas',
    ],
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
    name='SysClean',
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
    icon='icon.ico',
    version=None,
)
