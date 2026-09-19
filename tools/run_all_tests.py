# -*- coding: utf-8 -*-
"""
SysClean 全量回归入口。

用法（必须用带 tkinter 的 Python，本机为 Python310）：
    python tools/run_all_tests.py

依次执行：
  1. tests/test_bugfix_b1_b6.py    B1–B6 修复
  2. tests/test_db_rules.py        规则数据库 + 确认框几何
  3. tests/test_clean_flow.py      Clean Selected 点击链路
  4. tests/test_gui_smoke.py       真实 Tk 窗口冒烟
  5. tools/check_undefined_names.py 未定义名静态扫描（含自检）
  6. 六个源文件语法编译

全程只读取证 + 桩拦截，不会删除任何用户文件。
"""
import os
import subprocess
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

# PowerShell 终端常吞掉子进程 stdout，这里同时落盘一份，便于事后核对
LOG_PATH = os.path.join(BASE, "logs", "regression-latest.log")

SUITES = [
    ("B1–B6 修复", "tests/test_bugfix_b1_b6.py"),
    ("规则数据库", "tests/test_db_rules.py"),
    ("Clean 点击链路", "tests/test_clean_flow.py"),
    ("打包路径解析", "tests/test_app_paths.py"),
    ("GUI 真实窗口冒烟", "tests/test_gui_smoke.py"),
    ("静态扫描自检", "tools/selftest_checker.py"),
]

SOURCES = ["main.py", "gui.py", "scanner.py", "cli.py",
           "settings.py", "winapp2_parser.py"]


def run(args, cwd=BASE):
    """执行子进程。任何执行器自身的异常都要可见，不能悄悄中断整轮回归。"""
    try:
        p = subprocess.run([PY] + args, cwd=cwd,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=600)
    except subprocess.TimeoutExpired:
        return 98, "TIMEOUT: " + " ".join(args)
    except Exception as e:
        import traceback
        return 99, "RUNNER EXCEPTION: %r\n%s" % (e, traceback.format_exc())
    try:
        out = p.stdout.decode("utf-8", errors="replace")
    except Exception:
        out = str(p.stdout)
    return p.returncode, out


def summarize(out):
    """抽取结果行（兼容中文/乱码环境：只认数字与 FAIL）。"""
    lines = []
    for ln in out.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("FAIL"):
            lines.append(s)
        elif "FAIL" in s:
            lines.append(s)
    # 统计行：含「总计」或「失败」
    tail = [ln.strip() for ln in out.splitlines()
            if ("总计" in ln or "失败" in ln or "可疑未定义名" in ln)]
    return lines, tail[-1] if tail else ""


def _emit(line=""):
    """打印并追加到日志文件。"""
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main():
    try:
        return _main()
    except Exception:
        import traceback
        _emit("\n[RUNNER CRASH]\n" + traceback.format_exc())
        return 2


def _main():
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("SysClean 全量回归 %s\n"
                    % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        pass

    _emit("=" * 68)
    _emit("SysClean 全量回归")
    _emit("=" * 68)

    failed_suites = []
    for name, rel in SUITES:
        code, out = run([rel])
        fails, stat = summarize(out)
        ok = (code == 0)
        _emit(f"\n--- {name}  [{rel}]")
        _emit(f"    exit={code}  {stat}")
        for f in fails:
            _emit("    " + f)
        if not ok:
            failed_suites.append(name)
            _emit("    ---- 原始输出尾部 ----")
            for ln in out.splitlines()[-25:]:
                _emit("    | " + ln)

    # 静态扫描
    code, out = run(["tools/check_undefined_names.py"])
    _emit("\n--- 未定义名扫描")
    _emit(f"    exit={code}  {out.strip()}")
    if code != 0:
        failed_suites.append("未定义名扫描")

    # 语法编译
    _emit("\n--- 语法编译")
    for src in SOURCES:
        code, out = run(["-m", "py_compile", src])
        _emit(f"    {src:<20} {'OK' if code == 0 else 'FAIL'}")
        if code != 0:
            failed_suites.append(f"编译 {src}")
            _emit(out)

    _emit("\n" + "=" * 68)
    if failed_suites:
        _emit("存在失败套件： " + ", ".join(failed_suites))
        return 1
    _emit("全部通过")
    _emit(f"日志：{LOG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
