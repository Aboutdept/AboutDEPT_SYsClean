# -*- coding: utf-8 -*-
"""
SysClean - 路径解析（打包感知）

为什么需要这个模块：
    PyInstaller onefile 运行时，sys.modules["__main__"].__file__ 指向
    每次启动都会变的临时解压目录（_MEIxxxxxx）。若直接用它当基准目录：
      - settings.json 写进临时目录 → 设置每次启动全丢
      - 审计日志写进临时目录 → 清理记录全丢
      - 用户的 Custom/ 规则、exe 旁的 Winapp2.ini 永远读不到
    必须区分「只读数据」与「可写数据」两个基准。

对外接口：
    is_frozen()     是否以打包 exe 运行
    project_dir()   源码模式的项目根（多候选 + 特征目录校验）
    exe_dir()       exe/入口脚本所在目录（可写基准）
    bundle_dir()    打包内嵌数据目录（frozen 时为 _MEIPASS，只读）
    data_dir()      规则数据基准：exe 旁的覆盖优先，否则内嵌
    writable_dir()  设置/日志基准：exe 目录，不可写则退回 %APPDATA%/SysClean
"""

import os
import sys

# 只有真正的项目目录才会有的强标记（Custom 会被自动创建，不能作为强标记）
_STRONG_MARKERS = ("Databases", "Winapp2.ini", "main.py", "gui.py")


def is_frozen() -> bool:
    """是否运行在打包后的 exe 中（PyInstaller / Nuitka / cx_Freeze 均设置 frozen）。"""
    return bool(getattr(sys, "frozen", False))


def _exe_dir() -> str:
    try:
        return os.path.dirname(os.path.abspath(sys.executable))
    except Exception:
        return os.getcwd()


def project_dir() -> str:
    """源码模式下的项目根目录。

    多候选 + 特征目录校验：从子目录脚本启动（python tests/xxx.py）时，
    __main__ 的目录是 tests/，必须靠标记回退到真正的项目根。
    """
    cands = []
    try:
        f = sys.modules["__main__"].__file__
        if f:
            cands.append(os.path.dirname(os.path.abspath(f)))
    except Exception:
        pass
    cands.append(os.path.dirname(os.path.abspath(__file__)))
    cands.append(os.getcwd())

    for c in cands:
        try:
            for m in _STRONG_MARKERS:
                if os.path.exists(os.path.join(c, m)):
                    return c
        except OSError:
            continue
    for c in cands:
        try:
            if os.path.exists(os.path.join(c, "Custom")):
                return c
        except OSError:
            continue
    return cands[0]


def exe_dir() -> str:
    """exe（或入口脚本）所在目录 —— 唯一保证可写的基准。"""
    return _exe_dir() if is_frozen() else project_dir()


def bundle_dir() -> str:
    """打包内嵌数据目录（只读）。源码模式下等同项目根。"""
    if is_frozen():
        return getattr(sys, "_MEIPASS", None) or _exe_dir()
    return project_dir()


def data_dir() -> str:
    """规则数据基准：Databases/、Winapp2.ini、Custom/。

    优先级（frozen）：exe 旁的覆盖 > 内嵌数据。
    这样用户可以把自己改过的 Databases/ 或新版 Winapp2.ini 放在 exe 旁边生效。
    """
    if not is_frozen():
        return project_dir()
    e = _exe_dir()
    try:
        for m in ("Databases", "Winapp2.ini"):
            if os.path.exists(os.path.join(e, m)):
                return e
    except OSError:
        pass
    return bundle_dir()


def writable_dir() -> str:
    """设置与日志的写入基准。exe 目录不可写时退回 %APPDATA%/SysClean。"""
    base = exe_dir()
    try:
        if os.access(base, os.W_OK):
            return base
    except OSError:
        pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        folder = os.path.join(appdata, "SysClean")
        try:
            os.makedirs(folder, exist_ok=True)
            return folder
        except OSError:
            pass
    return base
