# -*- coding: utf-8 -*-
"""
SysClean CLI - 命令行模式（迭代 3）

支持计划任务静默清理与报告导出，不启动 GUI。

示例：
  # 仅扫描并导出 JSON 报告
  python main.py --scan --report report_2026-07-12.json

  # 导出 CSV 报告（Excel 友好，带 BOM）
  python main.py --scan --report report.csv

  # 用设置中保存的选择静默清理（需 --yes 才真正删除）
  python main.py --auto --yes --log cleanup.log

  # 清理「Temp Files」分类（先干跑确认，再 --yes 执行）
  python main.py --clean --category "Temp Files"
  python main.py --clean --category "Temp Files" --yes

  # 清理全部可清理项并导出汇总
  python main.py --clean --all --yes --report summary.txt
"""

import os
import sys
import argparse
from datetime import datetime

from settings import AppSettings
from scanner import (ScanEngine, CleanEngine, ReportGenerator,
                     default_cleanup_log_path, load_database_rules)
from winapp2_parser import load_winapp2


def _eligible(item) -> bool:
    """可清理项：非只读、存在、有大小、未被排除。"""
    return (not item.readonly) and item.exists and item.size_bytes > 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="SysClean", add_help=True,
        description="SysClean CLI - 扫描与清理（无界面模式）")
    p.add_argument("--scan", action="store_true",
                   help="仅扫描并出报告（不清理）")
    p.add_argument("--clean", action="store_true",
                   help="清理（需配合 --all / --category / --selected / --auto 之一）")
    p.add_argument("--auto", action="store_true",
                   help="用设置中保存的选择静默清理（等同 --clean --selected）")
    p.add_argument("--all", action="store_true",
                   help="清理所有可清理项（非只读、存在、有大小）")
    p.add_argument("--category", metavar="NAME",
                   help="仅清理指定分类的项（子串匹配，不区分大小写）")
    p.add_argument("--selected", action="store_true",
                   help="仅清理设置中保存勾选的项")
    p.add_argument("--yes", action="store_true",
                   help="确认执行删除。缺省为「干跑」：仅打印计划，不删除任何文件")
    p.add_argument("--report", metavar="PATH",
                   help="导出报告文件（.json / .csv / .txt）")
    p.add_argument("--log", metavar="PATH",
                   help="清理审计日志路径（默认 SysClean_cleanup.log）")
    p.add_argument("--winapp2", dest="winapp2", action="store_true", default=None,
                   help="启用 winapp2 社区数据库")
    p.add_argument("--no-winapp2", dest="winapp2", action="store_false",
                   help="停用 winapp2 社区数据库")
    p.add_argument("--db", dest="databases", action="store_true", default=None,
                   help="启用 CG/AIGC 规则数据库（Databases/*.ini）")
    p.add_argument("--no-db", dest="databases", action="store_false",
                   help="停用 CG/AIGC 规则数据库")
    return p


def _in_scope(item, scope: str, settings: AppSettings, category: str) -> bool:
    if scope == "all":
        return True
    if scope == "selected":
        return item.id in set(settings.selected_ids)
    if scope == "category":
        # BUGFIX B5: 空串此前恒真（"" in 任何字符串），会把清理范围放大到全量。
        needle = (category or "").strip().lower()
        return bool(needle) and needle in (item.category or "").lower()
    return False


def _print_summary(results, title: str = "Scan Result"):
    found = [r for r in results if r.exists and r.size_bytes > 0]
    total = sum(r.size_bytes for r in found)
    print("=" * 64)
    print(f"  {title}")
    print("=" * 64)
    print(f"  扫描目标总数 : {len(results)}")
    print(f"  发现可清理项 : {len(found)}")
    print(f"  可回收空间   : {ScanEngine._format_size(total)}"
          f" ({total:,} bytes)")
    by_cat = {}
    for r in found:
        by_cat[r.category] = by_cat.get(r.category, 0) + r.size_bytes
    if by_cat:
        print("  --- 按分类 ---")
        for cat, sz in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f"    {cat:<28} {ScanEngine._format_size(sz)}")
    print("=" * 64)


