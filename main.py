# -*- coding: utf-8 -*-
"""
SysClean - 系统垃圾文件扫描与清理工具
启动入口

- 不带参数：启动 GUI。
- 带参数（如 --scan / --clean / --auto）：进入 CLI 模式（迭代 3）。

致命异常兜底：打包为 exe / 用 pythonw 启动时没有控制台，未捕获异常会被
静默丢弃，表现为「程序没反应」。这里把 traceback 写入 logs/crash-*.log
并尽量弹出错误框。
"""

import os
import sys
import traceback
from datetime import datetime

# 确保可以正确导入模块
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    # 打包后 sys._MEIPASS 才是模块解压处；源码模式下等同 BASE_DIR
    _MEI = getattr(sys, "_MEIPASS", None)
    if _MEI and os.path.isdir(_MEI):
        sys.path.insert(0, _MEI)
except Exception:
    pass


def _logs_dir() -> str:
    """崩溃日志写可写目录（打包后为 exe 旁，不能写临时解压目录）。"""
    try:
        from app_paths import writable_dir
        return os.path.join(writable_dir(), "logs")
    except Exception:
        return os.path.join(BASE_DIR, "logs")


def _report_fatal(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    logdir = _logs_dir()
    try:
        os.makedirs(logdir, exist_ok=True)
        path = os.path.join(
            logdir, "crash-%s.log" % datetime.now().strftime("%Y%m%d-%H%M%S"))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        path = None
    try:
        import tkinter.messagebox as mb
        mb.showerror(
            "SysClean 启动失败",
            "程序发生未处理的异常，已终止。\n\n%s\n\n日志：%s" % (exc, path or "(写入失败)"),
        )
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _report_fatal


def _log_startup(mode: str):
    """记录启动环境到 logs/startup.log。

    打包成 exe 后没有控制台，排障全靠这个文件。它同时是路径层的
    活体证明：writable_dir 必须落在 exe 目录（而非 PyInstaller 的
    临时解压目录 _MEIxxxxxx），否则设置与日志每次启动都会丢。
    """
    try:
        d = _logs_dir()
        os.makedirs(d, exist_ok=True)
        import app_paths
        with open(os.path.join(d, "startup.log"), "a", encoding="utf-8") as f:
            f.write(
                "%s  mode=%s frozen=%s\n"
                "    exe        = %s\n"
                "    data_dir   = %s\n"
                "    bundle_dir = %s\n"
                "    writable   = %s\n"
                % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), mode,
                   app_paths.is_frozen(), sys.executable,
                   app_paths.data_dir(), app_paths.bundle_dir(),
                   app_paths.writable_dir())
            )
    except Exception:
        pass


def main():
    if len(sys.argv) > 1:
        # 有命令行参数 → 走 CLI 模式（不启动 GUI）
        from cli import run_cli
        _log_startup("cli")
        return run_cli(sys.argv[1:])

    from gui import SysCleanApp
    _log_startup("gui")
    app = SysCleanApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
