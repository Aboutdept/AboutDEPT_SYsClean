# -*- coding: utf-8 -*-
"""
SysClean - 系统垃圾文件扫描与清理工具
扫描 Windows 系统常见垃圾文件位置，提供可视化报告和一键清理功能。
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import re
import sys
import glob
import configparser
import subprocess
import threading
import json
import shutil
import platform
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple
import ctypes
import ctypes.wintypes

try:
    import winreg
except ImportError:  # 非 Windows 环境（仅影响注册表检测）
    winreg = None

# 迭代2：winapp2 数据库解析器（顶层导入安全：winapp2_parser 仅在函数内延迟 import scanner）
from winapp2_parser import load_winapp2

# ============================================================
#  扫描引擎
# ============================================================

@dataclass
class ScanItem:
    """单个扫描项目的数据结构"""
    id: str
    label: str               # 显示名称
    path: str                # 扫描路径（支持通配符 *）
    category: str            # 分类
    risk_level: str          # 风险等级: safe / medium / caution
    description: str         # 详细说明
    files: int = 0
    folders: int = 0
    size_bytes: int = 0
    exists: bool = False
    sub_items: list = field(default_factory=list)  # 子项明细
    selected: bool = False
    cleaning_note: str = ""  # 清理备注
    readonly: bool = False   # 只读模式：仅扫描统计，不允许清理
    # --- 迭代1：安装检测 + 可扩展性 + 持久化 ---
    installed: bool = True   # 是否检测到对应软件已安装（未安装则隐藏/折叠）
    source: str = "builtin"  # builtin / custom
    custom: bool = False     # 是否来自 Custom/ 自定义规则
    detect: list = field(default_factory=list)     # 安装检测：文件/文件夹路径（支持通配符）
    detect_reg: list = field(default_factory=list) # 安装检测：注册表键路径
    patterns: list = field(default_factory=list)   # 仅统计/清理匹配这些通配符的文件（空=整个目录）
    recurse: bool = False    # patterns 是否递归子目录

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)

    @property
    def size_gb(self) -> float:
        return round(self.size_bytes / (1024 * 1024 * 1024), 2)

    @property
    def size_str(self) -> str:
        if self.size_bytes >= 1024 * 1024 * 1024:
            return f"{self.size_gb:.2f} GB"
        elif self.size_bytes >= 1024 * 1024:
            return f"{self.size_mb:.2f} MB"
        elif self.size_bytes >= 1024:
            return f"{self.size_bytes / 1024:.2f} KB"
        else:
            return f"{self.size_bytes} B"

    @property
    def risk_display(self) -> str:
        mapping = {"safe": "Safe", "medium": "Medium", "caution": "Caution"}
        return mapping.get(self.risk_level, "Unknown")

    @property
    def risk_icon(self) -> str:
        if self.readonly:
            return "🔒"
        mapping = {"safe": "🟢", "medium": "🟡", "caution": "🔴"}
        return mapping.get(self.risk_level, "⚪")


# ============================================================
#  路径展开器（统一 %VAR% 与通配符，内置/自定义/winapp2 共用）
# ============================================================

class PathExpander:
    """统一路径展开：把 %LocalAppData% 等环境变量与通配符解析为真实路径。"""

    _TOKENS = {
        "%LocalAppData%":      lambda: os.environ.get("LOCALAPPDATA", ""),
        "%LocalLow%":          lambda: os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "LocalLow"),
        "%AppData%":           lambda: os.environ.get("APPDATA", ""),
        "%ProgramData%":       lambda: os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
        "%ProgramFiles%":      lambda: os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        "%ProgramFiles(x86)%": lambda: os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        "%UserProfile%":        lambda: os.environ.get("USERPROFILE", ""),
        "%SystemRoot%":        lambda: os.environ.get("SYSTEMROOT", r"C:\Windows"),
        "%WinDir%":            lambda: os.environ.get("WINDIR", r"C:\Windows"),
        "%Temp%":              lambda: os.environ.get("TEMP", ""),
        "%Documents%":         lambda: os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
        "%Videos%":            lambda: os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "%Pictures%":          lambda: os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "%Desktop%":           lambda: os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        # --- 补充（Dism++ / 通用清理规则常用写法）---
        # SYSTEMDRIVE 形如 "C:"（不带反斜杠），规则里写作 %SystemDrive%\Users
        "%SystemDrive%":       lambda: os.environ.get("SYSTEMDRIVE", "C:"),
        "%System%":            lambda: os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32"),
        "%Public%":            lambda: os.environ.get("PUBLIC", r"C:\Users\Public"),
        "%AllUsersProfile%":   lambda: os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
        "%OneDrive%":          lambda: os.environ.get("ONEDRIVE", ""),
        "%OneDriveCommercial%": lambda: os.environ.get("ONEDRIVECOMMERCIAL", ""),
        "%ProgramFilesX86%":   lambda: os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        "%ProgramFilesX64%":   lambda: os.environ.get("PROGRAMW6432", r"C:\Program Files"),
    }

    @classmethod
    def expand(cls, path: str) -> str:
        if not path:
            return path
        for token, getter in cls._TOKENS.items():
            if token in path:
                try:
                    path = path.replace(token, getter())
                except Exception:
                    pass
        # 兜底：大小写/异体写法（winapp2 数据库偶见 %localappdata% 等）
        if "%" in path:
            def _sub(m):
                raw = m.group(0)
                getter = cls._TOKENS.get(raw)
                if getter is None:
                    for t, g in cls._TOKENS.items():
                        if t.lower() == raw.lower():
                            getter = g
                            break
                if getter is None:
                    return raw
                try:
                    return getter()
                except Exception:
                    return raw
            try:
                path = re.sub(r"%[A-Za-z0-9_()]+%", _sub, path)
            except re.error:
                pass
        return path

    @classmethod
    def expand_list(cls, paths) -> List[str]:
        return [cls.expand(p) for p in (paths or [])]

    @classmethod
    def resolve_matches(cls, pattern: str) -> List[str]:
        """展开含通配符的路径为真实路径列表（无匹配返回空列表）。"""
        expanded = cls.expand(pattern)
        if "*" not in expanded and "?" not in expanded:
            return [expanded]
        try:
            return glob.glob(expanded)
        except (OSError, re.error):
            return []

    @classmethod
    def match_files(cls, root: str, patterns, recurse: bool = False) -> List[str]:
        """返回 root 下匹配 patterns 的文件路径列表。"""
        results: List[str] = []
        patterns = patterns or ["*"]
        try:
            if recurse:
                for pat in patterns:
                    for m in glob.glob(os.path.join(root, "**", pat), recursive=True):
                        if os.path.isfile(m):
                            results.append(m)
            else:
                for pat in patterns:
                    for m in glob.glob(os.path.join(root, pat)):
                        if os.path.isfile(m):
                            results.append(m)
        except (OSError, re.error):
            pass
        return results


# ============================================================
#  安装检测服务（只显示已安装 App，消灭噪音）
# ============================================================

def _reg_key_exists(key_path: str) -> bool:
    """检测注册表键是否存在（64 位视图）。"""
    if winreg is None:
        return False
    try:
        root_name, sub = key_path.split("\\", 1)
    except ValueError:
        return False
    hkey = {
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
        "HKLM64": winreg.HKEY_LOCAL_MACHINE,
    }.get(root_name)
    if hkey is None:
        return False
    try:
        key = winreg.OpenKey(hkey, sub, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        key.Close()
        return True
    except OSError:
        return False


class DetectionService:
    """安装检测：仅当对应软件存在时才视为「已安装」。

    未在下表中的项默认视为已安装（系统/通用项），保持向后兼容。
    """

    _DETECTION = {
        # --- Unreal Engine / Epic ---
        "ue_ddc":          {"paths": ["%LocalAppData%\\UnrealEngine"], "regs": ["HKLM\\SOFTWARE\\EpicGames"]},
        "ue_shader_cache": {"paths": ["%LocalAppData%\\UnrealEngine"], "regs": ["HKLM\\SOFTWARE\\EpicGames"]},
        "ue_intermediate": {"paths": ["%LocalAppData%\\UnrealEngine"], "regs": ["HKLM\\SOFTWARE\\EpicGames"]},
        "ue_crash":        {"paths": ["%Documents%\\Unreal Engine"], "regs": ["HKLM\\SOFTWARE\\EpicGames"]},
        "ue_autosaved":    {"paths": ["%Documents%\\Unreal Engine"], "regs": ["HKLM\\SOFTWARE\\EpicGames"]},
        "epic_vault":        {"paths": ["C:\\Program Files (x86)\\Epic Games", "%LocalAppData%\\Epic Games Launcher"]},
        "epic_launcher_cache": {"paths": ["%LocalAppData%\\Epic Games Launcher"]},
        # --- VP / Broadcast ---
        "aximmetry_recorded": {"paths": ["%Documents%\\Aximmetry"]},
        "aximmetry_profiles": {"paths": ["%Documents%\\Aximmetry"]},
        "disguise_thumbnails": {"paths": ["C:\\ProgramData\\Disguise"]},
        "disguise_logs":       {"paths": ["C:\\ProgramData\\Disguise"]},
        "pixotope_storage":  {"paths": ["%LocalAppData%\\Pixotope"]},
        "zd_reality_cache":  {"paths": ["%LocalAppData%\\ZeroDensity"]},
        "hecoos_cache":      {"paths": ["%LocalAppData%\\Hecoos"]},
        "bmd_resolve_logs":  {"paths": ["%LocalAppData%\\Blackmagic Design", "%Documents%\\Blackmagic Design"]},
        # --- CG / Post ---
        "ae_media_cache":    {"paths": ["%AppData%\\Adobe"], "regs": ["HKLM\\SOFTWARE\\Adobe"]},
        "ae_disk_cache":     {"paths": ["%AppData%\\Adobe"], "regs": ["HKLM\\SOFTWARE\\Adobe"]},
        "ae_autosave":       {"paths": ["%Documents%\\Adobe"], "regs": ["HKLM\\SOFTWARE\\Adobe"]},
        "pr_preview":        {"paths": ["%Documents%\\Adobe"], "regs": ["HKLM\\SOFTWARE\\Adobe"]},
        "maya_temp":         {"paths": ["%Documents%\\maya"], "regs": ["HKLM\\SOFTWARE\\Autodesk"]},
        "houdini_cache":     {"paths": ["%Documents%\\houdini"]},
        "houdini_temp":      {"paths": ["%LocalAppData%\\Side Effects Software"]},
        "c4d_cache":         {"paths": ["%Documents%\\Maxon"]},
        "blender_config":    {"paths": ["%AppData%\\Blender Foundation"]},
        "davinci_cache":     {"paths": ["%Documents%\\Blackmagic Design", "%LocalAppData%\\Blackmagic Design"]},
        "nuke_cache":        {"paths": ["%Documents%\\Foundry"]},
        "redshift_cache":    {"paths": ["%LocalAppData%\\Redshift"]},
        "octane_cache":      {"paths": ["%LocalAppData%\\OctaneRender"]},
        "vray_cache":        {"paths": ["%Documents%\\V-Ray"]},
        "nvidia_nv_cache":   {"paths": ["%LocalAppData%\\NVIDIA Corporation"]},
        # --- Games / misc optional ---
        "steam_temp":        {"paths": ["C:\\Program Files (x86)\\Steam"]},
    }

    @staticmethod
    def is_installed(item: "ScanItem") -> bool:
        # 自定义规则优先用自己的 detect 线索
        paths = list(item.detect) if item.detect else []
        regs = list(item.detect_reg) if item.detect_reg else []
        if not paths and not regs:
            det = DetectionService._DETECTION.get(item.id)
            if not det:
                return True  # 未登记 = 视为已安装（系统/通用项）
            paths = det.get("paths", [])
            regs = det.get("regs", [])
        for p in paths:
            for ep in PathExpander.resolve_matches(p):
                if os.path.exists(ep):
                    return True
        for r in regs:
            if _reg_key_exists(r):
                return True
        return False


# ============================================================
#  自定义规则加载（winapp2 子集：DetectFile / FileKeyN）
# ============================================================

def _base_dir() -> str:
    """规则数据基准目录（Databases/、Winapp2.ini、Custom/）。

    打包后（PyInstaller onefile / Nuitka）由 app_paths.data_dir() 负责：
    exe 旁的覆盖优先，否则用内嵌数据目录（_MEIPASS）。
    源码模式保留多候选 + 特征目录校验，避免从子目录脚本启动时基准跑偏
    （例如 python tests/xxx.py 会把基准判成 tests/）。
    """
    try:
        from app_paths import data_dir
        return data_dir()
    except Exception:
        pass

    cands = []
    try:
        f = sys.modules["__main__"].__file__
        if f:
            cands.append(os.path.dirname(os.path.abspath(f)))
    except Exception:
        pass
    cands.append(os.path.dirname(os.path.abspath(__file__)))
    cands.append(os.getcwd())

    # 强标记：只有真正的项目目录才会有（Custom 会被自动创建，不能作为强标记）
    strong = ("Databases", "Winapp2.ini", "main.py", "gui.py")
    for c in cands:
        for m in strong:
            if os.path.exists(os.path.join(c, m)):
                return c
    for c in cands:
        if os.path.exists(os.path.join(c, "Custom")):
            return c
    return cands[0]


def load_custom_rules(custom_dir: str = "Custom", source: str = "custom",
                      default_category: str = "Custom Rules",
                      create_dir: bool = True) -> List["ScanItem"]:
    """读取 *.ini 规则（winapp2 子集 + SysClean 扩展）。忽略 .disabled 后缀。

    扩展键：
      Category=<分类名>          ; 默认 default_category
      Risk=safe|medium|caution   ; 默认 safe（存在 Warning 键时强制 caution）

    语法示例：
        [My Tool Cache]
        DetectFile=%LocalAppData%\\MyTool
        FileKey1=%LocalAppData%\\MyTool\\Cache|*.tmp;*.cache|RECURSE
    """
    items: List["ScanItem"] = []
    base = _base_dir()
    folder = custom_dir if os.path.isabs(custom_dir) else os.path.join(base, custom_dir)
    if not os.path.isdir(folder):
        if not create_dir:
            return items
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            return items
    try:
        ini_files = [f for f in os.listdir(folder)
                     if f.lower().endswith(".ini") and not f.lower().endswith(".disabled")]
    except OSError:
        return items

    for fname in sorted(ini_files):
        fpath = os.path.join(folder, fname)
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str  # 保留大小写（FileKey1 等键名）
        try:
            parser.read(fpath, encoding="utf-8")
        except (OSError, configparser.Error):
            continue
        for section in parser.sections():
            data = dict(parser.items(section))
            detect = []
            detect_reg = []
            if data.get("DetectFile"):
                detect.append(PathExpander.expand(data["DetectFile"]))
            if data.get("Detect"):
                detect_reg.append(data["Detect"])
            if data.get("DetectReg"):
                detect_reg.append(data["DetectReg"])
            warning = "Warning" in data
            # SysClean 扩展：Category / Risk
            category = (data.get("Category") or "").strip() or default_category
            risk = (data.get("Risk") or "").strip().lower()
            if risk not in ("safe", "medium", "caution"):
                risk = "safe"
            if warning:
                risk = "caution"
            fk_entries = sorted(
                [k for k in data if k.startswith("FileKey")],
                key=lambda k: int("".join(filter(str.isdigit, k)) or 0)
            )
            idx = 0
            for key in fk_entries:
                parts = [p.strip() for p in data[key].split("|")]
                raw_path = PathExpander.expand(parts[0]) if parts else ""
                patterns: List[str] = []
                recurse = False
                removeself = False
                if len(parts) > 1 and parts[1]:
                    patterns = [p.strip() for p in parts[1].split(";") if p.strip()]
                if len(parts) > 2:
                    flags = " ".join(parts[2:]).upper()
                    recurse = "RECURSE" in flags
                    removeself = "REMOVESELF" in flags
                # REMOVESELF：清掉整个目录（与 winapp2 语义一致）
                if removeself:
                    patterns = []
                    recurse = True
                if not raw_path:
                    continue
                sid = re.sub(r"\W+", "_", f"{source}_{os.path.splitext(fname)[0]}_{section}_{idx}")
                item = ScanItem(
                    id=sid,
                    label=section + (f" (#{idx + 1})" if len(fk_entries) > 1 else ""),
                    path=raw_path,
                    category=category,
                    risk_level=risk,
                    description=data.get("Default", "") or f"{section}（来自 {fname}）",
                    cleaning_note=("REMOVESELF：将删除整个目录。" if removeself
                                   else "数据库规则。请确认路径安全后再清理。"),
                    source=source,
                    custom=(source == "custom"),
                    detect=detect,
                    detect_reg=detect_reg,
                    patterns=patterns,
                    recurse=recurse,
                )
                items.append(item)
                idx += 1
    return items


def load_database_rules(db_dir: str = "Databases") -> List["ScanItem"]:
    """加载 Databases/*.ini 规则数据库（CG/VP/AIGC + 系统补充项）。

    与 Custom/ 的区别：source="db"，缺目录时静默返回（不创建）。
    """
    return load_custom_rules(custom_dir=db_dir, source="db",
                             default_category="Database Rules", create_dir=False)


class ScanEngine:
    """扫描引擎 - 定义扫描目标并执行扫描"""

    def __init__(self):
        self.results: List[ScanItem] = []
        self.exclude_rules: List = []   # [(type, value), ...]，scan_all 会填充
        self._progress_callback = None
        self._log_callback = None

    def set_callbacks(self, progress_cb=None, log_cb=None):
        self._progress_callback = progress_cb
        self._log_callback = log_cb

    def _log(self, msg: str):
        if self._log_callback:
            self._log_callback(msg)

    def _progress(self, current: int, total: int):
        if self._progress_callback:
            self._progress_callback(current, total)

    @staticmethod
    def _resolve_paths(pattern: str) -> List[str]:
        """解析含通配符的路径，返回匹配的真实路径列表"""
        if "*" not in pattern and "?" not in pattern:
            return [pattern]
        try:
            # glob.glob 返回已存在路径
            matched = glob.glob(pattern)
            return matched if matched else []
        except (OSError, re.error):
            return []

    def get_scan_targets(self, custom_items: List["ScanItem"] = None,
                         winapp2_items: List["ScanItem"] = None,
                         db_items: List["ScanItem"] = None) -> List[ScanItem]:
        """返回所有预定义的扫描目标，涵盖 Windows 10/11。
        可合并 winapp2 数据库条目（winapp2_items）、规则数据库（Databases/*.ini,
        db_items）与 Custom/ 自定义规则（custom_items）。
        合并顺序：builtin → winapp2 → db → custom（custom 优先级最高）。"""
        # BUGFIX: 原先用 "C:\Users\<USERNAME>" 硬编码拼接，遇到用户目录被改名
        # （账户名与目录名不一致）、域账号、Profile 位于其它盘时全部失效。
        # 统一改用 USERPROFILE，拿不到时才回退旧拼接。
        up = os.environ.get("USERPROFILE") or ""
        if not up or not os.path.isdir(up):
            user = os.environ.get("USERNAME", "")
            up = f"C:\\Users\\{user}" if user else ""
        local = os.path.join(up, "AppData", "Local")
        roaming = os.path.join(up, "AppData", "Roaming")

        targets = [
            # ================================================================
            #  一、临时文件 (Temp Files)
            # ================================================================
            ScanItem(
                id="win_temp", label="Windows 系统临时文件",
                path=r"C:\Windows\Temp", category="Temp Files",
                risk_level="medium",
                description="Windows 系统及安装程序运行时产生的临时文件。安装/更新软件时可能残留大量文件。部分文件可能被占用，需要管理员权限才能删除。",
                cleaning_note="清理前关闭所有正在运行的程序。建议以管理员身份运行。"
            ),
            ScanItem(
                id="user_temp", label="用户临时文件",
                path=os.path.join(local, "Temp"), category="Temp Files",
                risk_level="safe",
                description="当前用户各应用程序运行时产生的临时文件和缓存。包含安装包解压、浏览器下载临时、Office 编辑临时等。",
                cleaning_note="安全清理。对日常使用无影响。"
            ),

            # ================================================================
            #  二、Windows 更新 (Windows Update)
            # ================================================================
            ScanItem(
                id="wu_download", label="Windows 更新下载缓存",
                path=r"C:\Windows\SoftwareDistribution\Download",
                category="Windows Update", risk_level="safe",
                description="已下载的 Windows 更新安装包。已安装的更新会保留这些文件，但下次检查更新时会重新下载。",
                cleaning_note="安全。先停止 Windows Update 服务再清理效果最佳。"
            ),
            ScanItem(
                id="wu_datastore", label="Windows 更新数据库",
                path=r"C:\Windows\SoftwareDistribution\DataStore",
                category="Windows Update", risk_level="medium",
                description="Windows 更新服务的元数据和日志数据库。清理后可能需要重新检测可用更新。",
                cleaning_note="清理后首次检查更新会较慢。"
            ),
            ScanItem(
                id="delivery_opt", label="传递优化缓存 (P2P)",
                path=r"C:\Windows\SoftwareDistribution\DeliveryOptimization",
                category="Windows Update", risk_level="safe",
                description="Windows 传递优化（P2P 分发）的缓存文件。局域网内多台电脑共享更新时使用。",
                cleaning_note="安全清理。"
            ),

            # ================================================================
            #  三、系统日志 (System Logs)
            # ================================================================
            ScanItem(
                id="win_logs", label="Windows 系统日志",
                path=r"C:\Windows\Logs", category="System Logs",
                risk_level="safe",
                description="Windows 各系统组件（网络、安装、安全等）的日志文件。老旧日志对排障已无用处。",
                cleaning_note="安全。旧日志不再需要。"
            ),
            ScanItem(
                id="panther", label="系统安装/升级日志 (Panther)",
                path=r"C:\Windows\Panther", category="System Logs",
                risk_level="safe",
                description="Windows 安装、升级和重大更新的详细日志。系统运行稳定后可删除。",
                cleaning_note="系统运行稳定时安全删除。"
            ),
            ScanItem(
                id="cbs_logs", label="CBS 组件服务日志",
                path=r"C:\Windows\Logs\CBS", category="System Logs",
                risk_level="safe",
                description="基于组件的服务（CBS）日志，记录系统更新、组件安装/卸载等操作。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="dism_logs", label="DISM 部署映像日志",
                path=r"C:\Windows\Logs\DISM", category="System Logs",
                risk_level="safe",
                description="DISM（部署映像服务和管理）工具的日志。使用 Dism 命令清理系统后会留下这些日志。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="setup_logs", label="Windows 安装程序日志",
                path=r"C:\Windows\Logs\Setup", category="System Logs",
                risk_level="safe",
                description="Windows 安装程序执行的日志，包括功能安装、.NET Framework 安装等操作记录。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="etl_logs", label="WMI/ETL 事件追踪日志",
                path=r"C:\Windows\System32\LogFiles\WMI",
                category="System Logs", risk_level="safe",
                description="Windows 事件追踪（ETL）日志文件，用于系统性能分析和诊断。可安全删除。",
                cleaning_note="安全清理。系统需要时会重新生成。"
            ),

            # ================================================================
            #  四、系统缓存 (System Cache)
            # ================================================================
            ScanItem(
                id="thumb_cache", label="缩略图缓存",
                path=os.path.join(local, "Microsoft", "Windows", "Explorer"),
                category="System Cache", risk_level="safe",
                description="Windows 资源管理器的缩略图缓存数据库（thumbcache_*.db）。删除后再次浏览文件夹时会自动重建。",
                cleaning_note="安全。打开文件夹时缩略图会自动重新生成。"
            ),
            ScanItem(
                id="prefetch", label="预读取缓存 (Prefetch)",
                path=r"C:\Windows\Prefetch", category="System Cache",
                risk_level="safe",
                description="Windows 预读取缓存，记录常用程序的启动文件以加速启动。删除后系统会自动重建，但短期内程序启动可能略慢。",
                cleaning_note="安全。可能暂时降低应用启动速度。"
            ),
            ScanItem(
                id="icon_cache", label="图标缓存数据库",
                path=os.path.join(local, "IconCache.db"),
                category="System Cache", risk_level="safe",
                description="Windows Shell 的图标缓存文件。删除后图标会重新加载，可能需要重启资源管理器。",
                cleaning_note="安全。可能需要重启 Explorer。"
            ),
            ScanItem(
                id="font_cache", label="字体缓存服务数据",
                path=r"C:\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache",
                category="System Cache", risk_level="safe",
                description="Windows 字体缓存服务的缓存数据。应用程序加载字体时使用，删除后自动重建。",
                cleaning_note="安全。自动重建。"
            ),
            ScanItem(
                id="search_index", label="Windows 搜索索引",
                path=r"C:\ProgramData\Microsoft\Search\Data\Applications\Windows",
                category="System Cache", risk_level="medium",
                description="Windows 搜索服务的索引数据库。删除后搜索功能会重建索引，重建期间搜索较慢。",
                cleaning_note="搜索索引重建期间搜索会变慢。"
            ),
            ScanItem(
                id="recycle_bin", label="回收站",
                path=r"C:\$Recycle.Bin", category="System Cache",
                risk_level="safe",
                description="所有驱动器的回收站。存放用户删除的文件，定期清理可释放大量空间。",
                cleaning_note="安全。清空前请确认没有误删的重要文件。"
            ),

            # ================================================================
            #  五、浏览器缓存 (Browser Cache)
            # ================================================================
            ScanItem(
                id="chrome_cache", label="Chrome 浏览器缓存",
                path=os.path.join(local, "Google", "Chrome", "User Data", "Default", "Cache"),
                category="Browser Cache", risk_level="safe",
                description="Google Chrome 的网页资源缓存（图片、CSS、JS 等）。清理后网页首次加载略慢。",
                cleaning_note="安全。清理前请关闭 Chrome。"
            ),
            ScanItem(
                id="chrome_code_cache", label="Chrome JS 代码缓存",
                path=os.path.join(local, "Google", "Chrome", "User Data", "Default", "Code Cache"),
                category="Browser Cache", risk_level="safe",
                description="Chrome 的 JavaScript 编译缓存，加速网页脚本执行。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="edge_cache", label="Edge 浏览器缓存",
                path=os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Cache"),
                category="Browser Cache", risk_level="safe",
                description="Microsoft Edge 的网页资源缓存。",
                cleaning_note="安全。清理前请关闭 Edge。"
            ),
            ScanItem(
                id="edge_code_cache", label="Edge JS 代码缓存",
                path=os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Code Cache"),
                category="Browser Cache", risk_level="safe",
                description="Edge 的 JavaScript 编译缓存。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="edge_inet_cache", label="IE/旧 Edge 网络缓存",
                path=os.path.join(local, "Microsoft", "Windows", "INetCache"),
                category="Browser Cache", risk_level="safe",
                description="Internet Explorer 和旧版 Edge 的网页缓存。部分旧系统组件仍会使用此路径。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="firefox_cache", label="Firefox 浏览器缓存",
                path=os.path.join(roaming, "Mozilla", "Firefox", "Profiles"),
                category="Browser Cache", risk_level="safe",
                description="Mozilla Firefox 的缓存目录。包含所有 Firefox 配置文件的网页缓存。",
                cleaning_note="安全。清理前请关闭 Firefox。"
            ),
            ScanItem(
                id="opera_cache", label="Opera 浏览器缓存",
                path=os.path.join(local, "Opera Software", "Opera Stable", "Cache"),
                category="Browser Cache", risk_level="safe",
                description="Opera 浏览器的网页资源缓存。",
                cleaning_note="安全。清理前请关闭 Opera。"
            ),
            ScanItem(
                id="brave_cache", label="Brave 浏览器缓存",
                path=os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Cache"),
                category="Browser Cache", risk_level="safe",
                description="Brave 浏览器的网页资源缓存。",
                cleaning_note="安全。清理前请关闭 Brave。"
            ),

            # ================================================================
            #  六、开发工具缓存 (Dev Tools)
            # ================================================================
            ScanItem(
                id="npm_cache", label="npm 包缓存",
                path=os.path.join(local, "npm-cache"),
                category="Dev Tools", risk_level="safe",
                description="Node.js npm 包管理器下载的包缓存。包含所有 npm install 过的依赖包。",
                cleaning_note="安全。下次 npm install 会重新下载。"
            ),
            ScanItem(
                id="pip_cache", label="pip 包缓存",
                path=os.path.join(local, "pip", "cache"),
                category="Dev Tools", risk_level="safe",
                description="Python pip 包管理器下载的包缓存。",
                cleaning_note="安全。下次 pip install 会重新下载。"
            ),
            ScanItem(
                id="nuget_cache", label="NuGet 包缓存",
                path=os.path.join(up, ".nuget", "packages"),
                category="Dev Tools", risk_level="medium",
                description=".NET/NuGet 包管理器的本地包缓存。包含所有还原过的 NuGet 依赖包。",
                cleaning_note="不做 C#/.NET 开发可安全清理。"
            ),
            ScanItem(
                id="maven_repo", label="Maven 本地仓库",
                path=os.path.join(up, ".m2", "repository"),
                category="Dev Tools", risk_level="medium",
                description="Java Maven 构建工具的本地依赖仓库。包含所有下载过的 JAR 包。",
                cleaning_note="不做 Java 开发可安全清理。清理后首次构建需重新下载依赖。"
            ),
            ScanItem(
                id="gradle_cache", label="Gradle 缓存",
                path=os.path.join(up, ".gradle", "caches"),
                category="Dev Tools", risk_level="medium",
                description="Gradle 构建工具的依赖缓存和构建缓存。",
                cleaning_note="不做 Java/Kotlin 开发可安全清理。"
            ),
            ScanItem(
                id="conda_cache", label="Conda 包缓存",
                path=os.path.join(up, ".conda", "pkgs"),
                category="Dev Tools", risk_level="medium",
                description="Anaconda/Miniconda 的下载包缓存（tar.bz2 压缩包）。已安装的环境不受影响。",
                cleaning_note="安全清理。已安装的 Conda 环境不受影响。"
            ),
            ScanItem(
                id="yarn_cache", label="Yarn 包缓存",
                path=os.path.join(local, "Yarn", "Cache"),
                category="Dev Tools", risk_level="safe",
                description="Yarn 包管理器的全局下载缓存。",
                cleaning_note="安全。下次安装会重新下载。"
            ),
            ScanItem(
                id="pnpm_cache", label="pnpm 包缓存",
                path=os.path.join(local, "pnpm-store"),
                category="Dev Tools", risk_level="safe",
                description="pnpm 包管理器的全局内容寻址存储。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="go_modules", label="Go Modules 缓存",
                path=os.path.join(up, "go", "pkg", "mod"),
                category="Dev Tools", risk_level="medium",
                description="Go 语言的模块依赖缓存。包含所有 go get 下载的依赖。",
                cleaning_note="不做 Go 开发可安全清理。"
            ),
            ScanItem(
                id="cargo_cache", label="Cargo/Rust 缓存",
                path=os.path.join(up, ".cargo", "registry"),
                category="Dev Tools", risk_level="medium",
                description="Rust Cargo 的 crate 注册表缓存和索引。",
                cleaning_note="不做 Rust 开发可安全清理。"
            ),
            ScanItem(
                id="vscode_cache", label="VS Code 缓存",
                path=os.path.join(roaming, "Code", "Cache"),
                category="Dev Tools", risk_level="safe",
                description="Visual Studio Code 的通用缓存文件。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="vscode_ext_cache", label="VS Code 扩展 VSIX 缓存",
                path=os.path.join(roaming, "Code", "CachedExtensionVSIXs"),
                category="Dev Tools", risk_level="safe",
                description="VS Code 已下载的扩展安装包（已安装完毕，这些 .vsix 文件不再需要）。",
                cleaning_note="安全。已安装的扩展不受影响。"
            ),
            ScanItem(
                id="vscode_data", label="VS Code 缓存数据",
                path=os.path.join(roaming, "Code", "CachedData"),
                category="Dev Tools", risk_level="safe",
                description="VS Code 的缓存数据（语法高亮、自动补全等）。",
                cleaning_note="安全。自动重建。"
            ),
            ScanItem(
                id="docker_data", label="Docker Desktop 数据",
                path=os.path.join(local, "Docker"),
                category="Dev Tools", risk_level="medium",
                description="Docker Desktop 的缓存和临时数据。注意：不要删除正在运行的容器数据。",
                cleaning_note="建议通过 Docker CLI 清理：docker system prune。"
            ),

            # ================================================================
            #  七、崩溃报告 (Crash Reports)
            # ================================================================
            ScanItem(
                id="crash_dumps", label="应用程序崩溃转储",
                path=os.path.join(local, "CrashDumps"),
                category="Crash Reports", risk_level="safe",
                description="应用程序崩溃时生成的调试转储文件（.dmp）。仅对开发者排查问题有用，普通用户可安全删除。",
                cleaning_note="安全。普通用户不需要这些文件。"
            ),
            ScanItem(
                id="wer_user", label="Windows 错误报告 (用户)",
                path=os.path.join(local, "Microsoft", "Windows", "WER"),
                category="Crash Reports", risk_level="safe",
                description="当前用户的 Windows 错误报告存档。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="wer_system", label="Windows 错误报告 (系统)",
                path=r"C:\ProgramData\Microsoft\Windows\WER",
                category="Crash Reports", risk_level="safe",
                description="系统级别的 Windows 错误报告存档。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="minidump", label="蓝屏 (BSOD) 小型转储",
                path=r"C:\Windows\Minidump", category="Crash Reports",
                risk_level="safe",
                description="系统蓝屏（BSOD）时生成的小型崩溃转储文件。仅用于系统排障分析。",
                cleaning_note="近期无蓝屏问题可安全删除。"
            ),
            ScanItem(
                id="memory_dmp", label="系统内存转储",
                path=r"C:\Windows\MEMORY.DMP", category="Crash Reports",
                risk_level="safe",
                description="完整系统内存转储文件（仅蓝屏时生成）。文件体积可达数 GB，用于深度调试。",
                cleaning_note="安全删除。"
            ),

            # ================================================================
            #  八、应用缓存 (App Cache)
            # ================================================================
            ScanItem(
                id="tencent_roaming", label="腾讯软件缓存 (微信/QQ/腾讯会议)",
                path=os.path.join(roaming, "Tencent"),
                category="App Cache", risk_level="caution",
                description="腾讯系应用（微信、QQ、腾讯会议、企业微信等）的缓存数据。包含聊天中的图片、文件、视频缓存。",
                cleaning_note="⚠ 警告：清理后聊天中缓存的图片和文件将丢失，请确认已保存重要内容。"
            ),
            ScanItem(
                id="tencent_files", label="腾讯用户数据 (QQ/微信)",
                path=os.path.join(up, "Documents", "Tencent Files"),
                category="App Cache", risk_level="caution",
                description="QQ 和微信的用户数据目录。包含聊天记录、文件传输历史等。",
                cleaning_note="⚠ 严重警告：包含重要聊天数据。不建议清理。"
            ),
            ScanItem(
                id="adobe_local", label="Adobe 本地缓存",
                path=os.path.join(local, "Adobe"),
                category="App Cache", risk_level="safe",
                description="Adobe 系列软件（Photoshop、Premiere、After Effects 等）的本地缓存和临时文件。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="adobe_roaming", label="Adobe 配置与缓存",
                path=os.path.join(roaming, "Adobe"),
                category="App Cache", risk_level="medium",
                description="Adobe 软件的配置文件和缓存（与 Local 互补）。清理可能重置部分软件偏好设置。",
                cleaning_note="可能重置部分软件偏好设置。"
            ),
            ScanItem(
                id="office_cache", label="Microsoft Office 文件缓存",
                path=os.path.join(local, "Microsoft", "Office", "16.0", "OfficeFileCache"),
                category="App Cache", risk_level="safe",
                description="Office 应用的文件操作缓存，用于加速文件打开和保存。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="teams_cache", label="Microsoft Teams 缓存",
                path=os.path.join(roaming, "Microsoft", "Teams"),
                category="App Cache", risk_level="safe",
                description="Microsoft Teams（经典版）的缓存数据，包含会议、聊天、文件缓存。",
                cleaning_note="安全。清理前请退出 Teams。"
            ),
            ScanItem(
                id="discord_cache", label="Discord 缓存",
                path=os.path.join(roaming, "discord", "Cache"),
                category="App Cache", risk_level="safe",
                description="Discord 的媒体缓存（图片、视频等）。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="zoom_cache", label="Zoom 会议缓存",
                path=os.path.join(roaming, "Zoom"),
                category="App Cache", risk_level="safe",
                description="Zoom 的会议录制临时文件和缓存数据。",
                cleaning_note="安全。注意不要删除已保存的会议录制。"
            ),
            ScanItem(
                id="slack_cache", label="Slack 缓存",
                path=os.path.join(roaming, "Slack", "Cache"),
                category="App Cache", risk_level="safe",
                description="Slack 的缓存数据（图片、文件预览等）。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="spotify_cache", label="Spotify 离线缓存",
                path=os.path.join(local, "Spotify", "Storage"),
                category="App Cache", risk_level="safe",
                description="Spotify 的离线下载歌曲缓存。清理后已下载的离线歌曲需要重新下载。",
                cleaning_note="安全。离线歌曲需重新下载。"
            ),
            ScanItem(
                id="steam_temp", label="Steam 下载临时文件",
                path=r"C:\Program Files (x86)\Steam\steamapps\temp",
                category="App Cache", risk_level="safe",
                description="Steam 游戏平台下载游戏时的临时文件。下载完成或取消后残留。",
                cleaning_note="安全。"
            ),
            ScanItem(
                id="nvidia_dxcache", label="NVIDIA 着色器缓存 (DXCache)",
                path=os.path.join(local, "NVIDIA", "DXCache"),
                category="App Cache", risk_level="safe",
                description="NVIDIA 显卡的 DirectX 着色器编译缓存。删除后游戏/3D 应用首次运行时会重新编译。",
                cleaning_note="安全。部分游戏首次启动可能稍慢。"
            ),
            ScanItem(
                id="nvidia_glcache", label="NVIDIA OpenGL 缓存 (GLCache)",
                path=os.path.join(local, "NVIDIA", "GLCache"),
                category="App Cache", risk_level="safe",
                description="NVIDIA 显卡的 OpenGL 着色器编译缓存。",
                cleaning_note="安全清理。"
            ),

            # ================================================================
            #  九、其他可清理项 (Other Cleanable)
            # ================================================================
            ScanItem(
                id="recent", label="最近使用的文件快捷方式",
                path=os.path.join(roaming, "Microsoft", "Windows", "Recent"),
                category="Other", risk_level="safe",
                description="Windows「最近使用」列表中的快捷方式文件（.lnk）。清理后仅影响最近文件列表，不影响实际文件。",
                cleaning_note="安全。仅影响最近文件列表。"
            ),
            ScanItem(
                id="config_msi", label="MSI 安装配置文件",
                path=r"C:\Config.Msi", category="Other",
                risk_level="medium",
                description="Windows Installer 的回滚配置文件（.rbs 和 .rfb）。用于软件修复和卸载时回滚操作。",
                cleaning_note="⚠ 可能影响软件修复/卸载功能，建议保留。"
            ),
            ScanItem(
                id="msi_patchcache", label="MSI 补丁缓存 ($PatchCache$)",
                path=r"C:\Windows\Installer\$PatchCache$",
                category="Other", risk_level="medium",
                description="Windows Installer 的补丁缓存。删除可能影响已安装软件的更新和修复。",
                cleaning_note="⚠ 可能影响软件更新/修复。建议保留。"
            ),
            ScanItem(
                id="windows_old", label="Windows.old 旧系统备份",
                path=r"C:\Windows.old", category="Other",
                risk_level="caution",
                description="系统升级后保留的旧 Windows 文件。可通过「磁盘清理」工具删除，释放 10-30 GB 空间。",
                cleaning_note="系统稳定后可用磁盘清理工具删除。"
            ),

            # ================================================================
            #  十、只读信息（仅统计大小，不允许清理）
            # ================================================================
            ScanItem(
                id="winsxs", label="组件存储 WinSxS [只读]",
                path=r"C:\Windows\WinSxS", category="Read-Only Info",
                risk_level="caution",
                description="Windows 并行程序集存储，存放系统各版本组件。此目录体积巨大（10-20 GB），但实际占用远小于显示值（使用硬链接）。请勿手动删除，应使用 DISM 命令清理。",
                cleaning_note="🔒 禁止手动删除。请使用管理员命令：Dism.exe /Online /Cleanup-Image /StartComponentCleanup",
                readonly=True
            ),
            ScanItem(
                id="installer", label="Windows Installer 缓存 [只读]",
                path=r"C:\Windows\Installer", category="Read-Only Info",
                risk_level="caution",
                description="Windows Installer 的安装包缓存（.msi/.msp 文件）。用于软件修复、更新和卸载。手动删除可能导致软件无法正常更新或卸载。建议使用 PatchCleaner 工具清理无引用的文件。",
                cleaning_note="🔒 禁止手动删除。如需清理请使用 PatchCleaner 工具。",
                readonly=True
            ),
            ScanItem(
                id="pagefile", label="虚拟内存 pagefile.sys [只读]",
                path=r"C:\pagefile.sys", category="Read-Only Info",
                risk_level="caution",
                description="Windows 虚拟内存分页文件。大小通常等于物理内存大小或由系统自动管理。此文件是系统运行必需的，不能删除。可通过「高级系统设置」调整大小。",
                cleaning_note="🔒 系统必需文件，不可删除。可在系统属性中调整大小。",
                readonly=True
            ),
            ScanItem(
                id="hiberfil", label="休眠文件 hiberfil.sys [只读]",
                path=r"C:\hiberfil.sys", category="Read-Only Info",
                risk_level="medium",
                description="Windows 休眠功能的文件。大小约等于物理内存。如果不需要休眠功能，可通过管理员命令 powercfg /h off 关闭并自动删除此文件，释放对应空间。",
                cleaning_note="🔒 不可直接删除。如不需要休眠功能，请以管理员运行：powercfg /h off",
                readonly=True
            ),
            ScanItem(
                id="swapfile_sys", label="交换文件 swapfile.sys [只读]",
                path=r"C:\swapfile.sys", category="Read-Only Info",
                risk_level="caution",
                description="Windows UWP 应用的交换文件。系统必需，不可删除。",
                cleaning_note="🔒 系统必需文件，不可删除。",
                readonly=True
            ),

            # ================================================================
            #  十一、虚幻引擎 (Unreal Engine)
            # ================================================================
            ScanItem(
                id="ue_ddc", label="UE 派生数据缓存 (DerivedDataCache)",
                path=os.path.join(local, "UnrealEngine", "Common", "DerivedDataCache"),
                category="Unreal Engine", risk_level="medium",
                description="虚幻引擎的派生数据缓存（DDC），存储已编译的着色器、材质和资源数据。打开不同项目时会不断积累，可占数十 GB。删除后下次打开项目需重新编译着色器（耗时较长）。",
                cleaning_note="⚠ 删除后首次打开 UE 项目需重新编译着色器，可能耗时数十分钟。"
            ),
            ScanItem(
                id="ue_shader_cache", label="UE 着色器缓存 (ShaderCache)",
                path=os.path.join(local, "UnrealEngine", "Common", "ShaderCache"),
                category="Unreal Engine", risk_level="safe",
                description="虚幻引擎的着色器编译缓存，加速材质加载速度。删除后会自动重建。",
                cleaning_note="安全。重新打开项目时自动重建。"
            ),
            ScanItem(
                id="ue_intermediate", label="UE 编译中间文件 (Intermediate)",
                path=os.path.join(local, "UnrealEngine", "Common", "Intermediate"),
                category="Unreal Engine", risk_level="safe",
                description="虚幻引擎编译过程中生成的中间文件（.obj、.lib 等）。引擎关闭后可安全清理。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="ue_crash", label="UE 崩溃报告 (CrashReports)",
                path=os.path.join(up, "Documents", "Unreal Engine", "AutoSaved", "CrashReports"),
                category="Unreal Engine", risk_level="safe",
                description="虚幻引擎崩溃时自动生成的调试报告（.log、.dmp 文件）。仅对排障有用，可安全删除。",
                cleaning_note="安全。普通用户不需要崩溃报告。"
            ),
            ScanItem(
                id="ue_autosaved", label="UE 自动保存 (AutoSaved)",
                path=os.path.join(up, "Documents", "Unreal Engine", "AutoSaved"),
                category="Unreal Engine", risk_level="medium",
                description="虚幻引擎的自动保存目录，包含配置文件、场景快照和日志。可能包含未保存的项目恢复数据。",
                cleaning_note="⚠ 清理前确认没有需要恢复的未保存工作。"
            ),
            ScanItem(
                id="epic_vault", label="Epic Games 保管库缓存 (VaultCache)",
                path=r"C:\Program Files (x86)\Epic Games\Launcher\VaultCache",
                category="Unreal Engine", risk_level="safe",
                description="Epic Games Launcher 从商城下载的资产包缓存。下载并导入项目后不再需要。",
                cleaning_note="安全。已导入项目的资产不受影响。"
            ),
            ScanItem(
                id="epic_launcher_cache", label="Epic Games Launcher 缓存",
                path=os.path.join(local, "Epic Games Launcher"),
                category="Unreal Engine", risk_level="safe",
                description="Epic Games Launcher 的网页缓存和临时数据。清理后启动器会重新加载。",
                cleaning_note="安全清理。"
            ),

            # ================================================================
            #  十二、VP 虚拟制作 (Virtual Production & Broadcast)
            # ================================================================
            ScanItem(
                id="aximmetry_recorded", label="Aximmetry 录制/导出数据 (Recorded)",
                path=os.path.join(up, "Documents", "Aximmetry", "Recorded"),
                category="VP & Broadcast", risk_level="medium",
                description="Aximmetry 虚拟制作系统的录制文件和导出数据。包含节目录制输出，可能占用大量磁盘空间。",
                cleaning_note="⚠ 请确认录制已导出备份后再清理。"
            ),
            ScanItem(
                id="aximmetry_profiles", label="Aximmetry 渲染配置缓存",
                path=os.path.join(up, "Documents", "Aximmetry", "RenderProfiles"),
                category="VP & Broadcast", risk_level="safe",
                description="Aximmetry 的渲染配置文件缓存。包含渲染管线预设和临时渲染数据。",
                cleaning_note="安全清理。自定义预设需手动备份。"
            ),
            ScanItem(
                id="disguise_thumbnails", label="Disguise 缩略图与渲染缓存",
                path=r"C:\ProgramData\Disguise\ThumbnailCache",
                category="VP & Broadcast", risk_level="safe",
                description="Disguise d3 虚拟制作系统生成的媒体缩略图和渲染缓存。用于快速预览素材。",
                cleaning_note="安全。重新打开项目时会自动重建缩略图。"
            ),
            ScanItem(
                id="disguise_logs", label="Disguise 日志与临时文件",
                path=r"C:\ProgramData\Disguise\Logs",
                category="VP & Broadcast", risk_level="safe",
                description="Disguise 系统的运行日志和临时文件。用于排障分析。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="pixotope_storage", label="Pixotope 本地存储 (Local Storage)",
                path=os.path.join(local, "Pixotope"),
                category="VP & Broadcast", risk_level="medium",
                description="Pixotope 广播图形系统的本地缓存和 Show 文件临时数据。",
                cleaning_note="⚠ 可能包含项目配置。清理前请备份重要的 Show 文件。"
            ),
            ScanItem(
                id="zd_reality_cache", label="Zero Density Reality 项目缓存",
                path=os.path.join(local, "ZeroDensity"),
                category="VP & Broadcast", risk_level="medium",
                description="Zero Density Reality 引擎的项目缓存。缓存路径取决于引擎配置，此为常见默认位置。删除后不影响原始项目文件。",
                cleaning_note="⚠ 建议通过 Reality Hub 管理界面清理缓存。"
            ),
            ScanItem(
                id="bmd_resolve_logs", label="Blackmagic Design 日志",
                path=os.path.join(local, "Blackmagic Design"),
                category="VP & Broadcast", risk_level="safe",
                description="Blackmagic Design 软件（DaVinci Resolve、ATEM 等）的日志和临时缓存。",
                cleaning_note="安全清理。"
            ),

            # ================================================================
            #  十三、CG 与后期制作 (CG & Post-Production)
            # ================================================================
            ScanItem(
                id="ae_media_cache", label="AE/PR 媒体缓存 (Media Cache Files)",
                path=os.path.join(roaming, "Adobe", "Common", "Media Cache Files"),
                category="CG & Post-Production", risk_level="safe",
                description="Adobe After Effects 和 Premiere Pro 的媒体缓存文件。导入视频/音频时自动生成的优化索引和预览数据。",
                cleaning_note="安全。重新导入素材时会自动重建。清理前请关闭 AE/PR。"
            ),
            ScanItem(
                id="ae_disk_cache", label="AE 磁盘缓存 (Disk Cache)",
                path=os.path.join(roaming, "Adobe", "After Effects", "Disk Cache"),
                category="CG & Post-Production", risk_level="safe",
                description="After Effects 的帧渲染缓存（RAM Preview 写入磁盘的部分）。加速预览播放回放。",
                cleaning_note="安全。下次预览时自动重建。"
            ),
            ScanItem(
                id="ae_autosave", label="AE 自动保存 (Auto-Save)",
                path=os.path.join(up, "Documents", "Adobe", "After Effects", "Auto-Save"),
                category="CG & Post-Production", risk_level="medium",
                description="After Effects 的自动保存项目文件。可用于恢复意外关闭的项目。",
                cleaning_note="⚠ 清理前确认当前项目已手动保存。"
            ),
            ScanItem(
                id="pr_preview", label="PR 预览文件 (Preview Files)",
                path=os.path.join(up, "Documents", "Adobe", "Premiere Pro", "Preview Files"),
                category="CG & Post-Production", risk_level="safe",
                description="Premiere Pro 的预览渲染文件（.avp/.mp4 索引）。删除后需重新生成预览。",
                cleaning_note="安全。重新打开时间线后需重新生成预览。"
            ),
            ScanItem(
                id="maya_temp", label="Maya 临时文件与缓存",
                path=os.path.join(up, "Documents", "maya", "projects"),
                category="CG & Post-Production", risk_level="medium",
                description="Autodesk Maya 的项目目录缓存。包含自动保存场景、渲染输出、粒子缓存等。",
                cleaning_note="⚠ 可能包含未保存的工作。请确认已保存所有项目后再清理。"
            ),
            ScanItem(
                id="houdini_cache", label="Houdini 着色器与模拟缓存",
                path=os.path.join(up, "Documents", "houdini"),
                category="CG & Post-Production", risk_level="safe",
                description="SideFX Houdini 的项目配置和缓存目录。包含着色器缓存、模拟临时数据等。",
                cleaning_note="安全。自定义工具和 OTL 需手动备份。"
            ),
            ScanItem(
                id="houdini_temp", label="Houdini 临时文件",
                path=os.path.join(local, "Side Effects Software"),
                category="CG & Post-Production", risk_level="safe",
                description="Houdini 的本地临时文件和许可证缓存。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="c4d_cache", label="Cinema 4D 预设与缓存",
                path=os.path.join(up, "Documents", "Maxon"),
                category="CG & Post-Production", risk_level="medium",
                description="Maxon Cinema 4D 的预设库、浏览器缓存和临时渲染文件。包含自定义材质预设。",
                cleaning_note="⚠ 自定义预设会一并删除。请手动备份重要预设。"
            ),
            ScanItem(
                id="blender_config", label="Blender 配置与临时文件",
                path=os.path.join(roaming, "Blender Foundation"),
                category="CG & Post-Production", risk_level="safe",
                description="Blender 的用户配置、自动保存和备份文件。",
                cleaning_note="安全。插件配置会恢复为默认值。"
            ),
            ScanItem(
                id="davinci_cache", label="DaVinci Resolve 渲染缓存",
                path=os.path.join(up, "Documents", "Blackmagic Design", "DaVinci Resolve"),
                category="CG & Post-Production", risk_level="medium",
                description="DaVinci Resolve 的项目数据，包含渲染缓存（CacheClip）、代理文件、调色预设和静帧画廊。",
                cleaning_note="⚠ 包含渲染缓存和代理文件。建议在 Resolve 内部通过「Playback > Delete Render Cache」清理。"
            ),
            ScanItem(
                id="nuke_cache", label="Nuke 缓存 (Disk Cache)",
                path=os.path.join(up, "Documents", "Foundry", "Nuke"),
                category="CG & Post-Production", risk_level="safe",
                description="Foundry Nuke 的磁盘缓存和临时文件。默认大小上限为 10 GB。",
                cleaning_note="安全。可通过环境变量 NUKE_DISK_CACHE 配置路径。"
            ),
            ScanItem(
                id="redshift_cache", label="Redshift 核心缓存",
                path=os.path.join(local, "Redshift"),
                category="CG & Post-Production", risk_level="safe",
                description="Redshift GPU 渲染器的核心缓存，包含着色器编译缓存和体积纹理缓存。",
                cleaning_note="安全。重新渲染时自动重建。"
            ),
            ScanItem(
                id="octane_cache", label="OctaneRender 缓存",
                path=os.path.join(local, "OctaneRender"),
                category="CG & Post-Production", risk_level="safe",
                description="Octane Render GPU 渲染器的着色器编译缓存和纹理缓存。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="vray_cache", label="V-Ray 着色器与灯光缓存",
                path=os.path.join(up, "Documents", "V-Ray"),
                category="CG & Post-Production", risk_level="safe",
                description="Chaos V-Ray 渲染器的灯光缓存（LCM）、 irradiance map 和着色器缓存。",
                cleaning_note="安全。下次渲染会重新计算。"
            ),
            ScanItem(
                id="nvidia_nv_cache", label="NVIDIA 渲染缓存 (NV_Cache)",
                path=os.path.join(local, "NVIDIA Corporation", "NV_Cache"),
                category="CG & Post-Production", risk_level="safe",
                description="NVIDIA 驱动级别的渲染缓存（含 OpenGL 着色器和 RTX 光追缓存）。VP/CG 工作站常见数 GB。",
                cleaning_note="安全。删除后首次渲染可能稍慢。"
            ),
            ScanItem(
                id="hecoos_cache", label="Hecoos Studio 缓存",
                path=os.path.join(local, "Hecoos"),
                category="VP & Broadcast", risk_level="medium",
                description="Hecoos 全域创作软件的场景缓存、预演渲染数据和日志文件。",
                cleaning_note="⚠ 可能包含项目预演数据。清理前请确认已导出。"
            ),

            # ================================================================
            #  十四、Windows 11 特有 (Win11 Exclusive)
            # ================================================================
            ScanItem(
                id="win11_widgets", label="Win11 小组件缓存",
                path=os.path.join(local, "Packages", "MicrosoftWindows.Client.WebExperience_*", "LocalCache"),
                category="Win11 Exclusive", risk_level="safe",
                description="Windows 11 小组件（天气、新闻等）的缓存数据。通配符匹配，自动检测是否存在。",
                cleaning_note="安全清理。组件会自动重新加载。"
            ),
            ScanItem(
                id="win11_teams_new", label="Win11 新版 Teams 缓存",
                path=os.path.join(local, "Packages", "MSTeams_*", "LocalCache"),
                category="Win11 Exclusive", risk_level="safe",
                description="Windows 11 预装的新版 Microsoft Teams（UWP 版）的缓存数据。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="win11_clipboard", label="Win11 剪贴板历史",
                path=os.path.join(local, "Packages", "Microsoft.Windows.Photos_*", "TempState"),
                category="Win11 Exclusive", risk_level="safe",
                description="Win11 系统应用（照片等）的临时状态缓存。通配符匹配。",
                cleaning_note="安全清理。"
            ),
        ]

        # --- 安装检测：在通配符展开前基于原始 id 判断（未安装软件后续可隐藏）---
        for t in targets:
            try:
                t.installed = DetectionService.is_installed(t)
            except Exception:
                t.installed = True

        # --- 处理通配符路径：展开为多个具体路径 ---
        expanded = []
        for t in targets:
            if "*" in t.path:
                resolved = self._resolve_paths(t.path)
                if resolved:
                    for i, rp in enumerate(resolved):
                        expanded_item = ScanItem(
                            id=f"{t.id}_{i}",
                            label=t.label,
                            path=rp,
                            category=t.category,
                            risk_level=t.risk_level,
                            description=t.description,
                            cleaning_note=t.cleaning_note,
                            readonly=t.readonly,
                            installed=t.installed,
                            source=t.source,
                            custom=t.custom,
                            detect=list(t.detect),
                            detect_reg=list(t.detect_reg),
                            patterns=list(t.patterns),
                            recurse=t.recurse,
                        )
                        expanded.append(expanded_item)
                # 如果通配符没有匹配到任何路径，也保留原始项（扫描时显示不存在）
                elif not resolved:
                    expanded.append(t)
            else:
                expanded.append(t)

        # --- 合并 winapp2 数据库条目（迭代2）---
        if winapp2_items:
            for w in winapp2_items:
                try:
                    w.installed = DetectionService.is_installed(w)
                except Exception:
                    w.installed = True
                # winapp2 的 FileKey 路径可能含通配符，展开之
                if "*" in w.path:
                    for wi, rp in enumerate(PathExpander.resolve_matches(w.path)):
                        expanded.append(ScanItem(
                            id=f"{w.id}_{wi}", label=w.label, path=rp, category=w.category,
                            risk_level=w.risk_level, description=w.description,
                            cleaning_note=w.cleaning_note, readonly=w.readonly,
                            installed=w.installed, source=w.source, custom=w.custom,
                            detect=list(w.detect), detect_reg=list(w.detect_reg),
                            patterns=list(w.patterns), recurse=w.recurse,
                        ))
                else:
                    expanded.append(w)

        # --- 合并规则数据库（Databases/*.ini）与自定义规则（Custom/*.ini） ---
        extra = list(db_items or []) + list(custom_items or [])
        if extra:
            for c in extra:
                try:
                    c.installed = DetectionService.is_installed(c)
                except Exception:
                    c.installed = True
                # 自定义规则路径同样可能含通配符
                if "*" in c.path:
                    for ci, rp in enumerate(PathExpander.resolve_matches(c.path)):
                        expanded.append(ScanItem(
                            id=f"{c.id}_{ci}", label=c.label, path=rp, category=c.category,
                            risk_level=c.risk_level, description=c.description,
                            cleaning_note=c.cleaning_note, readonly=c.readonly,
                            installed=c.installed, source=c.source, custom=c.custom,
                            detect=list(c.detect), detect_reg=list(c.detect_reg),
                            patterns=list(c.patterns), recurse=c.recurse,
                        ))
                else:
                    expanded.append(c)

        return expanded

    def _get_sub_items(self, path: str, top_n: int = 10) -> list:
        """获取目录中最大的前 N 个子项"""
        sub_items = []
        try:
            if os.path.isdir(path):
                entries = []
                for entry in os.scandir(path):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            size = entry.stat(follow_symlinks=False).st_size
                            entries.append((entry.name, size, False))
                        elif entry.is_dir(follow_symlinks=False):
                            dir_size = sum(
                                f.stat(follow_symlinks=False).st_size
                                for f in self._walk_files(entry.path)
                            )
                            entries.append((entry.name, dir_size, True))
                    except (PermissionError, OSError):
                        pass
                entries.sort(key=lambda x: x[1], reverse=True)
                sub_items = [
                    {
                        "name": name,
                        "size": size,
                        "is_dir": is_dir,
                        "size_str": self._format_size(size)
                    }
                    for name, size, is_dir in entries[:top_n]
                    if size > 0
                ]
        except (PermissionError, OSError):
            pass
        return sub_items

    @staticmethod
    def _walk_files(path: str):
        """递归遍历目录中的所有文件"""
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        yield entry
                    elif entry.is_dir(follow_symlinks=False):
                        yield from ScanEngine._walk_files(entry.path)
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes >= 1024 ** 3:
            return f"{size_bytes / (1024 ** 3):.2f} GB"
        elif size_bytes >= 1024 ** 2:
            return f"{size_bytes / (1024 ** 2):.2f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes} B"

    def _scan_path(self, item: ScanItem):
        """扫描单个路径"""
        try:
            if os.path.isfile(item.path):
                item.exists = True
                item.files = 1
                item.folders = 0
                item.size_bytes = os.path.getsize(item.path)
            elif os.path.isdir(item.path):
                item.exists = True
                # 自定义规则带 patterns：仅统计/清理匹配通配符的文件
                if item.patterns:
                    matched = PathExpander.match_files(item.path, item.patterns, item.recurse)
                    item.files = len(matched)
                    item.folders = 0
                    item.size_bytes = sum(self._safe_size(f) for f in matched)
                    item.sub_items = []
                else:
                    file_count = 0
                    dir_count = 0
                    total_size = 0
                    for root, dirs, files in os.walk(item.path):
                        dir_count += len(dirs)
                        for f in files:
                            try:
                                fp = os.path.join(root, f)
                                total_size += os.path.getsize(fp)
                                file_count += 1
                            except (PermissionError, OSError):
                                pass
                    item.files = file_count
                    item.folders = dir_count
                    item.size_bytes = total_size
                    # 获取子项明细
                    item.sub_items = self._get_sub_items(item.path, top_n=10)
            else:
                item.exists = False
        except (PermissionError, OSError) as e:
            item.exists = False
            item.description += f" [访问被拒绝: {e}]"

    @staticmethod
    def _safe_size(path: str) -> int:
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    def scan_all(self, custom_items: List["ScanItem"] = None,
                 winapp2_items: List["ScanItem"] = None,
                 winapp2_excludes: List = None,
                 global_excludes: List = None,
                 db_items: List["ScanItem"] = None) -> List[ScanItem]:
        """执行全部扫描。

        参数:
          custom_items    : Custom/*.ini 解析出的规则（None 则自动加载）
          db_items        : Databases/*.ini 规则数据库（None 则自动加载）
          winapp2_items   : winapp2 数据库解析出的 ScanItem 列表
          winapp2_excludes: winapp2 收集到的排除规则 [(type, value), ...]
          global_excludes : 用户在设置中配置的全局排除 [(type, value), ...]
        排除规则汇总后存入 self.exclude_rules，供 CleanEngine 使用。
        """
        if custom_items is None:
            custom_items = load_custom_rules()
        if db_items is None:
            db_items = load_database_rules()
        if winapp2_items is None:
            winapp2_items = []
        if winapp2_excludes is None:
            winapp2_excludes = []
        if global_excludes is None:
            global_excludes = []

        # 汇总排除规则：全局排除优先于 winapp2 排除。
        # 规范化为 (type, value)：winapp2 已是元组；用户全局排除为纯路径 → 视为 PATH。
        norm_global = []
        for g in global_excludes:
            if isinstance(g, str):
                g = g.strip()
                if g:
                    norm_global.append(("PATH", g))
            elif isinstance(g, (list, tuple)) and len(g) == 2:
                norm_global.append((str(g[0]).upper(), g[1]))
        self.exclude_rules = list(winapp2_excludes) + norm_global

        targets = self.get_scan_targets(
            custom_items=custom_items, winapp2_items=winapp2_items,
            db_items=db_items)
        total = len(targets)
        self.results = []

        for i, item in enumerate(targets):
            # 未安装软件：跳过耗时遍历，直接标记为空（hide 时可隐藏）
            if not item.installed:
                item.exists = False
                item.files = 0
                item.folders = 0
                item.size_bytes = 0
                self.results.append(item)
                self._progress(i + 1, total)
                continue
            self._log(f"正在扫描: {item.label}...")
            self._scan_path(item)
            self.results.append(item)
            self._progress(i + 1, total)

        # 按大小降序排列
        self.results.sort(key=lambda x: x.size_bytes, reverse=True)
        self._log("扫描完成！")
        return self.results


class CleanEngine:
    """清理引擎"""

    def __init__(self, log_callback=None, exclude_rules: List = None,
                 log_file: str = None):
        self._log = log_callback or (lambda msg: None)
        self._cleaned_items = []
        # 排除规则：[(type, value), ...]，type ∈ {"FILE","PATH"}
        #   FILE : value 为 "dir|pattern" 或 精确文件路径
        #   PATH : value 为 目录（其下所有文件/子目录均受保护）
        self.exclude_rules = exclude_rules or []
        self._normalize_exclusions()
        # 迭代3：审计日志文件（每次实际删除都会追加记录）。None = 不写文件。
        self.log_file = log_file
        self._audit_fh = None

    def set_exclusions(self, rules: List):
        self.exclude_rules = rules or []
        self._normalize_exclusions()

    def _normalize_exclusions(self):
        """BUGFIX B2: 展开排除规则中的环境变量。

        winapp2 的 ExcludeKey 形如 `FILE|%LocalAppData%\\Foo\\|*.log`，
        不展开的话 _is_excluded 永远匹配不上真实路径 → 排除保护完全失效。
        构造时一次性展开，避免逐文件重复解析。
        """
        normalized = []
        for rule in self.exclude_rules:
            try:
                typ, val = rule
            except (TypeError, ValueError):
                continue
            normalized.append((str(typ).upper(), PathExpander.expand(str(val))))
        self.exclude_rules = normalized

    # ---- 迭代3：审计日志 ----
    def _write_audit(self, line: str):
        """追加一行审计日志（仅在发生实际删除时惰性打开文件）。"""
        if not self.log_file:
            return
        try:
            if self._audit_fh is None:
                try:
                    is_new = (not os.path.exists(self.log_file)
                              or os.path.getsize(self.log_file) == 0)
                except OSError:
                    is_new = True
                self._audit_fh = open(self.log_file, "a", encoding="utf-8")
                if is_new:
                    self._audit_fh.write(
                        "# SysClean Cleanup Audit Log\n"
                        "# 每次实际删除都会追加记录。\n"
                        "# 列：TIMESTAMP\\tACTION\\tLABEL\\tPATH\\tSIZE_BYTES\n"
                    )
                self._audit_fh.write(
                    f"# --- Session "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
            self._audit_fh.write(line + "\n")
            self._audit_fh.flush()
        except OSError:
            pass

    def finalize(self):
        """清理结束：写入会话总计并关闭审计文件。"""
        if self._audit_fh is not None:
            try:
                total = sum(c["freed_bytes"] for c in self._cleaned_items)
                self._audit_fh.write(
                    f"# === Session total: {len(self._cleaned_items)} items, "
                    f"{ScanEngine._format_size(total)} freed ===\n\n"
                )
                self._audit_fh.close()
            except OSError:
                pass
            self._audit_fh = None

    def _is_excluded(self, path: str) -> bool:
        """判断某路径是否命中排除规则（FILE/PATH，支持通配符）。"""
        if not self.exclude_rules or not path:
            return False
        import fnmatch
        cand = os.path.normcase(os.path.normpath(path))
        cand_dir = os.path.normcase(os.path.normpath(os.path.dirname(path)))

        def _dir_match(base: str, target: str) -> bool:
            base = os.path.normcase(base).rstrip("\\/")
            target = os.path.normcase(target).rstrip("\\/")
            if ("*" not in base) and ("?" not in base):
                return target == base or target.startswith(base + os.sep)
            # 含通配符：用 fnmatch（* 跨路径分隔符匹配）
            if fnmatch.fnmatch(target, base):
                return True
            if fnmatch.fnmatch(target, base + "/*"):
                return True
            return False

        for typ, val in self.exclude_rules:
            if typ == "PATH":
                if _dir_match(val, cand) or _dir_match(val, cand_dir):
                    return True
            elif typ == "FILE":
                if "|" in val:
                    d, pat = val.split("|", 1)
                    if _dir_match(d, cand_dir) and fnmatch.fnmatch(os.path.basename(cand), pat):
                        return True
                else:
                    ex = os.path.normcase(os.path.normpath(val))
                    if cand == ex:
                        return True
        return False

    def clean_item(self, item: ScanItem) -> Tuple[bool, int]:
        """
        清理单个项目
        返回: (是否成功, 释放的字节数)
        """
        # 只读项不允许清理
        if item.readonly:
            self._log(f"跳过 (只读/禁止清理): {item.label}")
            return False, 0

        # 自定义规则带 patterns：按 glob 精确删除匹配文件（与聚合 size 无关）
        if item.patterns:
            if self._is_excluded(item.path):
                self._log(f"跳过 (命中排除规则，受保护): {item.label} -> {item.path}")
                return True, 0
            return self._clean_with_patterns(item)

        # 整体路径命中排除规则 → 跳过（保护用户文件）
        if self._is_excluded(item.path):
            self._log(f"跳过 (命中排除规则，受保护): {item.label} -> {item.path}")
            return True, 0

        if not item.exists or item.size_bytes == 0:
            self._log(f"跳过 (不存在或为空): {item.label}")
            return True, 0

        try:
            path = item.path
            freed = 0
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if os.path.isfile(path):
                freed = os.path.getsize(path)
                # BUGFIX B4: 单文件此前是 os.remove 永久删除，与 UI「移至回收站」
                # 文案不符。统一走 Shell 回收站（失败时 _delete_to_recycle_bin
                # 内部兜底为直接删除，行为不比原先更差）。
                self._delete_to_recycle_bin(path)
                self._log(f"已移至回收站: {path}")
            elif os.path.isdir(path):
                freed = item.size_bytes
                # 使用系统 API 移到回收站
                self._delete_to_recycle_bin(path)
                self._log(f"已移至回收站: {path}")

            # BUGFIX: 校验真的删掉了再记审计、再统计释放空间。
            # 原实现先写日志/先计数后删除，删除被占用失败时审计会虚高。
            if os.path.exists(path):
                self._log(f"清理未生效（仍存在，可能被占用）: {path}")
                return False, 0

            self._cleaned_items.append({
                "label": item.label,
                "path": path,
                "freed_bytes": freed,
                "freed_str": ScanEngine._format_size(freed)
            })
            # 迭代3：审计日志（仅记录实际删除）
            self._write_audit(f"{ts}\tDELETE\t{item.label}\t{path}\t{freed}")
            return True, freed

        except Exception as e:
            self._log(f"清理失败 [{item.label}]: {e}")
            return False, 0

    def _clean_with_patterns(self, item: ScanItem) -> Tuple[bool, int]:
        """按 patterns 精确删除匹配文件（移入回收站），不动目录内其他文件。"""
        matched = PathExpander.match_files(item.path, item.patterns, item.recurse)
        if not matched:
            self._log(f"跳过 (无匹配文件): {item.label}")
            return True, 0
        sizes = {}
        deleted = []
        skipped = 0
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for fp in matched:
            # 命中排除规则的文件保留
            if self._is_excluded(fp):
                self._log(f"保留 (命中排除规则): {fp}")
                skipped += 1
                continue
            try:
                sizes[fp] = os.path.getsize(fp)
                deleted.append(fp)
            except OSError:
                pass

        if deleted:
            self._delete_to_recycle_bin_multi(deleted)
        # BUGFIX: 只统计「真的被移走」的文件 —— 原实现在删除前就累加 size 并写
        # 审计日志，被占用/权限不足时审计与释放空间都会虚高。
        really = [fp for fp in deleted if not os.path.exists(fp)]
        freed = sum(sizes.get(fp, 0) for fp in really)
        for fp in really:
            self._log(f"已移至回收站: {fp}")
            self._write_audit(f"{ts}\tDELETE\t{item.label}\t{fp}\t{sizes.get(fp, 0)}")
        missed = [fp for fp in deleted if os.path.exists(fp)]
        for fp in missed:
            self._log(f"清理未生效（仍存在，可能被占用）: {fp}")
        if skipped:
            self._log(f"{item.label}: 跳过 {skipped} 个受保护文件")
        self._cleaned_items.append({
            "label": item.label,
            "path": item.path,
            "freed_bytes": freed,
            "freed_str": ScanEngine._format_size(freed)
        })
        return True, freed

    @staticmethod
    def _delete_to_recycle_bin_multi(paths: List[str]):
        """将多个文件/文件夹移入回收站（double-null 终止的路径列表）。
        若 Shell 操作未真正移除文件（无桌面/服务环境），回退为直接删除。"""
        if not paths:
            return
        try:
            from ctypes import windll
            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x40
            FOF_NOCONFIRMATION = 0x10
            FOF_SILENT = 0x4
            flags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
            multi = "\0".join(paths) + "\0\0"
            path_ptr = ctypes.c_wchar_p(multi)
            null_ptr = ctypes.c_wchar_p(None)
            windll.shell32.SHFileOperationW(
                0, FO_DELETE, path_ptr, null_ptr, flags, None, None
            )
        except Exception:
            pass
        # 校验：任何仍存在的路径做兜底删除
        for p in paths:
            if os.path.exists(p):
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                    else:
                        shutil.rmtree(p, ignore_errors=True)
                except OSError:
                    pass

    @staticmethod
    def _delete_to_recycle_bin(path: str):
        """使用 Windows Shell API 将文件/文件夹移到回收站。
        若 Shell 操作未真正移除（无桌面环境），回退为直接删除。"""
        try:
            from ctypes import windll
            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x40
            FOF_NOCONFIRMATION = 0x10
            FOF_SILENT = 0x4
            flags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT

            path_ptr = ctypes.c_wchar_p(path)
            null_ptr = ctypes.c_wchar_p(None)

            windll.shell32.SHFileOperationW(
                0, FO_DELETE, path_ptr, null_ptr, flags, None, None
            )
        except Exception:
            pass
        # 校验兜底
        if os.path.exists(path):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                pass


class ReportGenerator:
    """报告生成器"""

    @staticmethod
    def generate_text_report(results: List[ScanItem], cleaned_items: list = None) -> str:
        """Generate plain-text report"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_bytes = sum(r.size_bytes for r in results if r.exists and r.size_bytes > 0)

        lines = [
            "=" * 70,
            "   SysClean - System Junk File Scan Report",
            f"   Scan Time: {now}",
            f"   OS: {platform.platform()}",
            "=" * 70,
            "",
            f"{'#':<4} {'Name':<38} {'Size':>10} {'Files':>8}  {'Risk':>6}",
            "-" * 70,
        ]

        idx = 1
        for item in results:
            if item.exists and item.size_bytes > 0:
                lines.append(
                    f"{idx:<4} {item.label:<38} {item.size_str:>10} "
                    f"{item.files:>8}  {item.risk_display:>6}"
                )
                idx += 1

        lines.extend([
            "",
            "-" * 70,
            f"  Total scan targets: {len(results)}",
            f"  Found (non-empty):  {idx - 1}",
            f"  Total space:        {ScanEngine._format_size(total_bytes)}",
            f"  Total space:        {total_bytes / (1024**3):.2f} GB",
            "=" * 70,
        ])

        if cleaned_items:
            cleaned_bytes = sum(c["freed_bytes"] for c in cleaned_items)
            lines.extend([
                "",
                "=" * 70,
                "   Cleanup Record",
                "=" * 70,
            ])
            for c in cleaned_items:
                lines.append(f"  [OK] {c['label']:<38} {c['freed_str']:>10}")
            lines.extend([
                "",
                f"  Total freed: {ScanEngine._format_size(cleaned_bytes)}",
                "=" * 70,
            ])

        return "\n".join(lines)

    @staticmethod
    def generate_json_report(results: List[ScanItem]) -> str:
        """生成 JSON 格式报告"""
        data = {
            "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "os": platform.platform(),
            "total_size_bytes": sum(r.size_bytes for r in results),
            "items": []
        }
        for item in results:
            data["items"].append({
                "id": item.id,
                "label": item.label,
                "path": item.path,
                "category": item.category,
                "risk_level": item.risk_level,
                "size_bytes": item.size_bytes,
                "size_str": item.size_str,
                "files": item.files,
                "folders": item.folders,
                "exists": item.exists,
                "description": item.description,
                "cleaning_note": item.cleaning_note,
                "sub_items": item.sub_items,
            })
        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def generate_csv_report(results: List[ScanItem], cleaned_items: list = None) -> str:
        """生成 CSV 格式报告（带 BOM，Excel 可正确显示中文）。"""
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Label", "Path", "Category", "Risk", "SizeBytes", "SizeStr",
            "Files", "Folders", "Exists", "Description"
        ])
        for item in results:
            writer.writerow([
                item.label, item.path, item.category, item.risk_level,
                item.size_bytes, item.size_str, item.files, item.folders,
                item.exists, item.description
            ])
        if cleaned_items:
            writer.writerow([])
            writer.writerow(["Cleanup Record"])
            writer.writerow(["Label", "Path", "FreedBytes", "FreedStr"])
            for c in cleaned_items:
                writer.writerow([c["label"], c["path"], c["freed_bytes"], c["freed_str"]])
        return buf.getvalue()


def default_cleanup_log_path() -> str:
    """返回清理审计日志的默认路径。

    优先 exe/脚本同目录的 SysClean_cleanup.log（便携模式）；
    不可写时退回 %APPDATA%/SysClean/cleanup.log。
    """
    try:
        from app_paths import writable_dir
        base = writable_dir()
    except Exception:
        try:
            from settings import _project_base
            base = _project_base()
        except Exception:
            base = os.getcwd()
    cand = os.path.join(base, "SysClean_cleanup.log")
    try:
        if os.access(base, os.W_OK) or not os.path.exists(cand):
            return cand
    except OSError:
        pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        folder = os.path.join(appdata, "SysClean")
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass
        return os.path.join(folder, "cleanup.log")
    return cand
