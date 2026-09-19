# -*- coding: utf-8 -*-
"""
Clean selected 点击无反应 — 回归测试

背景：先前把 messagebox.askyesno 换成 ConfirmDialog 时，误删了
_start_clean 中 total_size / has_caution / has_medium 的计算，
导致点击按钮即抛 NameError；pythonw 无控制台 → 静默无反应。

本测试用轻量 harness 直接驱动 _start_clean 全链路，确保不再出现
未定义变量 / 工作线程异常导致界面卡死的情况。
"""
import os
import sys
import time
import types
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gui  # noqa: E402
import scanner  # noqa: E402
from scanner import ScanItem, ScanEngine  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"   [ {detail} ]" if detail else ""))


# ---------------------------------------------------------------- harness
class _Var:
    def __init__(self, v=0):
        self.v = v

    def set(self, v):
        self.v = v

    def get(self):
        return self.v


class _Widget:
    def __init__(self):
        self.state = "normal"
        self.text = ""

    def configure(self, **kw):
        if "state" in kw:
            self.state = kw["state"]
        if "text" in kw:
            self.text = kw["text"]


class _Tree:
    def __init__(self, selection):
        self._sel = list(selection)

    def selection(self):
        return list(self._sel)


def make_app(items, selected_ids, monkeypatch_clean=None):
    """构造一个只含 _start_clean 所需成员的 harness。

    说明：无头环境下不能真的弹 Tk 窗口（wait_window 会阻塞），
    因此调用方需自行把 gui.ConfirmDialog / gui.messagebox 换成桩。
    """
    app = object.__new__(gui.SysCleanApp)
    app.results = items
    app.id_map = {}
    app._current_excludes = []
    app._cleaned_ids = []
    app.cleaned_items = []
    app.is_cleaning = False
    app.is_scanning = False
    app.scan_btn = _Widget()
    app.clean_btn = _Widget()
    app.progress_var = _Var(0)
    app.progress_label = _Widget()
    app.stat_freed = _Widget()
    app.settings = types.SimpleNamespace(selected_ids=[], save=lambda: None)
    app.logs = []
    app.root = types.SimpleNamespace(after=lambda ms, fn: fn())
    app.tree = _Tree(selected_ids)
    app._append_log = lambda m, t="info": app.logs.append(str(m))
    app._populate_tree = lambda: None
    app._update_stats = lambda: None

    if monkeypatch_clean is not None:
        app._make_clean_engine = lambda: monkeypatch_clean
    else:
        app._make_clean_engine = gui.SysCleanApp._make_clean_engine.__get__(app)
    return app


def mk_item(iid, label, size, risk="safe", path=None):
    it = ScanItem(
        id=iid, label=label, path=path or f"C:\\tmp\\{iid}",
        category="Test", risk_level=risk,
        description="d", cleaning_note="n",
    )
    it.exists = True
    it.size_bytes = size
    it.files = 1
    it.readonly = False
    it.installed = True
    return it


# ---------------------------------------------------------------- tests
class _FakeMessageBox:
    """替换 tkinter.messagebox，避免无头环境弹出阻塞式对话框。"""

    def __init__(self):
        self.calls = []

    def showinfo(self, *a, **k):
        self.calls.append(("info", a))

    def showerror(self, *a, **k):
        self.calls.append(("error", a))

    def showwarning(self, *a, **k):
        self.calls.append(("warn", a))

    def askyesno(self, *a, **k):
        self.calls.append(("ask", a))
        return True


class _FakeConfirmDialog:
    """替换 ConfirmDialog：只记录构造参数，不创建 Tk 窗口。"""

    last = None
    result = True

    def __init__(self, parent, title="", summary="", items=None,
                 danger=False, caution=False, confirm_text=""):
        _FakeConfirmDialog.last = {
            "title": title, "summary": summary, "items": items or [],
            "danger": danger, "caution": caution, "confirm_text": confirm_text,
        }

    def show(self):
        return _FakeConfirmDialog.result


def install_stubs():
    """安装桩，返回 (orig_dialog, orig_messagebox)。"""
    od, om = gui.ConfirmDialog, gui.messagebox
    gui.ConfirmDialog = _FakeConfirmDialog
    gui.messagebox = _FakeMessageBox()
    return od, om


