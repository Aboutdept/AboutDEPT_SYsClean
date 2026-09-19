# -*- coding: utf-8 -*-
"""规则数据库 + 确认对话框 回归测试（只读，不删除任何文件）。"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
os.chdir(PROJ)

from scanner import (ScanEngine, ScanItem, load_database_rules,  # noqa: E402
                     load_custom_rules, PathExpander)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok))
    print(("PASS  " if ok else "FAIL  ") + name + (("  | " + detail) if detail else ""))


def test_db_rules_loaded():
    items = load_database_rules()
    check("数据库规则已加载", len(items) > 0, f"{len(items)} 条")
    check("数据库规则路径已展开", all("%" not in i.path for i in items),
          str([i.path for i in items if "%" in i.path][:2]))
    cats = sorted({i.category for i in items})
    check("分类非默认值", "Database Rules" not in cats, str(cats))
    check("CG/AIGC 分类存在", "AIGC" in cats, str(cats))
    risks = sorted({i.risk_level for i in items})
    check("Risk 字段生效（含 caution）", "caution" in risks, str(risks))
    check("HuggingFace 项为 caution",
          any(i.risk_level == "caution" and "Hugging" in i.label for i in items))
    check("id 前缀为 db_", all(i.id.startswith("db_") for i in items),
          str([i.id for i in items[:2]]))
    check("source 为 db", all(i.source == "db" for i in items))


def test_db_merge_into_targets():
    db_items = load_database_rules()
    eng = ScanEngine()
    targets = eng.get_scan_targets(db_items=db_items)
    ids = {t.id for t in targets}
    hit = [i for i in db_items if i.id in ids]
    check("数据库规则合并进扫描目标", len(hit) > 0, f"{len(hit)}/{len(db_items)}")


def test_custom_still_works():
    custom = load_custom_rules()
    check("Custom/ 规则仍以 custom 为前缀",
          all(i.id.startswith("custom_") for i in custom), f"{len(custom)} 条")
    check("Custom/ 默认分类保持 Custom Rules",
          all(i.category == "Custom Rules" for i in custom))


def test_path_expander_new_vars():
    e = PathExpander.expand(r"%SystemDrive%\Users")
    check("%SystemDrive% 展开无双反斜杠", "\\\\" not in e, e)
    check("%Public% 已展开", not PathExpander.expand(r"%Public%\x").startswith("%"),
          PathExpander.expand(r"%Public%\x"))
    check("%ProgramFilesX86% 已展开",
          not PathExpander.expand(r"%ProgramFilesX86%\x").startswith("%"))


def test_userprofile_not_hardcoded():
    up = os.environ.get("USERPROFILE", "")
    eng = ScanEngine()
    targets = eng.get_scan_targets()
    bad = [t.id for t in targets
           if ("C:\\Users\\" + os.environ.get("USERNAME", "")) in t.path
           and up not in t.path]
    check("内置目标不再硬编码 C:\\Users\\<name>", not bad, str(bad[:5]))


def test_confirm_dialog_fixed_height():
    """无头环境可能无法建窗口 —— 失败标记为 skip 而非 FAIL。"""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception as ex:
        print("SKIP  确认对话框（无法创建 Tk 窗口）: " + repr(ex))
        return
    try:
        from gui import ConfirmDialog
        few = [("🟢", f"item-{i}", "1.00 MB", rf"C:\path\to\some\folder-{i}")
               for i in range(3)]
        many = [("🟢", f"item-{i}", "1.00 MB", rf"C:\path\to\some\folder-{i}")
                for i in range(300)]
        d1 = ConfirmDialog(root, "t", "s", few)
        h1 = d1.win.winfo_reqheight()
        d1.win.destroy()
        d2 = ConfirmDialog(root, "t", "s", many)
        h2 = d2.win.winfo_reqheight()
        scrolled = d2.text.yview()
        d2.win.destroy()
        check("确认框高度不随项数增长", h1 == h2, f"{h1} vs {h2}")
        check("确认框高度有上限", max(h1, h2) <= 560, f"{max(h1, h2)}")
        check("内容超出时可滚动（yview != (0,1)）", scrolled != (0.0, 1.0), str(scrolled))
    finally:
        root.destroy()


def test_syntax():
    import py_compile
    for f in ("scanner.py", "gui.py", "cli.py", "winapp2_parser.py",
              "settings.py", "main.py"):
        try:
            py_compile.compile(os.path.join(PROJ, f), doraise=True)
            check(f"语法编译 {f}", True)
        except Exception as e:
            check(f"语法编译 {f}", False, str(e))


if __name__ == "__main__":
    for fn in (test_db_rules_loaded, test_db_merge_into_targets,
               test_custom_still_works, test_path_expander_new_vars,
               test_userprofile_not_hardcoded, test_confirm_dialog_fixed_height,
               test_syntax):
        try:
            fn()
        except Exception as e:
            check(f"{fn.__name__} 抛出异常", False, repr(e))
    failed = [n for n, ok in RESULTS if not ok]
    print("")
    print(f"总计 {len(RESULTS)} 项，失败 {len(failed)} 项")
    if failed:
        print("失败项: " + ", ".join(failed))
    sys.exit(1 if failed else 0)
