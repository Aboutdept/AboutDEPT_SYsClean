# -*- coding: utf-8 -*-
"""
SysClean - 设置持久化 (AppSettings)
保存用户选择、窗口尺寸、是否仅显示已安装软件等。
优先存于 exe/脚本同目录（便携模式），不可写时退回 %APPDATA%/SysClean。
"""

import os
import sys
import json

try:
    from app_paths import writable_dir, data_dir
except Exception:  # 极简兜底：app_paths 缺失时仍能工作
    def writable_dir():
        try:
            return os.path.dirname(os.path.abspath(sys.modules["__main__"].__file__))
        except Exception:
            return os.getcwd()

    def data_dir():
        return writable_dir()


def _project_base() -> str:
    """设置/日志的写入基准（打包后为 exe 所在目录，而非临时解压目录）。"""
    return writable_dir()


class AppSettings:
    """轻量设置存储，读写 settings.json。"""

    def __init__(self):
        self.path = self._resolve_path()
        # 默认值
        self.selected_ids: list = []
        self.window_size: str = "1150x740"
        self.hide_not_installed: bool = True
        # 迭代2：winapp2 数据库
        self.enable_winapp2: bool = True
        self.winapp2_path: str = self.default_winapp2_path()
        self.global_exclusions: list = []
        # 规则数据库（Databases/*.ini：CG/VP/AIGC + 系统补充项）
        self.enable_databases: bool = True

    @staticmethod
    def default_winapp2_path() -> str:
        """Winapp2.ini 是只读数据，基准用 data_dir()（打包后指向内嵌目录）。"""
        return os.path.join(data_dir(), "Winapp2.ini")

    @staticmethod
    def _resolve_path() -> str:
        base = writable_dir()
        candidate = os.path.join(base, "settings.json")
        # 同目录可写 → 便携模式
        try:
            if os.access(base, os.W_OK) or not os.path.exists(candidate):
                return candidate
        except OSError:
            pass
        # 否则退回 AppData
        appdata = os.environ.get("APPDATA")
        if appdata:
            folder = os.path.join(appdata, "SysClean")
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError:
                pass
            return os.path.join(folder, "settings.json")
        return candidate

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
                self.selected_ids = data.get("selected_ids", []) or []
                self.window_size = data.get("window_size", "1150x740") or "1150x740"
                self.hide_not_installed = bool(data.get("hide_not_installed", True))
                self.enable_winapp2 = bool(data.get("enable_winapp2", True))
                # 保存的路径失效（换机器 / 打包后路径变化）时回退到默认
                wp = data.get("winapp2_path")
                if wp and os.path.exists(wp):
                    self.winapp2_path = wp
                else:
                    self.winapp2_path = self.default_winapp2_path()
                self.global_exclusions = data.get("global_exclusions", []) or []
                self.enable_databases = bool(data.get("enable_databases", True))
        except (OSError, ValueError):
            pass
        return self

    def save(self):
        try:
            parent = os.path.dirname(self.path) or "."
            os.makedirs(parent, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({
                    "selected_ids": self.selected_ids,
                    "window_size": self.window_size,
                    "hide_not_installed": self.hide_not_installed,
                    "enable_winapp2": self.enable_winapp2,
                    "winapp2_path": self.winapp2_path,
                    "global_exclusions": self.global_exclusions,
                    "enable_databases": self.enable_databases,
                }, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return self