def test_start_clean_no_nameerror():
    """核心回归：点击 Clean Selected 不得抛 NameError（变量缺失）。"""
    items = [mk_item("a", "Alpha", 1024, "safe"),
             mk_item("b", "Beta", 2048, "caution")]
    app = make_app(items, ["iid-a", "iid-b"])
    app.id_map = {"iid-a": items[0], "iid-b": items[1]}

    od, om = install_stubs()

    # 拦截真实删除，避免动用户文件
    eng = scanner.CleanEngine(log_callback=lambda m: None, exclude_rules=[])
    eng.clean_item = lambda item: (True, item.size_bytes)
    app._make_clean_engine = lambda: eng

    err = None
    try:
        app._start_clean()
        # 等后台线程收尾（root.after 桩是同步执行，线程结束后即完成）
        for _ in range(100):
            if not app.is_cleaning:
                break
            time.sleep(0.02)
    except Exception as e:  # NameError 等
        err = e
    finally:
        gui.ConfirmDialog, gui.messagebox = od, om

    cap = _FakeConfirmDialog.last or {}
    check("点击 Clean Selected 不抛异常", err is None, repr(err))
    check("确认框收到 2 项明细", len(cap.get("items", [])) == 2,
          str(len(cap.get("items", []))))
    check("合计大小写入摘要（3.00 KB）", "3.00 KB" in cap.get("summary", ""),
          cap.get("summary", ""))
    check("caution 项触发危险标记", cap.get("danger") is True, str(cap.get("danger")))
    check("清理线程已启动并完成收尾", app.is_cleaning is False)
    check("释放空间已统计", app.progress_label.text == "Clean Complete",
          app.progress_label.text)
    check("统计释放 3.00 KB", app.stat_freed.text == "3.00 KB", app.stat_freed.text)


def test_confirm_dialog_not_growing():
    """大量条目时确认框高度恒定（不超屏幕）。"""
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception as e:
        check("ConfirmDialog 几何恒定", False, f"Tk 不可用: {e}")
        return
    root.withdraw()
    try:
        base = None
        for n in (3, 300):
            d = gui.ConfirmDialog(
                root, title="t", summary="s",
                items=[("●", f"item-{i}", "1.0 MB", f"C:\\p\\{i}") for i in range(n)],
                danger=True)
            h = d.win.winfo_reqheight()
            d.win.destroy()
            if base is None:
                base = h
            ok = (h == base) and h <= root.winfo_screenheight()
            check(f"ConfirmDialog {n} 项高度恒定且未超屏", ok, f"h={h} base={base}")
    finally:
        root.destroy()


def test_clean_worker_exception_recovers():
    """清理过程抛异常时，按钮必须恢复可用，不能永久卡在 Cleaning。"""
    items = [mk_item("c", "Gamma", 4096)]
    app = make_app(items, ["iid-c"])
    app.id_map = {"iid-c": items[0]}

    od, om = install_stubs()

    class Boom:
        _cleaned_items = []

        def clean_item(self, item):
            raise RuntimeError("模拟清理失败")

        def finalize(self):
            pass

    app._make_clean_engine = lambda: Boom()
    err = None
    try:
        app._start_clean()
        for _ in range(100):
            if not app.is_cleaning:
                break
            time.sleep(0.02)
    except Exception as e:
        err = e
    finally:
        gui.ConfirmDialog, gui.messagebox = od, om

    check("异常时不向上抛出", err is None, repr(err))
    check("异常后按钮恢复可用", app.clean_btn.state == "normal", app.clean_btn.state)
    check("异常后标记为 Clean Failed", app.progress_label.text == "Clean Failed",
          app.progress_label.text)
    check("异常已写入日志", any("模拟清理失败" in m for m in app.logs), str(app.logs[-1:]))


def test_tk_error_hook_installed():
    """tkinter 回调异常兜底已安装（无控制台时不静默）。"""
    check("report_callback_exception 在 __init__ 中安装",
          "report_callback_exception" in gui.SysCleanApp.__init__.__code__.co_names)

    app = object.__new__(gui.SysCleanApp)
    app.logs = []
    app._append_log = lambda m, t="info": app.logs.append(m)
    app.scan_btn = _Widget()
    app.clean_btn = _Widget()
    app.progress_label = _Widget()

    import tkinter as tk
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        root = None
    # messagebox 在无窗口时可能弹窗，这里只验证不抛异常
    try:
        gui.messagebox.showerror = lambda *a, **k: None
    except Exception:
        pass
    try:
        app._on_tk_error(NameError, NameError("name 'x' is not defined"), None)
        ok = True
    except Exception as e:
        ok = False
        app.logs.append(repr(e))
    finally:
        if root is not None:
            root.destroy()
    check("异常兜底函数可执行", ok, str(app.logs[-1:]))


def main():
    print("=" * 64)
    print("SysClean - Clean selected 无反应 回归测试")
    print("=" * 64)
    test_start_clean_no_nameerror()
    test_confirm_dialog_not_growing()
    test_clean_worker_exception_recovers()
    test_tk_error_hook_installed()
    print("-" * 64)
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"总计 {len(RESULTS)} 项，通过 {len(RESULTS) - len(failed)}，失败 {len(failed)}")
    if failed:
        print("失败项：")
        for n in failed:
            print("  - " + n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
