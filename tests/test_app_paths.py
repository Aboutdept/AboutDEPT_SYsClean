# -*- coding: utf-8 -*-
"""
app_paths 单元测试 —— 打包（frozen）路径解析是 exe 能否正常工作的关键。

背景：PyInstaller onefile 下 __main__.__file__ 指向临时解压目录（_MEIxxxxxx），
若沿用旧逻辑，settings.json / 审计日志会写进临时目录，每次启动全丢。
本测试用 monkeypatch 模拟 frozen 环境，覆盖四种关键分支。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app_paths  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"   [ {detail} ]" if detail else ""))


class FrozenEnv:
    """临时把进程伪装成 PyInstaller onefile 运行环境。"""

    def __init__(self, exe_dir, bundle_dir):
        self.exe_dir = exe_dir
        self.bundle = bundle_dir
        self._saved = {}

    def __enter__(self):
        for k in ("frozen", "_MEIPASS", "executable"):
            self._saved[k] = getattr(sys, k, None)
        sys.frozen = True
        sys._MEIPASS = self.bundle
        sys.executable = os.path.join(self.exe_dir, "SysClean.exe")
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            if v is None:
                try:
                    delattr(sys, k)
                except AttributeError:
                    pass
            else:
                setattr(sys, k, v)


def test_frozen_basic():
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = os.path.join(tmp, "dist")
        bundle = os.path.join(tmp, "_MEI123456")
        os.makedirs(exe_dir)
        os.makedirs(bundle)

        with FrozenEnv(exe_dir, bundle):
            check("frozen: is_frozen() 为真", app_paths.is_frozen() is True)
            check("frozen: exe_dir 指向 exe 所在目录",
                  os.path.abspath(app_paths.exe_dir()) == os.path.abspath(exe_dir),
                  app_paths.exe_dir())
            check("frozen: bundle_dir 指向 _MEIPASS",
                  os.path.abspath(app_paths.bundle_dir()) == os.path.abspath(bundle),
                  app_paths.bundle_dir())
            # 关键：可写目录必须是 exe 目录，绝不能是 _MEI 临时目录
            check("frozen: writable_dir 不是临时解压目录",
                  os.path.abspath(app_paths.writable_dir()) == os.path.abspath(exe_dir),
                  app_paths.writable_dir())
            check("frozen: 无覆盖时 data_dir 回退内嵌目录",
                  os.path.abspath(app_paths.data_dir()) == os.path.abspath(bundle),
                  app_paths.data_dir())


def test_frozen_user_override():
    """用户把 Databases/ 放在 exe 旁 → 应覆盖内嵌规则库。"""
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = os.path.join(tmp, "dist")
        bundle = os.path.join(tmp, "_MEI123456")
        os.makedirs(os.path.join(exe_dir, "Databases"))
        os.makedirs(os.path.join(bundle, "Databases"))

        with FrozenEnv(exe_dir, bundle):
            check("frozen: exe 旁有 Databases 时优先使用",
                  os.path.abspath(app_paths.data_dir()) == os.path.abspath(exe_dir),
                  app_paths.data_dir())

        # 仅放 Winapp2.ini 也应触发覆盖
        exe2 = os.path.join(tmp, "dist2")
        os.makedirs(exe2)
        with open(os.path.join(exe2, "Winapp2.ini"), "w", encoding="utf-8") as f:
            f.write("[x]\n")
        with FrozenEnv(exe2, bundle):
            check("frozen: exe 旁有 Winapp2.ini 时优先使用",
                  os.path.abspath(app_paths.data_dir()) == os.path.abspath(exe2),
                  app_paths.data_dir())


def test_source_mode():
    """源码模式：项目根必须正确（不能误判成 tests/）。"""
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    check("源码: project_dir 命中项目根",
          os.path.abspath(app_paths.project_dir()) == os.path.abspath(proj),
          app_paths.project_dir())
    check("源码: is_frozen() 为假", app_paths.is_frozen() is False)
    check("源码: data_dir 与 project_dir 一致",
          os.path.abspath(app_paths.data_dir()) == os.path.abspath(proj),
          app_paths.data_dir())


def test_settings_uses_writable_dir():
    """settings.json 必须落在可写目录（打包后为 exe 目录）。"""
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = os.path.join(tmp, "dist")
        bundle = os.path.join(tmp, "_MEI999")
        os.makedirs(exe_dir)
        os.makedirs(bundle)

        with FrozenEnv(exe_dir, bundle):
            from settings import AppSettings
            s = AppSettings()
            check("frozen: settings.json 落在 exe 目录",
                  os.path.dirname(os.path.abspath(s.path)) == os.path.abspath(exe_dir),
                  s.path)
            check("frozen: winapp2 默认路径落在内嵌数据目录",
                  os.path.dirname(os.path.abspath(s.winapp2_path))
                  == os.path.abspath(bundle),
                  s.winapp2_path)


def main():
    print("=" * 64)
    print("app_paths 打包路径解析测试")
    print("=" * 64)
    test_frozen_basic()
    test_frozen_user_override()
    test_source_mode()
    test_settings_uses_writable_dir()
    print("-" * 64)
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"总计 {len(RESULTS)} 项，通过 {len(RESULTS) - len(failed)}，失败 {len(failed)}")
    for n in failed:
        print("  - " + n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
