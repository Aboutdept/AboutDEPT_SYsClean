# -*- coding: utf-8 -*-
"""
GUI 冒烟测试：真实构造 SysCleanApp（真 Tk 窗口），走一遍
「扫描结果入树 → 选中 → 点击 Clean Selected → 收尾」全链路。

目的：捕获真实窗口构造 / 真实 Tk 事件循环下的属性错误与 NameError。
这类问题在纯逻辑桩测试里发现不了，而 pythonw 下又是静默的。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import ScanItem  # noqa: E402

import gui  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"   [ {detail} ]" if detail else ""))


class _MsgBox:
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


class _Dialog:
    last = None

    def __init__(self, parent, title="", summary="", items=None,
                 danger=False, caution=False, confirm_text=""):
        _Dialog.last = {"items": items or [], "summary": summary, "danger": danger}

    def show(self):
        return True


def mk_item(iid, label, size, risk="safe", cat="冒烟分类"):
    it = ScanItem(id=iid, label=label, path=f"C:\\tmp\\{iid}", category=cat,
                  risk_level=risk, description="d", cleaning_note="n")
    it.exists = True
    it.size_bytes = size
    it.files = 3
    it.readonly = False
    it.installed = True
    return it


def main():
    print("=" * 64)
    print("SysClean GUI 冒烟测试（真实 Tk 窗口）")
    print("=" * 64)

    try:
        import tkinter as tk
        tk.Tk()
    except Exception as e:
        print("Tk 不可用，跳过：", e)
        return 0

    err = None
    app = None
    try:
        app = gui.SysCleanApp()
        check("SysCleanApp 构造成功（含全部控件）", True)
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        check("SysCleanApp 构造成功（含全部控件）", False, repr(e))

    if app is None:
        print(err)
        return 1

    app.root.withdraw()
    try:
        # --- 注入扫描结果并填充树 ---
        items = [mk_item("s1", "冒烟项A", 5 * 1024 * 1024, "safe"),
                 mk_item("s2", "冒烟项B", 7 * 1024 * 1024, "caution")]
        app.results = items
        app.hide_not_installed = True
        app._populate_tree()
        check("树已填充（id_map 命中 2 项）", len(app.id_map) == 2,
              str(len(app.id_map)))
        check("分类标题只出现一次",
              len(app.tree.get_children()) == 1, str(len(app.tree.get_children())))

        # --- 选中并点击 Clean Selected ---
        target = [k for k, v in app.id_map.items() if v.id == "s1"][0]
        app.tree.selection_set(target)

        od, om = gui.ConfirmDialog, gui.messagebox
        gui.ConfirmDialog = _Dialog
        gui.messagebox = _MsgBox()

        # 不写真实审计日志（log_file=None），也不真的删文件
        deleted = []
        eng = gui.CleanEngine(log_callback=lambda m: None,
                              exclude_rules=[], log_file=None)

        def _fake_clean(item):
            deleted.append(item.id)
            return True, item.size_bytes

        eng.clean_item = _fake_clean
        app._make_clean_engine = lambda: eng

        app._start_clean()

        # 真实运行环境主线程在 mainloop 中；工作线程的 root.after 才能在
        # mainloop 里被投递。测试必须同样进入 mainloop，否则 after 会抛
        # RuntimeError('main thread is not in main loop')。
        deadline = time.time() + 15

        def pump():
            if not app.is_cleaning or time.time() > deadline:
                app.root.quit()
                return
            app.root.after(30, pump)

        app.root.after(30, pump)
        app.root.mainloop()

        check("点击后真实调用了清理", deleted == ["s1"], str(deleted))
        check("界面收尾为 Clean Complete",
              app.progress_label.cget("text") == "Clean Complete",
              app.progress_label.cget("text"))
        check("释放空间已回写统计", app.stat_freed.cget("text") == "5.00 MB",
              app.stat_freed.cget("text"))
        check("清理按钮恢复可用", str(app.clean_btn.cget("state")) == "normal",
              str(app.clean_btn.cget("state")))
        gui.ConfirmDialog, gui.messagebox = od, om
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        check("清理链路无异常", False, repr(e))
        if err:
            print(err)
    finally:
        try:
            app.root.destroy()
        except Exception:
            pass

    print("-" * 64)
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"总计 {len(RESULTS)} 项，通过 {len(RESULTS) - len(failed)}，失败 {len(failed)}")
    for n in failed:
        print("  - " + n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
