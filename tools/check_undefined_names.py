# -*- coding: utf-8 -*-
"""轻量未定义名扫描（mini-pyflakes）：捕获 NameError 类隐患。

用法：python tools/check_undefined_names.py
"""
import ast
import builtins
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTINS = set(dir(builtins))


def module_names(tree):
    """模块级定义的名字 + 导入名。"""
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, (ast.Try, ast.If, ast.With, ast.For, ast.While)):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(sub.name)
                elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                    for a in sub.names:
                        names.add((a.asname or a.name).split(".")[0])
                elif isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        for n in ast.walk(t):
                            if isinstance(n, ast.Name):
                                names.add(n.id)
    return names


class ScopeChecker(ast.NodeVisitor):
    def __init__(self, mod_names):
        self.mod_names = mod_names
        self.issues = []
        self.stack = [set()]

    def _enter(self, extra=None):
        self.stack.append(set(extra or ()))

    def _exit(self):
        self.stack.pop()

    def _bound(self, name):
        return any(name in s for s in self.stack)

    def _collect_bound(self, node):
        """收集函数体内所有被绑定的名字（含 lambda / 推导式 / 注解赋值）。"""
        for n in ast.walk(node):
            if isinstance(n, (ast.Assign, ast.AugAssign)):
                tgts = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in tgts:
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name):
                            self.stack[-1].add(x.id)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                self.stack[-1].add(n.target.id)
            elif isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name):
                self.stack[-1].add(n.target.id)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    self.stack[-1].add((a.asname or a.name).split(".")[0])
            elif isinstance(n, ast.ClassDef):
                # 类名本身；类体作用域不加入其属性（属性通过 self.X 访问）
                self.stack[-1].add(n.name)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if not isinstance(n, ast.Lambda):
                    self.stack[-1].add(n.name)
                for a in (n.args.args + n.args.kwonlyargs):
                    self.stack[-1].add(a.arg)
                if n.args.vararg:
                    self.stack[-1].add(n.args.vararg.arg)
                if n.args.kwarg:
                    self.stack[-1].add(n.args.kwarg.arg)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                self.stack[-1].add(n.name)
            elif isinstance(n, (ast.For, ast.comprehension)):
                for x in ast.walk(n.target):
                    if isinstance(x, ast.Name):
                        self.stack[-1].add(x.id)
            elif isinstance(n, ast.withitem) and n.optional_vars is not None:
                for x in ast.walk(n.optional_vars):
                    if isinstance(x, ast.Name):
                        self.stack[-1].add(x.id)
            elif isinstance(n, (ast.Global, ast.Nonlocal)):
                for nm in n.names:
                    self.stack[-1].add(nm)

    def visit_FunctionDef(self, node):
        args = {a.arg for a in node.args.args + node.args.kwonlyargs}
        if node.args.vararg:
            args.add(node.args.vararg.arg)
        if node.args.kwarg:
            args.add(node.args.kwarg.arg)
        self._enter(args)
        self._collect_bound(node)
        self.generic_visit(node)
        self._exit()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        args = {a.arg for a in node.args.args + node.args.kwonlyargs}
        self._enter(args)
        self.generic_visit(node)
        self._exit()

    def visit_ClassDef(self, node):
        self._enter()
        self._collect_bound(node)
        self.generic_visit(node)
        self._exit()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            n = node.id
            if (n not in BUILTINS and n not in self.mod_names
                    and not self._bound(n) and not n.startswith("__")):
                self.issues.append((n, node.lineno))
        self.generic_visit(node)


def main():
    files = [f for f in os.listdir(ROOT)
             if f.endswith(".py") and f != "conftest.py"]
    total = 0
    for f in sorted(files):
        path = os.path.join(ROOT, f)
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src, filename=path)
        mod = module_names(tree)
        c = ScopeChecker(mod)
        c.visit(tree)
        if c.issues:
            print(f"\n=== {f} ===")
            for name, line in c.issues:
                print(f"  行 {line}: 可能未定义 -> {name}")
                total += 1
    print(f"\n扫描 {len(files)} 个文件，可疑未定义名 {total} 处")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
