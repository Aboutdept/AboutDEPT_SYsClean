# -*- coding: utf-8 -*-
"""check_undefined_names 自检：必须能检出「变量未定义」形态的 Bug。"""
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_undefined_names as C

CASE = (
    "def _start_clean(self):\n"
    "    items_to_clean = []\n"
    "    return total_size, has_caution, has_medium\n"
)

OK_CASE = (
    "def _start_clean(self):\n"
    "    items_to_clean = []\n"
    "    total_size = sum(1 for _ in items_to_clean)\n"
    "    has_caution = False\n"
    "    has_medium = False\n"
    "    return total_size, has_caution, has_medium\n"
)


def scan(src):
    t = ast.parse(src)
    s = C.ScopeChecker(C.module_names(t))
    s.visit(t)
    return sorted(n for n, _ in s.issues)


bad = scan(CASE)
good = scan(OK_CASE)

ok1 = bad == ["has_caution", "has_medium", "total_size"]
ok2 = good == []

print(("PASS  " if ok1 else "FAIL  ") + f"能检出未定义变量 -> {bad}")
print(("PASS  " if ok2 else "FAIL  ") + f"正常代码无误报 -> {good}")
sys.exit(0 if (ok1 and ok2) else 1)
