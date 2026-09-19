# -*- coding: utf-8 -*-
"""
SysClean GUI - Main Interface
Windows System Junk File Scanner & Cleaner
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import subprocess
import os
import sys
import traceback
import webbrowser
from datetime import datetime
from typing import Optional

from scanner import (
    ScanEngine, ScanItem, CleanEngine, ReportGenerator, default_cleanup_log_path,
    load_database_rules,
)
from winapp2_parser import load_winapp2
from settings import AppSettings

# ============================================================
#  Color Theme - Matching Tilta Encoder dark-blue style
# ============================================================

class Theme:
    """Deep blue-black color scheme, consistent with AboutDEPT tools."""
    # Backgrounds
    BG_BASE      = "#0b1220"   # main background
    BG_CARD      = "#121a2b"   # card / panel background
    BG_INPUT     = "#0f1626"   # input fields, troughs
    BG_HOVER     = "#1a2947"   # hover state
    BG_BTN       = "#1a2947"   # default button
    BG_BTN_HOVER = "#1f3155"   # button hover
    BG_DISABLED  = "#0f1626"   # disabled bg

    # Borders
    BORDER       = "#1f2a44"
    BORDER_INPUT = "#2a3553"
    BORDER_STRONG = "#3b4b71"

    # Foreground
    FG_PRIMARY   = "#e5e7eb"
    FG_SECONDARY = "#a0aec0"
    FG_DIM       = "#4a5568"
    FG_WHITE     = "#ffffff"

    # Accents
    ACCENT_BLUE    = "#3182ce"
    ACCENT_BADGE   = "#c3dafe"
    ACCENT_GREEN   = "#68d391"
    ACCENT_RED     = "#f56565"
    ACCENT_YELLOW  = "#ecc94b"
    ACCENT_ORANGE  = "#ed8936"

    # Treeview row tags
    TAG_SAFE      = "#68d391"
    TAG_MEDIUM    = "#ecc94b"
    TAG_CAUTION   = "#f56565"
    TAG_READONLY  = "#718096"
    TAG_NOT_FOUND = "#4a5568"
    TAG_CATEGORY  = "#a0aec0"


# ============================================================
#  固定高度确认对话框（内容超出滚动）
# ============================================================

class ConfirmDialog:
    """清理确认框。

    替代 messagebox.askyesno —— 后者在待清理项很多时会把对话框撑到超出屏幕高度，
    确认按钮被推到屏幕外。这里改为固定尺寸 + 列表区滚动条：
      * 整体高度恒定（默认 520px，列表区 16 行）；
      * 内容超出时右侧纵向滚动条（路径过长时底部横向滚动条）；
      * 危险项顶部红色警示条，确认按钮用 Danger 样式。
    """

    WIDTH = 680
    HEIGHT = 520
    LIST_ROWS = 14

    def __init__(self, parent, title: str, summary: str, items,
                 danger: bool = False, caution: bool = False,
                 confirm_text: str = "确认清理"):
        """
        items: [(icon, name, size_str, path), ...]
        """
        self.parent = parent
        self.items = list(items)
        self.danger = danger
        self.result = False

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.configure(bg=Theme.BG_BASE)
        self.win.minsize(520, 380)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self.win.bind("<Escape>", lambda e: self._cancel())
        self.win.bind("<Return>", lambda e: self._ok())

        pad = dict(padx=16, pady=(12, 0))
        ttk.Label(self.win, text=title, style="Title.TLabel").pack(anchor="w", **pad)

        if danger:
            warn = tk.Label(self.win, text="⚠ 包含高风险项目（caution），确认前请逐项核对。",
                            bg="#3b1418", fg=Theme.ACCENT_RED,
                            font=("system-ui", 10, "bold"), padx=12, pady=8, anchor="w")
            warn.pack(fill="x", padx=16, pady=(10, 0))
        elif caution:
            warn = tk.Label(self.win, text="包含中风险项目（medium）。",
                            bg="#3b2f10", fg=Theme.ACCENT_YELLOW,
                            font=("system-ui", 10), padx=12, pady=8, anchor="w")
            warn.pack(fill="x", padx=16, pady=(10, 0))

        ttk.Label(self.win, text=summary, style="Subtitle.TLabel",
                  wraplength=self.WIDTH - 40, justify="left").pack(anchor="w", **pad)

        # ---- 列表区（固定高度 + 滚动条）----
        list_frame = tk.Frame(self.win, bg=Theme.BG_CARD,
                              highlightbackground=Theme.BORDER, highlightthickness=1)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(10, 0))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.text = tk.Text(
            list_frame, height=self.LIST_ROWS, wrap="none",
            bg=Theme.BG_INPUT, fg=Theme.FG_PRIMARY,
            font=("Consolas", 10), relief="flat",
            padx=12, pady=10, spacing1=2, spacing3=2,
            insertbackground=Theme.FG_PRIMARY,
            selectbackground=Theme.ACCENT_BLUE, selectforeground=Theme.FG_WHITE,
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        ysb = ttk.Scrollbar(list_frame, orient="vertical", command=self.text.yview,
                            style="Dark.Vertical.TScrollbar")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.text.xview)
        xsb.grid(row=1, column=0, sticky="ew")
        self.text.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.text.tag_configure("name", foreground=Theme.FG_PRIMARY)
        self.text.tag_configure("size", foreground=Theme.ACCENT_BADGE)
        self.text.tag_configure("path", foreground=Theme.FG_DIM)
        self.text.tag_configure("danger", foreground=Theme.ACCENT_RED)
        self._fill()

        self.text.configure(state="disabled")
        self.text.see("1.0")

        # ---- 底部按钮 ----
        btn = ttk.Frame(self.win, style="Base.TFrame")
        btn.pack(fill="x", padx=16, pady=12)
        ttk.Button(btn, text="  取消", style="Secondary.TButton",
                   command=self._cancel).pack(side="right")
        style = "Danger.TButton" if danger else "Primary.TButton"
        ttk.Button(btn, text=f"  {confirm_text}", style=style,
                   command=self._ok).pack(side="right", padx=(0, 8))
        ttk.Label(btn, text=f"共 {len(self.items)} 项",
                  style="Stat.TLabel").pack(side="left")

        self._center()
        self.win.focus_force()

    def _fill(self):
        for icon, name, size_str, path in self.items:
            self.text.insert("end", f"  {icon} ", "name")
            self.text.insert("end", f"{name}", "name")
            self.text.insert("end", f"   {size_str}", "size")
            self.text.insert("end", f"\n      {path}\n", "path")

    def _center(self):
        self.win.update_idletasks()
        px = self.parent.winfo_rootx()
        py = self.parent.winfo_rooty()
        pw = self.parent.winfo_width() or self.WIDTH
        ph = self.parent.winfo_height() or self.HEIGHT
        x = px + (pw - self.WIDTH) // 2
        y = py + (ph - self.HEIGHT) // 2
        # 保证不超出屏幕
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = max(0, min(x, sw - self.WIDTH))
        y = max(0, min(y, sh - self.HEIGHT))
        self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def _ok(self):
        self.result = True
        self.win.destroy()

    def _cancel(self):
        self.result = False
        self.win.destroy()

    def show(self) -> bool:
        self.win.wait_window()
        return self.result


# ============================================================
#  Main Application
# ============================================================

class SysCleanApp:
    """SysClean main application"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SysClean - Windows System Junk Scanner & Cleaner")
        self.root.geometry("1150x740")
        self.root.minsize(960, 620)
        self.root.configure(bg=Theme.BG_BASE)

        # BUGFIX: tkinter 回调异常默认只打到 stderr。用 pythonw / 打包 exe 启动时
        # 没有控制台，异常被彻底吞掉，表现为「点了没反应」。这里统一兜底：
        # 写日志面板 + 弹错误框（含 traceback），保证失败可见。
        self.root.report_callback_exception = self._on_tk_error

        # Load application icon
        self._load_icon()

        # DPI awareness
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # Settings (persistence)
        self.settings = AppSettings()
        self.settings.load()
        self.hide_not_installed = self.settings.hide_not_installed
        self.id_map = {}          # tree iid -> ScanItem
        self._cleaned_ids = []    # 最近一次清理的 item id 列表
        self._current_excludes = []  # 当前扫描得到的排除规则（winapp2 + 全局）

        # Apply saved window size (size part only; position recentered below)
        try:
            size_part = self.settings.window_size.split("+")[0]
            if size_part and "x" in size_part:
                self.root.geometry(size_part)
        except Exception:
            pass

        # State
        self.scan_engine = ScanEngine()
        self.clean_engine = None
        self.results: list = []
        self.is_scanning = False
        self.is_cleaning = False
        self.cleaned_items = []

        # Close handler: persist selection + window size
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Build UI
        self._setup_styles()
        self._build_ui()

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f"+{x}+{y}")

    # ================================================
    #  Icon
    # ================================================

    def _load_icon(self):
        """Load icon.ico for window title bar and taskbar.

        Works in dev / PyInstaller onefile / Nuitka onefile modes:
        - Dev:            icon.ico 在 app_paths.project_dir()
        - onefile:        icon.ico 在 app_paths.bundle_dir()（_MEIPASS）
        - 便携覆盖:        exe 旁的 icon.ico 优先
        """
        candidates = []
        try:
            from app_paths import bundle_dir, exe_dir
            candidates.append(os.path.join(exe_dir(), "icon.ico"))
            candidates.append(os.path.join(bundle_dir(), "icon.ico"))
        except Exception:
            pass
        try:
            base = os.path.dirname(os.path.abspath(sys.modules["__main__"].__file__))
            candidates.append(os.path.join(base, "icon.ico"))
        except Exception:
            pass
        candidates.append(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"))

        icon_path = None
        for p in candidates:
            if p and os.path.isfile(p):
                icon_path = p
                break
        if icon_path:
            try:
                self.root.iconbitmap(icon_path)
                # Also set taskbar icon via WM_SETICON
                from ctypes import windll, c_int
                hicon = windll.user32.LoadImageW(
                    None, icon_path, 1,  # IMAGE_ICON = 1
                    0, 0, 0x00008000  # LR_LOADFROMFILE
                )
                if hicon:
                    windll.user32.SendMessageW(
                        int(self.root.frame(), 16),
                        0x0080, 1, hicon)  # WM_SETICON, ICON_LARGE
                    windll.user32.SendMessageW(
                        int(self.root.frame(), 16),
                        0x0080, 0, hicon)  # WM_SETICON, ICON_SMALL
            except Exception:
                pass

    # ================================================
    #  Styles
    # ================================================

    def _setup_styles(self):
        """Configure ttk styles matching Tilta dark-blue theme."""
        style = ttk.Style()
        style.theme_use("clam")

        # -- Global --
        style.configure(".", background=Theme.BG_BASE, foreground=Theme.FG_PRIMARY,
                        borderwidth=0, focusthickness=0)

        # -- Frames --
        style.configure("Card.TFrame",    background=Theme.BG_CARD)
        style.configure("Base.TFrame",    background=Theme.BG_BASE)

        # -- Labels --
        style.configure("Title.TLabel",    background=Theme.BG_BASE,
                        foreground=Theme.FG_PRIMARY,
                        font=("system-ui", 18, "bold"))
        style.configure("Subtitle.TLabel", background=Theme.BG_BASE,
                        foreground=Theme.FG_SECONDARY,
                        font=("system-ui", 10))
        style.configure("Card.TLabel",     background=Theme.BG_CARD,
                        foreground=Theme.FG_PRIMARY, font=("system-ui", 10))
        style.configure("CardBold.TLabel", background=Theme.BG_CARD,
                        foreground=Theme.FG_PRIMARY, font=("system-ui", 11, "bold"))
        style.configure("Stat.TLabel",     background=Theme.BG_CARD,
                        foreground=Theme.FG_SECONDARY, font=("system-ui", 9))
        style.configure("StatValue.TLabel", background=Theme.BG_CARD,
                        foreground=Theme.ACCENT_BADGE, font=("system-ui", 22, "bold"))
        style.configure("Muted.TLabel",    background=Theme.BG_CARD,
                        foreground=Theme.FG_SECONDARY, font=("system-ui", 12))

        # -- Primary Button (blue accent) --
        style.configure("Primary.TButton",
                        background="#2c5282", foreground=Theme.FG_WHITE,
                        font=("system-ui", 11, "bold"), padding=(20, 10),
                        borderwidth=0)
        style.map("Primary.TButton",
                  background=[("active", "#3182ce"), ("disabled", Theme.BG_DISABLED)],
                  foreground=[("disabled", Theme.FG_DIM)])

        # -- Danger Button (red) --
        style.configure("Danger.TButton",
                        background="#c53030", foreground=Theme.FG_WHITE,
                        font=("system-ui", 11, "bold"), padding=(20, 10),
                        borderwidth=0)
        style.map("Danger.TButton",
                  background=[("active", "#e53e3e"), ("disabled", Theme.BG_DISABLED)],
                  foreground=[("disabled", Theme.FG_DIM)])

        # -- Secondary Button --
        style.configure("Secondary.TButton",
                        background=Theme.BG_BTN, foreground=Theme.FG_PRIMARY,
                        font=("system-ui", 10), padding=(15, 8), borderwidth=0)
        style.map("Secondary.TButton",
                  background=[("active", Theme.BG_BTN_HOVER), ("disabled", Theme.BG_DISABLED)],
                  foreground=[("disabled", Theme.FG_DIM)])

        # -- Progressbar --
        style.configure("Scan.Horizontal.TProgressbar",
                        troughcolor=Theme.BG_INPUT, background=Theme.ACCENT_BLUE,
                        thickness=6, borderwidth=0)

        # -- Treeview --
        style.configure("Clean.Treeview",
                        background=Theme.BG_CARD, foreground=Theme.FG_PRIMARY,
                        fieldbackground=Theme.BG_CARD, borderwidth=0,
                        font=("system-ui", 10), rowheight=34)
        style.configure("Clean.Treeview.Heading",
                        background=Theme.BG_INPUT, foreground=Theme.ACCENT_BADGE,
                        font=("system-ui", 10, "bold"), padding=(12, 6),
                        borderwidth=0, relief="flat")
        style.map("Clean.Treeview",
                  background=[("selected", Theme.BG_HOVER)],
                  foreground=[("selected", Theme.FG_WHITE)])

        # -- Scrollbar --
        style.configure("Dark.Vertical.TScrollbar",
                        background=Theme.BORDER_INPUT, troughcolor=Theme.BG_BASE,
                        arrowcolor=Theme.FG_DIM, borderwidth=0)
        style.map("Dark.Vertical.TScrollbar",
                  background=[("active", Theme.BORDER_STRONG)])

    # ================================================
    #  Build UI
    # ================================================

    def _build_ui(self):
        main = ttk.Frame(self.root, style="Base.TFrame")
        main.pack(fill="both", expand=True, padx=20, pady=14)

        self._build_header(main)
        self._build_stats(main)
        self._build_progress(main)
        self._build_content(main)
        self._build_footer(main)
        self._build_log(main)

    def _build_header(self, parent):
        header = ttk.Frame(parent, style="Base.TFrame")
        header.pack(fill="x", pady=(0, 14))

        ttk.Label(header, text="SysClean", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  Windows System Junk Scanner & Cleaner",
                  style="Subtitle.TLabel").pack(side="left", padx=(10, 0))

        # Right: settings button + toggles
        ttk.Button(
            header, text="⚙ 设置", style="Secondary.TButton",
            command=self._open_options_dialog,
        ).pack(side="right", padx=(8, 0))

        # winapp2 数据库开关
        self.wa_var = tk.BooleanVar(value=self.settings.enable_winapp2)
        self.wa_chk = ttk.Checkbutton(
            header, text="winapp2 数据库",
            variable=self.wa_var,
            command=self._toggle_winapp2,
        )
        self.wa_chk.pack(side="right", padx=(8, 0))

        # toggle "only show installed apps"
        self.hide_var = tk.BooleanVar(value=self.hide_not_installed)
        self.hide_chk = ttk.Checkbutton(
            header, text="仅显示已安装软件",
            variable=self.hide_var,
            command=self._toggle_hide,
        )
        self.hide_chk.pack(side="right")

    def _toggle_hide(self):
        """切换：仅显示已安装软件（隐藏未安装且无内容的项）。"""
        self.hide_not_installed = self.hide_var.get()
        self.settings.hide_not_installed = self.hide_not_installed
        self.settings.save()
        if self.results:
            self._populate_tree()

    def _toggle_winapp2(self):
        """切换：启用/停用 winapp2 社区数据库。需重新扫描生效。"""
        self.settings.enable_winapp2 = self.wa_var.get()
        self.settings.save()
        self._append_log(
            f"winapp2 数据库已{'启用' if self.wa_var.get() else '停用'}"
            f"（下次扫描生效）。", "info")

    def _open_options_dialog(self):
        """设置对话框：winapp2 数据库开关 + 全局排除列表。"""
        dlg = tk.Toplevel(self.root)
        dlg.title("SysClean 设置")
        dlg.configure(bg=Theme.BG_BASE)
        dlg.minsize(520, 360)
        dlg.transient(self.root)
        dlg.grab_set()

        # winapp2 开关
        wa_var = tk.BooleanVar(value=self.settings.enable_winapp2)
        db_var = tk.BooleanVar(value=self.settings.enable_databases)
        wa_frame = tk.Frame(dlg, bg=Theme.BG_CARD,
                            highlightbackground=Theme.BORDER, highlightthickness=1,
                            padx=14, pady=10)
        wa_frame.pack(fill="x", padx=16, pady=(16, 8))
        ttk.Checkbutton(wa_frame, text="启用 winapp2 社区数据库（覆盖数千款通用 App）",
                        variable=wa_var).pack(anchor="w")
        ttk.Label(wa_frame,
                  text=f"数据库文件：{self.settings.winapp2_path}",
                  style="Stat.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(wa_frame,
                        text="启用 CG / AIGC 规则数据库（Databases/*.ini）",
                        variable=db_var).pack(anchor="w", pady=(8, 0))
        ttk.Label(wa_frame,
                  text="含 Unreal/Unity/Maya/3dsMax/Houdini/Nuke/Resolve/Adobe/"
                       "TouchDesigner/ComfyUI/Gradio/HuggingFace 等缓存规则",
                  style="Stat.TLabel").pack(anchor="w", pady=(2, 0))

        # 全局排除
        ex_frame = tk.Frame(dlg, bg=Theme.BG_CARD,
                            highlightbackground=Theme.BORDER, highlightthickness=1,
                            padx=14, pady=10)
        ex_frame.pack(fill="both", expand=True, padx=16, pady=(8, 8))
        ttk.Label(ex_frame, text="全局排除（每行一条路径；清理时这些路径下的文件一律保留）",
                  style="CardBold.TLabel").pack(anchor="w")
        ex_text = tk.Text(ex_frame, height=8, wrap="word",
                          bg=Theme.BG_INPUT, fg=Theme.FG_PRIMARY,
                          font=("Consolas", 9), relief="flat",
                          insertbackground=Theme.FG_PRIMARY,
                          selectbackground=Theme.ACCENT_BLUE,
                          selectforeground=Theme.FG_WHITE,
                          padx=10, pady=8)
        ex_text.pack(fill="both", expand=True, pady=(8, 0))
        ex_text.insert("1.0", "\n".join(self.settings.global_exclusions))

        # 按钮
        btn_frame = ttk.Frame(dlg, style="Base.TFrame")
        btn_frame.pack(fill="x", padx=16, pady=(4, 16))

        def _save():
            lines = [ln.strip() for ln in ex_text.get("1.0", "end").splitlines()]
            self.settings.global_exclusions = [ln for ln in lines if ln]
            self.settings.enable_winapp2 = wa_var.get()
            self.settings.enable_databases = db_var.get()
            self.wa_var.set(wa_var.get())
            self.settings.save()
            self._append_log("设置已保存（下次扫描生效）。", "success")
            dlg.destroy()

        ttk.Button(btn_frame, text="  保存", style="Primary.TButton",
                   command=_save).pack(side="right", padx=(8, 0))
        ttk.Button(btn_frame, text="  取消", style="Secondary.TButton",
                   command=dlg.destroy).pack(side="right")

    def _build_stats(self, parent):
        stats_frame = ttk.Frame(parent, style="Base.TFrame")
        stats_frame.pack(fill="x", pady=(0, 10))

        cards = [
            ("Reclaimable", "0 GB",   "stat_total"),
            ("Scan Items",   "0",      "stat_count"),
            ("Total Files",  "0",      "stat_files"),
            ("Freed Space",  "0 GB",   "stat_freed"),
        ]

        for title, default, attr in cards:
            card = tk.Frame(stats_frame, bg=Theme.BG_CARD,
                            highlightbackground=Theme.BORDER, highlightthickness=1,
                            padx=16, pady=10)
            card.pack(side="left", fill="both", expand=True, padx=(0, 8))
            card.pack_propagate(False)

            lbl = ttk.Label(card, text=default, style="StatValue.TLabel")
            lbl.pack(anchor="w")
            ttk.Label(card, text=title, style="Stat.TLabel").pack(anchor="w")
            setattr(self, attr, lbl)

        # fix last padding
        for child in stats_frame.winfo_children():
            child.pack_configure(padx=(0, 0))

    def _build_progress(self, parent):
        prog_frame = ttk.Frame(parent, style="Base.TFrame")
        prog_frame.pack(fill="x", pady=(0, 10))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(
            prog_frame, variable=self.progress_var, maximum=100,
            style="Scan.Horizontal.TProgressbar"
        )
        self.progress.pack(fill="x", side="left", expand=True)

        self.progress_label = ttk.Label(
            prog_frame, text="Ready", style="Muted.TLabel", width=32
        )
        self.progress_label.pack(side="right", padx=(12, 0))

    def _build_content(self, parent):
        content = ttk.Frame(parent, style="Base.TFrame")
        content.pack(fill="both", expand=True, pady=(0, 10))

        # Left: Treeview
        left = ttk.Frame(content, style="Base.TFrame")
        left.pack(side="left", fill="both", expand=True)

        columns = ("size", "files", "risk", "category", "path")
        self.tree = ttk.Treeview(
            left, columns=columns, show="tree headings",
            style="Clean.Treeview", selectmode="browse", height=14
        )

        self.tree.heading("#0",       text="  Item",      anchor="w")
        self.tree.heading("size",     text="  Size",      anchor="e")
        self.tree.heading("files",    text="  Files",     anchor="e")
        self.tree.heading("risk",     text="  Risk",      anchor="center")
        self.tree.heading("category", text="  Category",  anchor="w")
        self.tree.heading("path",     text="  Path",      anchor="w")

        self.tree.column("#0",       width=290, minwidth=200, anchor="w")
        self.tree.column("size",     width=100, minwidth=80,  anchor="e")
        self.tree.column("files",    width=80,  minwidth=60,  anchor="e")
        self.tree.column("risk",     width=90,  minwidth=70,  anchor="center")
        self.tree.column("category", width=120, minwidth=90,  anchor="w")
        self.tree.column("path",     width=260, minwidth=150, anchor="w")

        # Tag colors
        self.tree.tag_configure("safe",       foreground=Theme.TAG_SAFE)
        self.tree.tag_configure("medium",     foreground=Theme.TAG_MEDIUM)
        self.tree.tag_configure("caution",    foreground=Theme.TAG_CAUTION)
        self.tree.tag_configure("readonly",   foreground=Theme.TAG_READONLY)
        self.tree.tag_configure("not_found",  foreground=Theme.TAG_NOT_FOUND)
        self.tree.tag_configure("category",   foreground=Theme.TAG_CATEGORY,
                                font=("system-ui", 10, "bold"))

        # Events
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>",          self._on_double_click)
        self.tree.bind("<Button-3>",          self._on_right_click)

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview,
                           style="Dark.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Right: Detail panel
        self._build_detail_panel(content)

    def _build_detail_panel(self, parent):
        self.detail_frame = tk.Frame(
            parent, bg=Theme.BG_CARD, width=310,
            highlightbackground=Theme.BORDER, highlightthickness=1
        )
        self.detail_frame.pack(side="right", fill="y", padx=(10, 0))
        self.detail_frame.pack_propagate(False)

        ttk.Label(self.detail_frame, text="  Item Details",
                  style="CardBold.TLabel").pack(padx=12, pady=(12, 6), anchor="w")

        sep = tk.Frame(self.detail_frame, bg=Theme.BORDER, height=1)
        sep.pack(fill="x", padx=12, pady=(0, 6))

        self.detail_text = tk.Text(
            self.detail_frame, wrap="word", state="disabled",
            bg=Theme.BG_CARD, fg=Theme.FG_SECONDARY,
            font=("system-ui", 9), relief="flat",
            insertbackground=Theme.FG_PRIMARY,
            selectbackground=Theme.ACCENT_BLUE, selectforeground=Theme.FG_WHITE,
            padx=12, pady=8, spacing1=2, spacing3=4,
        )
        self.detail_text.pack(fill="both", expand=True)

        # Text tags
        self.detail_text.tag_configure("title",     foreground=Theme.FG_PRIMARY,
                                       font=("system-ui", 12, "bold"))
        self.detail_text.tag_configure("key",       foreground=Theme.ACCENT_BADGE,
                                       font=("system-ui", 10, "bold"))
        self.detail_text.tag_configure("value",     foreground=Theme.FG_PRIMARY)
        self.detail_text.tag_configure("warn",      foreground=Theme.ACCENT_RED)
        self.detail_text.tag_configure("dim",       foreground=Theme.FG_DIM)
        self.detail_text.tag_configure("note",      foreground=Theme.ACCENT_ORANGE)
        self.detail_text.tag_configure("subitem",   foreground=Theme.FG_SECONDARY,
                                       font=("Consolas", 9))
        self.detail_text.tag_configure("subheader", foreground=Theme.ACCENT_BADGE,
                                       font=("system-ui", 10, "bold"))

        # Context menu
        self.context_menu = tk.Menu(
            self.root, tearoff=0,
            bg=Theme.BG_CARD, fg=Theme.FG_PRIMARY,
            activebackground=Theme.BG_HOVER, activeforeground=Theme.FG_WHITE,
            font=("system-ui", 10), borderwidth=1,
            relief="flat", bd=0,
        )
        self.context_menu.add_command(label="  Open in Explorer",
                                     command=self._open_selected_folder)
        self.context_menu.add_command(label="  Copy Path",
                                     command=self._copy_selected_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="  Clean This Item",
                                     command=self._clean_selected)

    def _build_footer(self, parent):
        footer = ttk.Frame(parent, style="Base.TFrame")
        footer.pack(fill="x", pady=(0, 10))

        self.scan_btn = ttk.Button(
            footer, text="  Start Scan", style="Primary.TButton",
            command=self._start_scan
        )
        self.scan_btn.pack(side="left", padx=(0, 8))

        self.clean_btn = ttk.Button(
            footer, text="  Clean Selected", style="Danger.TButton",
            command=self._start_clean, state="disabled"
        )
        self.clean_btn.pack(side="left", padx=(0, 8))

        ttk.Button(
            footer, text="  Select All Safe Items", style="Secondary.TButton",
            command=self._select_safe
        ).pack(side="right", padx=(8, 0))

        ttk.Button(
            footer, text="  Export Report", style="Secondary.TButton",
            command=self._export_report, state="disabled"
        ).pack(side="right", padx=(0, 0))

    def _build_log(self, parent):
        log_frame = tk.Frame(parent, bg=Theme.BG_CARD,
                             highlightbackground=Theme.BORDER, highlightthickness=1)
        log_frame.pack(fill="x", pady=(0, 0))

        ttk.Label(log_frame, text="  Activity Log",
                  style="Stat.TLabel").pack(padx=12, pady=(8, 4), anchor="w")

        self.log_text = tk.Text(
            log_frame, height=4, wrap="word", state="disabled",
            bg=Theme.BG_CARD, fg=Theme.FG_DIM,
            font=("Consolas", 9), relief="flat",
            insertbackground=Theme.FG_DIM,
            padx=12, pady=4,
        )
        self.log_text.pack(fill="x", padx=4, pady=(0, 8))

        self.log_text.tag_configure("info",    foreground=Theme.FG_SECONDARY)
        self.log_text.tag_configure("success", foreground=Theme.ACCENT_GREEN)
        self.log_text.tag_configure("warn",    foreground=Theme.ACCENT_YELLOW)
        self.log_text.tag_configure("error",   foreground=Theme.ACCENT_RED)

    # ================================================
    #  Logging
    # ================================================

    def _append_log(self, msg: str, tag: str = "info"):
        def _do():
            self.log_text.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, _do)

    def _on_tk_error(self, exc, val, tb):
        """tkinter 回调异常兜底：无控制台启动时异常会被吞掉，这里强制可见。"""
        text = "".join(traceback.format_exception(exc, val, tb))
        try:
            self._append_log(f"内部错误: {val}", "error")
        except Exception:
            pass
        try:
            messagebox.showerror(
                "SysClean 内部错误",
                f"操作未能完成：\n\n{val}\n\n"
                f"详细信息已写入日志面板。\n\n{text[-1200:]}"
            )
        except Exception:
            pass
        # 清理/扫描进行中发生异常时，恢复按钮状态，避免界面卡死
        try:
            self.is_scanning = False
            self.is_cleaning = False
            self.scan_btn.configure(state="normal")
            self.clean_btn.configure(state="normal")
            self.progress_label.configure(text="Error")
        except Exception:
            pass

    # ================================================
    #  Scan
    # ================================================

    def _start_scan(self):
        if self.is_scanning or self.is_cleaning:
            return

        self.is_scanning = True
        self.scan_btn.configure(state="disabled")
        self.clean_btn.configure(state="disabled")
        self.progress_var.set(0)
        self.progress_label.configure(text="Scanning...")
        self._clear_tree()
        self._append_log("Starting C: drive junk file scan...", "info")

        self.scan_engine.set_callbacks(
            progress_cb=self._on_scan_progress,
            log_cb=lambda msg: self._append_log(msg, "info")
        )
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        try:
            # 迭代2：加载 winapp2 社区数据库（按设置启用）
            winapp2_items, winapp2_excludes = load_winapp2(
                self.settings.winapp2_path, self.settings.enable_winapp2)
            if self.settings.enable_winapp2:
                self._append_log(
                    f"winapp2 数据库：{len(winapp2_items)} 条已安装 App 条目"
                    f"（来自 {os.path.basename(self.settings.winapp2_path)}）。", "info")
            # 规则数据库（Databases/*.ini）
            db_items = load_database_rules() if self.settings.enable_databases else []
            if self.settings.enable_databases:
                self._append_log(f"规则数据库：{len(db_items)} 条（CG/VP/AIGC + 系统补充）。",
                                 "info")
            self.results = self.scan_engine.scan_all(
                winapp2_items=winapp2_items,
                winapp2_excludes=winapp2_excludes,
                global_excludes=self.settings.global_exclusions,
                db_items=db_items,
            )
            # 清理引擎使用的排除规则（已由 scan_all 规范化为 (type, value) 元组）
            self._current_excludes = list(self.scan_engine.exclude_rules)
            self.root.after(0, self._on_scan_complete)
        except Exception as e:
            self._append_log(f"Scan error: {e}", "error")
            self.root.after(0, self._on_scan_error)

    def _on_scan_progress(self, current: int, total: int):
        def _do():
            pct = (current / total) * 100
            self.progress_var.set(pct)
            self.progress_label.configure(
                text=f"Scanning {current}/{total} ({pct:.0f}%)"
            )
        self.root.after(0, _do)

    def _on_scan_complete(self):
        self.is_scanning = False
        self.scan_btn.configure(state="normal")
        self.clean_btn.configure(state="normal")
        self.progress_var.set(100)
        self.progress_label.configure(text="Scan Complete")

        self._populate_tree()
        self._update_stats()

        total_size = sum(r.size_bytes for r in self.results if r.exists and r.size_bytes > 0)
        self._append_log(
            f"Scan complete! Found {ScanEngine._format_size(total_size)} reclaimable.",
            "success"
        )

    def _on_scan_error(self):
        self.is_scanning = False
        self.scan_btn.configure(state="normal")
        self.progress_label.configure(text="Scan Failed")

    # ================================================
    #  Treeview
    # ================================================

    def _clear_tree(self):
        self.tree.delete(*self.tree.get_children())

    @staticmethod
    def _visible_items(results, hide_not_installed: bool):
        """应用隐藏规则，返回可见项（BUGFIX B3 抽出，便于单测）。"""
        visible = []
        for item in results:
            if hide_not_installed:
                if not item.installed:
                    # 未安装且未找到内容 → 隐藏（消灭噪音）
                    if not item.exists or item.size_bytes == 0:
                        continue
                elif item.source in ("winapp2", "db") and (
                        not item.exists or item.size_bytes == 0):
                    # winapp2 / 规则数据库：命中检测但未实际产生缓存 → 同样隐藏
                    continue
            visible.append(item)
        return visible

    @staticmethod
    def _group_by_category(items):
        """按分类聚合成 [(category, [item, ...]), ...]。

        BUGFIX B3: scan_all 是按 size 全局降序排序的，原先靠「相邻项分类不同就插入
        一个分类标题」来分组，会导致同一分类在树里重复出现 N 次标题。
        这里改为先聚合再渲染，分类顺序 = 该分类首个（最大）项的出现顺序。
        """
        groups = {}
        order = []
        for item in items:
            cat = item.category
            if cat not in groups:
                groups[cat] = []
                order.append(cat)
            groups[cat].append(item)
        return [(c, groups[c]) for c in order]

    def _populate_tree(self):
        self._clear_tree()
        self.id_map = {}
        saved = set(self.settings.selected_ids)

        visible = self._visible_items(self.results, self.hide_not_installed)
        if not visible:
            return

        for category, items in self._group_by_category(visible):
            cat_id = self.tree.insert("", "end", text=f"  {category}",
                                      values=("", "", "", "", ""),
                                      tags=("category",), open=True)

            for item in items:
                # Determine tag
                if not item.exists or item.size_bytes == 0:
                    tag = "not_found"
                elif item.readonly:
                    tag = "readonly"
                else:
                    tag = item.risk_level

                # Determine prefix
                if item.readonly and item.exists and item.size_bytes > 0:
                    prefix = "  🔒 "
                elif item.exists and item.size_bytes > 0:
                    prefix = f"  {item.risk_icon} "
                else:
                    prefix = "  . "

                size_display = item.size_str if item.exists and item.size_bytes > 0 else "-"
                files_display = str(item.files) if item.exists else "-"

                # Risk display
                if item.readonly:
                    risk_display = "Read-Only"
                elif item.exists:
                    risk_display = item.risk_display
                else:
                    risk_display = "N/A"

                # 第 6 个值存储 item.id（不显示），用于健壮地按 id 反查
                iid = self.tree.insert(
                    cat_id, "end",
                    text=f"{prefix}{item.label}",
                    values=(
                        size_display,
                        files_display,
                        risk_display,
                        item.category,
                        item.path,
                        item.id,
                    ),
                    tags=(tag,),
                )
                self.id_map[iid] = item
                # 按保存的选择预选
                if (item.id in saved and item.exists and item.size_bytes > 0
                        and not item.readonly):
                    self.tree.selection_add(iid)

    def _on_select(self, event):
        scan_item = self._get_selected_scan_item()
        if scan_item is None:
            self._clear_detail()
            return
        self._show_detail(scan_item)

    def _get_selected_scan_item(self) -> Optional[ScanItem]:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.id_map.get(selection[0])

    def _on_double_click(self, event):
        scan_item = self._get_selected_scan_item()
        if scan_item and scan_item.exists:
            path = scan_item.path
            if os.path.isdir(path):
                subprocess.Popen(f'explorer "{path}"')
            elif os.path.isfile(path):
                subprocess.Popen(f'explorer /select,"{path}"')

    def _on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _open_selected_folder(self):
        self._on_double_click(None)

    def _copy_selected_path(self):
        scan_item = self._get_selected_scan_item()
        if scan_item:
            self.root.clipboard_clear()
            self.root.clipboard_append(scan_item.path)
            self._append_log(f"Path copied: {scan_item.path}", "info")

    def _clean_selected(self):
        scan_item = self._get_selected_scan_item()
        if scan_item is None:
            return
        if scan_item.readonly:
            messagebox.showinfo("Read-Only",
                f"This item is read-only and cannot be cleaned:\n\n"
                f"🔒 {scan_item.label}\n\n"
                f"{scan_item.cleaning_note}")
            return
        if scan_item.exists and scan_item.size_bytes > 0:
            confirm = ConfirmDialog(
                self.root,
                title="确认清理",
                summary="文件将被移入回收站（可从回收站还原）。",
                items=[(scan_item.risk_icon, scan_item.label,
                        scan_item.size_str, scan_item.path)],
                danger=(scan_item.risk_level == "caution"),
                caution=(scan_item.risk_level == "medium"),
            ).show()
            if confirm:
                self.is_cleaning = True
                self.scan_btn.configure(state="disabled")
                self.clean_btn.configure(state="disabled")
                self.progress_label.configure(text="Cleaning...")
                self.progress_var.set(50)
                self._append_log(f"Cleaning: {scan_item.label}...", "warn")
                self.clean_engine = self._make_clean_engine()

                def _do_clean():
                    freed = 0
                    err = None
                    try:
                        _s, freed = self.clean_engine.clean_item(scan_item)
                        self.cleaned_items = self.clean_engine._cleaned_items
                    except Exception as e:
                        err = e
                        self.cleaned_items = getattr(
                            self.clean_engine, "_cleaned_items", [])
                    self._finish_clean(freed, err)

                threading.Thread(target=_do_clean, daemon=True).start()

    # ================================================
    #  Detail Panel
    # ================================================

    def _clear_detail(self):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.configure(state="disabled")

    def _show_detail(self, item: ScanItem):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")

        # Title with readonly badge
        if item.readonly:
            self.detail_text.insert("end", f"🔒 {item.label}\n", "title")
            self.detail_text.insert("end", "READ-ONLY — Display Only\n\n", "warn")
        else:
            self.detail_text.insert("end", f"{item.label}\n", "title")
            self.detail_text.insert("end", "\n")

        self.detail_text.insert("end", "Path\n", "key")
        self.detail_text.insert("end", f"{item.path}\n\n", "value")

        if item.exists and item.size_bytes > 0:
            self.detail_text.insert("end", "Size\n", "key")
            self.detail_text.insert("end", f"{item.size_str}\n\n", "value")

            self.detail_text.insert("end", "Files\n", "key")
            self.detail_text.insert("end",
                f"{item.files} files, {item.folders} folders\n\n", "value")

            self.detail_text.insert("end", "Risk Level\n", "key")
            if item.readonly:
                self.detail_text.insert("end",
                    "🔒 Read-Only (Display Only)\n\n", "warn")
            else:
                self.detail_text.insert("end",
                    f"{item.risk_icon} {item.risk_display}\n\n", "value")
        else:
            self.detail_text.insert("end", "Status: ", "key")
            self.detail_text.insert("end", "Not found or empty\n\n", "dim")

        self.detail_text.insert("end", "Description\n", "key")
        self.detail_text.insert("end", f"{item.description}\n\n", "value")

        if item.cleaning_note:
            self.detail_text.insert("end", "Note\n", "key")
            self.detail_text.insert("end", f"{item.cleaning_note}\n\n", "note")

        if item.sub_items:
            self.detail_text.insert("end", "-- Top Items --\n", "subheader")
            for si in item.sub_items[:8]:
                t = "[DIR]" if si["is_dir"] else "[FILE]"
                self.detail_text.insert("end",
                    f"  {t} {si['size_str']:>10}  {si['name']}\n", "subitem")

        self.detail_text.configure(state="disabled")

    # ================================================
    #  Stats
    # ================================================

    def _update_stats(self):
        active = [r for r in self.results if r.exists and r.size_bytes > 0]
        total_bytes = sum(r.size_bytes for r in active)
        total_files = sum(r.files for r in active)

        self.stat_total.configure(
            text=f"{total_bytes / (1024**3):.2f} GB"
            if total_bytes >= 1024**3
            else f"{total_bytes / (1024**2):.1f} MB"
        )
        self.stat_count.configure(text=str(len(active)))
        self.stat_files.configure(text=f"{total_files:,}")

    # ================================================
    #  Select & Clean
    # ================================================

    def _select_safe(self):
        if not self.results:
            messagebox.showinfo("Info", "Please run a scan first.")
            return

        count = 0
        for iid, r in self.id_map.items():
            if (r.risk_level == "safe" and r.exists and r.size_bytes > 0
                    and not r.readonly and r.installed):
                self.tree.selection_add(iid)
                count += 1

        if count > 0:
            self._append_log(f"Selected {count} safe items.", "success")
        else:
            self._append_log("No safe items found.", "warn")

    def _start_clean(self):
        if not self.results:
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select items to clean from the list.")
            return

        items_to_clean = []
        for sel in selection:
            r = self.id_map.get(sel)
            if r and r.exists and r.size_bytes > 0 and not r.readonly:
                items_to_clean.append(r)

        if not items_to_clean:
            messagebox.showinfo("Info", "Selected items are read-only or not found.")
            return

        # 构建待清理明细（固定高度对话框内滚动显示，避免项多时撑爆屏幕）
        total_size = sum(i.size_bytes for i in items_to_clean)
        has_caution = any(i.risk_level == "caution" for i in items_to_clean)
        has_medium = any(i.risk_level == "medium" for i in items_to_clean)

        detail_items = [
            (i.risk_icon, i.label, i.size_str, i.path) for i in items_to_clean]
        summary = (f"即将清理 {len(items_to_clean)} 项，合计 "
                   f"{ScanEngine._format_size(total_size)}。"
                   f"文件将被移入回收站（可从回收站还原）。")
        confirm = ConfirmDialog(
            self.root,
            title="确认清理",
            summary=summary,
            items=detail_items,
            danger=has_caution,
            caution=has_medium and not has_caution,
            confirm_text="确认清理",
        ).show()
        if not confirm:
            self._append_log("已取消清理。", "info")
            return

        self.is_cleaning = True
        self.scan_btn.configure(state="disabled")
        self.clean_btn.configure(state="disabled")
        self.progress_label.configure(text="Cleaning...")
        self.progress_var.set(0)
        self._append_log(f"Cleaning {len(items_to_clean)} item(s)...", "warn")

        self.clean_engine = self._make_clean_engine()
        threading.Thread(
            target=self._clean_worker, args=(items_to_clean,), daemon=True
        ).start()

    def _make_clean_engine(self) -> CleanEngine:
        """构造带当前排除规则的清理引擎（winapp2 排除 + 用户全局排除）。
        同时写入审计日志文件（迭代3）：每次 GUI 清理同样留痕。"""
        return CleanEngine(
            log_callback=self._append_log,
            exclude_rules=self._current_excludes,
            log_file=default_cleanup_log_path(),
        )

    def _clean_worker(self, items):
        """在后台线程执行清理。任何异常都必须回到主线程收尾，
        否则界面会永久停在 Cleaning... 状态（表现为「点了没反应」）。"""
        total = len(items)
        freed_total = 0
        err = None
        try:
            for i, item in enumerate(items):
                self._append_log(f"Cleaning: {item.label}...", "info")
                success, freed = self.clean_engine.clean_item(item)
                freed_total += freed

                self.root.after(0,
                    lambda idx=i, t=total: self.progress_var.set((idx / t) * 100))

                if success:
                    self._append_log(
                        f"  OK  Released {ScanEngine._format_size(freed)}", "success")
                else:
                    self._append_log(f"  FAIL  Clean failed.", "error")

            self.cleaned_items = self.clean_engine._cleaned_items
            self._cleaned_ids = [i.id for i in items]
        except Exception as e:
            err = e
            self.cleaned_items = getattr(self.clean_engine, "_cleaned_items", [])
            self._cleaned_ids = []
        self._finish_clean(freed_total, err)

    def _finish_clean(self, freed_total, err):
        """回到主线程收尾。

        工作线程调用 root.after 时若主线程不在 mainloop 会抛
        RuntimeError('main thread is not in main loop')，异常若逃逸会让
        界面永久停在 Cleaning...（表现为「点了没反应」）。这里兜底为
        同步收尾——跨线程操作 Tk 不安全，但比界面卡死好。
        """
        try:
            self.root.after(0, lambda: self._on_clean_complete(freed_total, err))
            return
        except Exception:
            pass
        try:
            self._on_clean_complete(freed_total, err)
        except Exception:
            pass

    def _on_clean_complete(self, freed_total: int, error: Optional[Exception] = None):
        self.is_cleaning = False
        self.scan_btn.configure(state="normal")
        self.clean_btn.configure(state="normal")
        self.progress_var.set(100)

        if error is not None:
            self.progress_label.configure(text="Clean Failed")
            self._append_log(f"清理异常: {error}", "error")
            messagebox.showerror(
                "Clean Failed",
                f"清理过程发生错误：\n\n{error}\n\n"
                f"已完成 {len(self.cleaned_items or [])} 项，其余未执行。"
            )
            return

        # 迭代3：关闭审计日志（写入会话总计）
        try:
            if self.clean_engine is not None:
                self.clean_engine.finalize()
        except Exception:
            pass

        # 记住本次清理的选择，下次启动自动预选
        if self._cleaned_ids:
            self.settings.selected_ids = self._cleaned_ids
            self.settings.save()

        freed_str = ScanEngine._format_size(freed_total)
        self.progress_label.configure(text="Clean Complete")
        self.stat_freed.configure(text=freed_str)

        # BUGFIX: 清理结束后把已清理项清零并刷新列表。
        # 原先树里仍显示旧大小，用户可对同一项重复发起清理，第二次会重复写审计日志。
        cleaned_paths = {c.get("path") for c in (self.cleaned_items or [])}
        if cleaned_paths:
            for r in self.results:
                if r.path in cleaned_paths:
                    r.exists = False
                    r.size_bytes = 0
                    r.files = 0
                    r.folders = 0
                    r.sub_items = []
            self._populate_tree()
            self._update_stats()

        self._append_log(f"Clean complete! Released {freed_str}", "success")
        messagebox.showinfo("Clean Complete",
            f"Freed: {freed_str}\n\nFiles moved to Recycle Bin.")

    def _on_close(self):
        """关闭窗口时持久化选择与窗口尺寸。"""
        try:
            self.settings.selected_ids = [
                self.id_map[i].id for i in self.tree.selection() if i in self.id_map
            ]
            self.settings.window_size = self.root.geometry().split("+")[0]
            self.settings.save()
        except Exception:
            pass
        self.root.destroy()

    # ================================================
    #  Export
    # ================================================

    def _export_report(self):
        if not self.results:
            return

        filepath = filedialog.asksaveasfilename(
            title="Export Scan Report",
            defaultextension=".txt",
            filetypes=[
                ("Text Report", "*.txt"),
                ("JSON Data",   "*.json"),
                ("CSV Data",    "*.csv"),
                ("All Files",   "*.*"),
            ],
            initialfile=f"SysClean_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )
        if not filepath:
            return

        try:
            ext = os.path.splitext(filepath)[1].lower()
            if ext == ".json":
                content = ReportGenerator.generate_json_report(self.results)
                encoding = "utf-8"
            elif ext == ".csv":
                content = ReportGenerator.generate_csv_report(
                    self.results, self.cleaned_items)
                encoding = "utf-8-sig"   # Excel 中文友好
            else:
                content = ReportGenerator.generate_text_report(
                    self.results, self.cleaned_items)
                encoding = "utf-8"

            with open(filepath, "w", encoding=encoding) as f:
                f.write(content)

            self._append_log(f"Report exported: {filepath}", "success")
            messagebox.showinfo("Export Success",
                f"Report saved to:\n{filepath}")
        except Exception as e:
            self._append_log(f"Export failed: {e}", "error")
            messagebox.showerror("Export Failed", str(e))

    # ================================================
    #  Run
    # ================================================

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = SysCleanApp()
    app.run()