def _export_report(path: str, results, cleaned_items=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        content = ReportGenerator.generate_json_report(results)
        write_mode = "w"
        encoding = "utf-8"
    elif ext == ".csv":
        content = ReportGenerator.generate_csv_report(results, cleaned_items)
        write_mode = "w"
        encoding = "utf-8-sig"   # Excel 中文友好
    else:
        content = ReportGenerator.generate_text_report(results, cleaned_items)
        write_mode = "w"
        encoding = "utf-8"
    with open(path, write_mode, encoding=encoding) as f:
        f.write(content)
    print(f"  [OK] 报告已导出: {path}")


def run_cli(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # 决定运行模式
    if args.auto:
        mode = "clean"
        scope = "selected"
    elif args.clean:
        mode = "clean"
        if args.all:
            scope = "all"
        elif args.category:
            scope = "category"
        else:
            scope = "selected"
    elif args.scan:
        mode = "scan"
    else:
        parser.print_help()
        return 0

    # BUGFIX B5: 空分类名会让 range 判断退化成「全量清理」，在此显式拒绝
    if args.category is not None and not args.category.strip():
        parser.error("--category 不能为空字符串")

    settings = AppSettings()
    settings.load()

    # winapp2 / hide 可被 CLI 覆盖
    use_winapp2 = settings.enable_winapp2 if args.winapp2 is None else args.winapp2

    winapp2_items, winapp2_excludes = load_winapp2(
        settings.winapp2_path, use_winapp2)
    if use_winapp2:
        print(f"  [info] winapp2 数据库: {len(winapp2_items)} 条已安装 App 条目")

    # 规则数据库（Databases/*.ini）
    use_db = settings.enable_databases if args.databases is None else args.databases
    db_items = load_database_rules() if use_db else []
    if use_db:
        print(f"  [info] 规则数据库: {len(db_items)} 条（CG/VP/AIGC + 系统补充）")

    engine = ScanEngine()
    # hide 选项仅影响 GUI 展示；CLI 始终扫描全部，再按 eligible 过滤
    results = engine.scan_all(
        winapp2_items=winapp2_items,
        winapp2_excludes=winapp2_excludes,
        global_excludes=settings.global_exclusions,
        db_items=db_items,
    )

    if mode == "scan":
        _print_summary(results, "Scan Result")
        if args.report:
            _export_report(args.report, results)
        return 0

    # ---- clean 模式 ----
    candidates = [r for r in results
                  if _eligible(r) and _in_scope(r, scope, settings, args.category or "")]
    total = sum(r.size_bytes for r in candidates)

    if not candidates:
        print("  没有符合范围的可清理项。")
        if args.report:
            _export_report(args.report, results)
        return 0

    print("=" * 64)
    print(f"  计划清理（scope={scope}）: {len(candidates)} 项, "
          f"共 {ScanEngine._format_size(total)}")
    print("=" * 64)
    for r in candidates:
        print(f"    [{r.risk_level}] {r.label}  {r.size_str}  -> {r.path}")

    if not args.yes:
        print("\n  * 干跑模式（dry-run）：未删除任何文件。")
        print("  * 确认执行请加上 --yes 参数。")
        if args.report:
            _export_report(args.report, results)
        return 0

    # ---- 实际清理 ----
    log_path = args.log or default_cleanup_log_path()
    cleaner = CleanEngine(
        log_callback=lambda m: print(f"  [clean] {m}"),
        exclude_rules=engine.exclude_rules,
        log_file=log_path,
    )
    freed_total = 0
    ok_count = 0
    for it in candidates:
        ok, freed = cleaner.clean_item(it)
        freed_total += freed
        if ok:
            ok_count += 1
    cleaner.finalize()

    print("=" * 64)
    print(f"  清理完成: {ok_count}/{len(candidates)} 项, "
          f"释放 {ScanEngine._format_size(freed_total)}")
    print(f"  审计日志: {log_path}")
    print("=" * 64)

    if args.report:
        _export_report(args.report, results, cleaner._cleaned_items)

    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
