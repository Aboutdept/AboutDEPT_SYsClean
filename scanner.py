# -*- coding: utf-8 -*-
"""
SysClean - 系统垃圾文件扫描与清理工具
扫描 Windows 系统常见垃圾文件位置，提供可视化报告和一键清理功能。
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import glob
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


class ScanEngine:
    """扫描引擎 - 定义扫描目标并执行扫描"""

    def __init__(self):
        self.results: List[ScanItem] = []
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

    def get_scan_targets(self) -> List[ScanItem]:
        """返回所有预定义的扫描目标，涵盖 Windows 10/11"""
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

            # ================================================================
            #  十五、系统还原与修复 (System Restore & Repair)
            # ================================================================
            ScanItem(
                id="system_restore", label="系统还原点",
                path=r"C:\System Volume Information",
                category="System Restore", risk_level="caution",
                description="系统还原点的存储区域。占用空间可能较大（数 GB）。删除还原点会释放空间，但会清除所有系统还原历史。",
                cleaning_note="⚠ 警告：删除后无法通过系统还原来恢复系统。建议仅清理过旧的还原点。"
            ),
            ScanItem(
                id="dotnet_native_cache", label=".NET Native 程序集缓存",
                path=os.path.join(local, "Microsoft", "NET", "Native"),
                category="Dev Tools", risk_level="medium",
                description="UWP/.NET Native 应用编译后的程序集缓存。用于加速应用启动。",
                cleaning_note="删除后相关 UWP 应用首次启动会稍慢。"
            ),
            ScanItem(
                id="dotnet_share_cache", label=".NET Share 程序集缓存",
                path=os.path.join(local, "Microsoft", "NET", "Share"),
                category="Dev Tools", risk_level="medium",
                description=".NET 共享程序集缓存。存储多个 .NET 应用共享的预编译程序集。",
                cleaning_note="删除后 .NET 应用可能需要重新编译。"
            ),
            ScanItem(
                id="dotnet_framework_cache", label=".NET Framework 内部缓存",
                path=r"C:\Windows\Microsoft.NET",
                category="Dev Tools", risk_level="medium",
                description=".NET Framework 的临时文件和程序集缓存。包含已下载的 .NET 程序集和中间文件。",
                cleaning_note="删除后 .NET Framework 应用可能需要重新下载依赖。"
            ),
            ScanItem(
                id="baidu_netdisk_logs", label="百度网盘日志",
                path=os.path.join(local, "Baidu", "Netdisk"),
                category="App Cache", risk_level="safe",
                description="百度网盘的日志文件。包含下载、上传、同步等操作记录。",
                cleaning_note="安全清理。删除后不影响百度网盘正常使用。"
            ),
            ScanItem(
                id="vs_component_model", label="VS 组件模型缓存",
                path=os.path.join(local, "Microsoft", "VisualStudio", "*", "ComponentModelCache"),
                category="Dev Tools", risk_level="safe",
                description="Visual Studio 的组件模型缓存（MEF 缓存）。用于加速扩展加载。通配符匹配各版本。",
                cleaning_note="安全。VS 会自动重建缓存。"
            ),
            ScanItem(
                id="vs_extensions", label="VS 扩展缓存",
                path=os.path.join(local, "Microsoft", "VisualStudio", "*", "Extensions"),
                category="Dev Tools", risk_level="safe",
                description="Visual Studio 已安装扩展的缓存。通配符匹配各版本。",
                cleaning_note="安全。已安装的扩展不受影响。"
            ),
            ScanItem(
                id="vs_database", label="VS 数据库缓存",
                path=os.path.join(local, "Microsoft", "VisualStudio", "*", "Database"),
                category="Dev Tools", risk_level="safe",
                description="Visual Studio 的数据库工具缓存。包含 SQL Server 项目的临时数据。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="vs_shader_cache", label="VS 着色器缓存",
                path=os.path.join(local, "Microsoft", "VisualStudio", "*", "ShaderCache"),
                category="Dev Tools", risk_level="safe",
                description="Visual Studio 的图形诊断着色器缓存。用于 DirectX 和 HLSL 调试。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="vsdebugger", label="VS 调试器临时文件",
                path=os.path.join(local, "Microsoft", "VSCommon", "VSCommon"),
                category="Dev Tools", risk_level="safe",
                description="Visual Studio 调试器的临时文件和缓存。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="vs_pxg_cache", label="VS Performance 性能缓存",
                path=os.path.join(local, "Microsoft", "VSCommon", "PerformanceEngine"),
                category="Dev Tools", risk_level="safe",
                description="Visual Studio 性能分析工具的缓存数据。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="package_cache", label="VS Installer Package Cache",
                path=r"C:\ProgramData\Package Cache",
                category="Dev Tools", risk_level="medium",
                description="Visual Studio Installer 的下载包缓存。包含已下载的 VS 安装包。",
                cleaning_note="⚠ 清理后如需修复/修改 VS 可能需要重新下载。"
            ),

            # ================================================================
            #  十六、VP 虚拟制作扩展 (VP & Broadcast Extended)
            # ================================================================
            ScanItem(
                id="notch_cache", label="Notch 渲染器缓存",
                path=os.path.join(local, "Notch"),
                category="VP & Broadcast Extended", risk_level="medium",
                description="Notch 渲染器的着色器编译缓存和 Field 模拟缓存。与 Disguise 集成时可能占用数十 GB。",
                cleaning_note="⚠ 删除后 Notch 场景首次加载需重新编译着色器。"
            ),
            ScanItem(
                id="notch_builder_cache", label="Notch Builder 预览缓存",
                path=os.path.join(roaming, "Notch"),
                category="VP & Broadcast Extended", risk_level="safe",
                description="Notch Builder 的场景预览缓存和编译临时文件。",
                cleaning_note="安全。重新打开场景时会自动重建。"
            ),
            ScanItem(
                id="omniverse_cache", label="NVIDIA Omniverse 缓存",
                path=os.path.join(local, "NVIDIA Corporation", "Omniverse"),
                category="VP & Broadcast Extended", risk_level="medium",
                description="NVIDIA Omniverse 的 USD 资产缓存、PhysX 仿真缓存和 RTX 光追缓存。VP/CG 工作站常见数 GB。",
                cleaning_note="⚠ 删除后已下载的 Omniverse 资产需重新下载。"
            ),
            ScanItem(
                id="mosys_tracker", label="Mo-Sys StarTracker 缓存",
                path=os.path.join(local, "Mo-Sys"),
                category="VP & Broadcast Extended", risk_level="safe",
                description="Mo-Sys StarTracker 摄像机追踪系统的校准和日志文件。LED Wall VP 现场常用。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="sensapex_cache", label="Sensapex 控制器缓存",
                path=os.path.join(local, "Sensapex"),
                category="VP & Broadcast Extended", risk_level="safe",
                description="Sensapex 电动云台控制器的追踪缓存和配置文件。",
                cleaning_note="安全清理。"
            ),

            # ================================================================
            #  十七、多媒体工具 (Multimedia Tools)
            # ================================================================
            ScanItem(
                id="vlc_cache", label="VLC 媒体播放器缓存",
                path=os.path.join(roaming, "vlc"),
                category="Multimedia Tools", risk_level="safe",
                description="VLC 视频播放器的解码缓存、字幕缓存和媒体数据库。",
                cleaning_note="安全。重新播放时自动重建。"
            ),
            ScanItem(
                id="adobe_reader_cache", label="Adobe Reader 缓存",
                path=os.path.join(roaming, "Adobe", "Acrobat"),
                category="Multimedia Tools", risk_level="safe",
                description="Adobe Acrobat Reader 的临时文件、收藏夹和最近文档列表。",
                cleaning_note="安全清理。"
            ),
            ScanItem(
                id="libreoffice_cache", label="LibreOffice 缓存",
                path=os.path.join(roaming, "LibreOffice"),
                category="Multimedia Tools", risk_level="safe",
                description="LibreOffice 开源办公套件的临时文件、缓存和最近使用列表。",
                cleaning_note="安全清理。"
            ),
        ]

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
                        )
                        expanded.append(expanded_item)
                # 如果通配符没有匹配到任何路径，也保留原始项（扫描时显示不存在）
                elif not resolved:
                    expanded.append(t)
            else:
                expanded.append(t)

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

    def scan_all(self) -> List[ScanItem]:
        """执行全部扫描"""
        targets = self.get_scan_targets()
        total = len(targets)
        self.results = []

        for i, item in enumerate(targets):
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

    def __init__(self, log_callback=None):
        self._log = log_callback or (lambda msg: None)
        self._cleaned_items = []

    def clean_item(self, item: ScanItem) -> Tuple[bool, int]:
        """
        清理单个项目
        返回: (是否成功, 释放的字节数)
        """
        # 只读项不允许清理
        if item.readonly:
            self._log(f"跳过 (只读/禁止清理): {item.label}")
            return False, 0

        if not item.exists or item.size_bytes == 0:
            self._log(f"跳过 (不存在或为空): {item.label}")
            return True, 0

        try:
            path = item.path
            freed = 0

            if os.path.isfile(path):
                freed = os.path.getsize(path)
                os.remove(path)
                self._log(f"已删除文件: {path}")
            elif os.path.isdir(path):
                freed = item.size_bytes
                # 使用系统 API 移到回收站
                self._delete_to_recycle_bin(path)
                self._log(f"已移至回收站: {path}")

            self._cleaned_items.append({
                "label": item.label,
                "path": path,
                "freed_bytes": freed,
                "freed_str": ScanEngine._format_size(freed)
            })
            return True, freed

        except Exception as e:
            self._log(f"清理失败 [{item.label}]: {e}")
            return False, 0

    @staticmethod
    def _delete_to_recycle_bin(path: str):
        """使用 Windows Shell API 将文件/文件夹移到回收站"""
        try:
            from ctypes import windll
            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x40
            FOF_NOCONFIRMATION = 0x10
            FOF_SILENT = 0x4
            flags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT

            path_ptr = ctypes.c_wchar_p(path)
            null_ptr = ctypes.c_wchar_p(None)

            result = windll.shell32.SHFileOperationW(
                0, FO_DELETE, path_ptr, null_ptr, flags, None, None
            )
            if result != 0:
                # 如果回收站失败，尝试直接删除
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path, ignore_errors=True)
        except Exception:
            # fallback
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path, ignore_errors=True)


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
