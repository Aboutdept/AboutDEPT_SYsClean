# -*- coding: utf-8 -*-
"""SysClean B1-B6 回归测试（2026-09-19）

运行：
    <Python 3.10 或带 tkinter 的解释器> tests/test_bugfix_b1_b6.py

约定：
  * 只读；唯一写入是 tempfile 下自造的一个 sample.tmp，且回收站调用被 monkeypatch
    拦截，不会真实删除任何文件。
  * 必须用带 tkinter 的解释器（managed Python 3.13.12 无 tkinter，会 ImportError）。
"""
import os
import sys
import shutil
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
os.chdir(PROJ)

from winapp2_parser import load_winapp2                      # noqa: E402
from scanner import PathExpander, CleanEngine, ScanEngine, ScanItem  # noqa: E402
from gui import SysCleanApp                                   # noqa: E402
import cli as cli_mod                                        # noqa: E402


RESULTS = []
calls = []          # 记录被「移入回收站」的路径（测试桩填充）


def check(name, ok, detail=""):
    RESULTS.append((name, ok))
    print(("PASS  " if ok else "FAIL  ") + name + (("  | " + detail) if detail else ""))


def test_b1_winapp2_path_expanded():
    items, _ = load_winapp2(os.path.join(PROJ, "Winapp2.ini"), True)
    still_raw = [i for i in items if "%" in i.path]
    check("B1 winapp2 条目路径无残留 %VAR%", not still_raw,
          f"总条目 {len(items)}，残留 {len(still_raw)}")

    eng = ScanEngine()
    no_star = [i for i in items if "*" not in i.path]

    # 断言设计说明（2026-09-19 修订）：
    # 原实现只抽样前 15 条并要求「至少 1 条非空」，属于脆弱断言 —— 本机 winapp2
    # 前 30 条无通配符目录（.dotnet / .Thumbnails / Adobe\CRLogs ...）顶层恰好
    # 没有匹配文件（内容都在子目录里，而这些 FileKey 未开 RECURSE），
    # 于是 B1 明明修好了却判 FAIL。
    # 改为两条统计断言：
    #   1) 路径存在率 —— B1 的核心证据（展开前 265 条路径含 %VAR% 必不存在）
    #   2) 非空命中数 —— 用大样本，避免被个别空目录带偏
    # 只扫一遍 100 条，同时产出两组统计（扫描是真读文件系统，别重复扫）
    sample = no_star[:100]
    for it in sample:
        eng._scan_path(it)
    exists_ok = sum(1 for i in sample[:60] if i.exists)
    nonempty = sum(1 for i in sample if i.exists and i.size_bytes > 0)

    check("B1 无通配符条目展开后路径真实存在", exists_ok >= 55,
          f"抽样 60 条，存在 {exists_ok} 条")
    check("B1 无通配符条目已能真实扫描到内容", nonempty >= 10,
          f"抽样 100 条，非空 {nonempty} 条")


def test_b6_detect_expanded():
    items, _ = load_winapp2(os.path.join(PROJ, "Winapp2.ini"), True)
    det_raw = [i for i in items if any("%" in d for d in i.detect)]
    check("B6 winapp2 detect 无残留 %VAR%", not det_raw, f"残留条目 {len(det_raw)}")


def test_b2_exclusions_expanded():
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")
    ce = CleanEngine(exclude_rules=[("FILE", r"%AppData%\Everything\|Filters.csv"),
                                    ("PATH", r"%LocalAppData%\Foo\Cache")])
    check("B2 FILE 规则命中受保护文件",
          ce._is_excluded(os.path.join(appdata, "Everything", "Filters.csv")) is True)
    check("B2 FILE 规则不放过同目录其它文件",
          ce._is_excluded(os.path.join(appdata, "Everything", "other.dat")) is False)
    check("B2 PATH 规则保护子目录文件",
          ce._is_excluded(os.path.join(local, "Foo", "Cache", "sub", "a.tmp")) is True)
    check("B2 规则已展开为真实路径", all("%" not in v for _, v in ce.exclude_rules))
    check("B2 大小写变体也能展开",
          "%" not in PathExpander.expand(r"%localappdata%\Foo"))


