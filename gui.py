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
import webbrowser
from datetime import datetime
from typing import Optional

from scanner import (
    ScanEngine, ScanItem, CleanEngine, ReportGenerator
)

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

        # Load application icon
        self._load_icon()

        # DPI awareness
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # State
        self.scan_engine = ScanEngine()
        self.clean_engine = None
        self.results: list = []
        self.is_scanning = False
        self.is_cleaning = False
        self.cleaned_items = []

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

        Works in both dev (PyCharm) and Nuitka onefile modes:
        - Dev:          __file__ = project/gui.py  →  icon.ico is one level up
        - Nuitka onefile: __file__ = temp/main.py →  icon.ico extracted alongside exe
        """
        # Use main.py's directory (sys.modules entry point) for Nuitka compat
        base = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
        icon_path = os.path.join(base, "icon.ico")
        if not os.path.isfile(icon_path):
            # Fallback: gui.py's own directory (covers dev mode)
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.isfile(icon_path):
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
            self.results = self.scan_engine.scan_all()
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

    def _populate_tree(self):
        self._clear_tree()
        current_category = None

        for item in self.results:
            if item.category != current_category:
                cat_id = self.tree.insert("", "end", text=f"  {item.category}",
                                          values=("", "", "", "", ""),
                                          tags=("category",), open=True)
                current_category = item.category

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

            self.tree.insert(
                cat_id, "end",
                text=f"{prefix}{item.label}",
                values=(
                    size_display,
                    files_display,
                    risk_display,
                    item.category,
                    item.path
                ),
                tags=(tag,),
            )

    def _on_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        values = item.get("values", ())
        if not values or values[0] == "":
            self._clear_detail()
            return

        label = item.get("text", "").strip()
        for p in ["🔒 ", "🟢 ", "🟡 ", "🔴 ", ". "]:
            if label.startswith(p):
                label = label[len(p):].strip()
                break

        for r in self.results:
            if r.label == label:
                self._show_detail(r)
                return

    def _get_selected_scan_item(self) -> Optional[ScanItem]:
        selection = self.tree.selection()
        if not selection:
            return None
        item = self.tree.item(selection[0])
        values = item.get("values", ())
        if not values or values[0] == "":
            return None
        label = item.get("text", "").strip()
        for p in ["🔒 ", "🟢 ", "🟡 ", "🔴 ", ". "]:
            if label.startswith(p):
                label = label[len(p):].strip()
                break
        for r in self.results:
            if r.label == label:
                return r
        return None

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
        if scan_item and scan_item.readonly:
            messagebox.showinfo("Read-Only",
                f"This item is read-only and cannot be cleaned:\n\n"
                f"🔒 {scan_item.label}\n\n"
                f"{scan_item.cleaning_note}")
            return
        if scan_item and scan_item.exists and scan_item.size_bytes > 0:
            confirm = messagebox.askyesno(
                "Confirm Clean",
                f"Clean the following item?\n\n"
                f"{scan_item.risk_icon} {scan_item.label}\n"
                f"Size: {scan_item.size_str}\n\n"
                f"Note: {scan_item.cleaning_note}"
            )
            if confirm:
                self.is_cleaning = True
                self.scan_btn.configure(state="disabled")
                self.clean_btn.configure(state="disabled")
                self.progress_label.configure(text="Cleaning...")
                self.progress_var.set(50)
                self._append_log(f"Cleaning: {scan_item.label}...", "warn")
                self.clean_engine = CleanEngine(log_callback=self._append_log)

                def _do_clean():
                    success, freed = self.clean_engine.clean_item(scan_item)
                    self.cleaned_items = self.clean_engine._cleaned_items
                    self.root.after(0, lambda: self._on_clean_complete(freed))

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
        for cat_node in self.tree.get_children():
            for item_node in self.tree.get_children(cat_node):
                label = self.tree.item(item_node, "text").strip()
                for p in ["🔒 ", "🟢 ", "🟡 ", "🔴 ", ". "]:
                    if label.startswith(p):
                        label = label[len(p):].strip()
                        break
                for r in self.results:
                    if (r.label == label and r.risk_level == "safe"
                            and r.exists and r.size_bytes > 0 and not r.readonly):
                        self.tree.selection_add(item_node)
                        count += 1
                        break

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
            label = self.tree.item(sel, "text").strip()
            for p in ["🔒 ", "🟢 ", "🟡 ", "🔴 ", ". "]:
                if label.startswith(p):
                    label = label[len(p):].strip()
                    break
            for r in self.results:
                if r.label == label and r.exists and r.size_bytes > 0 and not r.readonly:
                    items_to_clean.append(r)
                    break

        if not items_to_clean:
            messagebox.showinfo("Info", "Selected items are read-only or not found.")
            return

        if not items_to_clean:
            messagebox.showinfo("Info", "Selected items not found or empty.")
            return

        total_size = sum(i.size_bytes for i in items_to_clean)
        item_names = "\n".join(
            f"  {i.risk_icon} {i.label} ({i.size_str})" for i in items_to_clean)

        has_caution = any(i.risk_level == "caution" for i in items_to_clean)
        has_medium  = any(i.risk_level == "medium"  for i in items_to_clean)

        warn_text = ""
        if has_caution:
            warn_text = "\n\n  WARNING: Contains high-risk items. Proceed with caution!"
        elif has_medium:
            warn_text = "\n\n  NOTE: Contains medium-risk items. Please confirm."

        confirm = messagebox.askyesno(
            "Confirm Clean",
            f"Clean {len(items_to_clean)} item(s) "
            f"(total {ScanEngine._format_size(total_size)})?\n\n"
            f"{item_names}{warn_text}\n\n"
            f"Files will be moved to Recycle Bin. Continue?"
        )
        if not confirm:
            return

        self.is_cleaning = True
        self.scan_btn.configure(state="disabled")
        self.clean_btn.configure(state="disabled")
        self.progress_label.configure(text="Cleaning...")
        self.progress_var.set(0)
        self._append_log(f"Cleaning {len(items_to_clean)} item(s)...", "warn")

        self.clean_engine = CleanEngine(log_callback=self._append_log)
        threading.Thread(
            target=self._clean_worker, args=(items_to_clean,), daemon=True
        ).start()

    def _clean_worker(self, items):
        total = len(items)
        freed_total = 0
        for i, item in enumerate(items):
            self._append_log(f"Cleaning: {item.label}...", "info")
            success, freed = self.clean_engine.clean_item(item)
            freed_total += freed

            self.root.after(0,
                lambda idx=i, t=total: self.progress_var.set((idx / t) * 100))

            if success:
                self._append_log(f"  OK  Released {ScanEngine._format_size(freed)}",
                                 "success")
            else:
                self._append_log(f"  FAIL  Clean failed.", "error")

        self.cleaned_items = self.clean_engine._cleaned_items
        self.root.after(0, lambda: self._on_clean_complete(freed_total))

    def _on_clean_complete(self, freed_total: int):
        self.is_cleaning = False
        self.scan_btn.configure(state="normal")
        self.clean_btn.configure(state="normal")
        self.progress_var.set(100)

        freed_str = ScanEngine._format_size(freed_total)
        self.progress_label.configure(text="Clean Complete")
        self.stat_freed.configure(text=freed_str)
        self._append_log(f"Clean complete! Released {freed_str}", "success")
        messagebox.showinfo("Clean Complete",
            f"Freed: {freed_str}\n\nFiles moved to Recycle Bin.")

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
                ("All Files",   "*.*"),
            ],
            initialfile=f"SysClean_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )
        if not filepath:
            return

        try:
            if filepath.endswith(".json"):
                content = ReportGenerator.generate_json_report(self.results)
            else:
                content = ReportGenerator.generate_text_report(
                    self.results, self.cleaned_items)

            with open(filepath, "w", encoding="utf-8") as f:
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