def test_b3_category_grouping():
    def mk(cid, cat, sz):
        return ScanItem(id=cid, label=cid, path=r"C:\x", category=cat,
                        risk_level="safe", description="", size_bytes=sz,
                        exists=True, installed=True)

    fake = [mk("a", "Temp Files", 900), mk("b", "App Cache", 800),
            mk("c", "Temp Files", 700), mk("d", "Logs", 600),
            mk("e", "App Cache", 500)]
    groups = SysCleanApp._group_by_category(fake)
    cats = [c for c, _ in groups]
    check("B3 分类不重复", len(cats) == len(set(cats)), str(cats))
    check("B3 分组内分类一致",
          all(all(i.category == c for i in its) for c, its in groups))
    check("B3 分类顺序按最大项出现顺序",
          cats == ["Temp Files", "App Cache", "Logs"], str(cats))
    check("B3 可见项过滤不丢项", len(SysCleanApp._visible_items(fake, True)) == 5)


def _fake_recycle(path):
    """模拟回收站成功：记录调用并真正移除（仅作用于测试自造的临时文件）。"""
    calls.append(path)
    for fn in (os.remove, lambda p: shutil.rmtree(p, ignore_errors=True)):
        try:
            fn(path)
            break
        except OSError:
            continue


def test_b4_single_file_uses_recycle_bin():
    calls.clear()
    orig = CleanEngine._delete_to_recycle_bin
    CleanEngine._delete_to_recycle_bin = staticmethod(_fake_recycle)
    try:
        tmpdir = tempfile.mkdtemp(prefix="sysclean_b4_")
        fp = os.path.join(tmpdir, "sample.tmp")
        with open(fp, "w") as f:
            f.write("x" * 2048)
        item = ScanItem(id="t", label="t", path=fp, category="T", risk_level="safe",
                        description="", exists=True, size_bytes=2048)
        ok, freed = CleanEngine().clean_item(item)
        check("B4 单文件调用回收站而非 os.remove", calls == [fp], str(calls))
        check("B4 回收站生效后文件不再存在", not os.path.exists(fp))
        check("B4 释放字节统计正确", ok is True and freed == 2048, str(freed))
        # 删除未生效时应判定失败且不虚报释放空间
        fp2 = os.path.join(tmpdir, "stuck.tmp")
        with open(fp2, "w") as f:
            f.write("y" * 1024)
        calls.clear()
        CleanEngine._delete_to_recycle_bin = staticmethod(lambda p: calls.append(p))
        item2 = ScanItem(id="t2", label="t2", path=fp2, category="T", risk_level="safe",
                         description="", exists=True, size_bytes=1024)
        ok2, freed2 = CleanEngine().clean_item(item2)
        check("B4 删除未生效时不虚报释放空间", ok2 is False and freed2 == 0,
              f"ok={ok2} freed={freed2}")
    finally:
        CleanEngine._delete_to_recycle_bin = orig


def test_b5_empty_category():
    class S:
        selected_ids = []

    it = ScanItem(id="x", label="x", path=r"C:\x", category="Temp Files",
                  risk_level="safe", description="")
    check("B5 空 category 不再匹配任意项",
          cli_mod._in_scope(it, "category", S(), "") is False)
    check("B5 合法 category 仍生效",
          cli_mod._in_scope(it, "category", S(), "temp") is True)
    try:
        cli_mod.run_cli(["--clean", "--category", "   "])
        check("B5 CLI 空 --category 被拒绝", False, "未抛 SystemExit")
    except SystemExit as e:
        check("B5 CLI 空 --category 被拒绝", e.code == 2, f"SystemExit code={e.code}")


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
    for fn in (test_b1_winapp2_path_expanded, test_b6_detect_expanded,
               test_b2_exclusions_expanded, test_b3_category_grouping,
               test_b4_single_file_uses_recycle_bin, test_b5_empty_category,
               test_syntax):
        try:
            fn()
        except Exception as e:
            check(f"{fn.__name__} 抛出异常", False, repr(e))
    failed = [n for n, ok in RESULTS if not ok]
    print("")
    print("=" * 60)
    print(f"总计 {len(RESULTS)} 项，失败 {len(failed)} 项")
    if failed:
        print("失败项: " + ", ".join(failed))
    print("=" * 60)
    sys.exit(1 if failed else 0)
