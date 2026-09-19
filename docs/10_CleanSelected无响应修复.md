# Bug 修复记录：Clean Selected 点击无反应

日期：2026-09-19
影响：GUI 主功能完全不可用（扫描正常，清理无法触发）
严重度：**致命**

---

## 一、根因

`gui.py::_start_clean()` 在把 `messagebox.askyesno` 换成自定义 `ConfirmDialog`
（固定高度 + 滚动条改造）时，**误删了三个变量的计算**：

```python
total_size  = sum(i.size_bytes for i in items_to_clean)
has_caution = any(i.risk_level == "caution" for i in items_to_clean)
has_medium  = any(i.risk_level == "medium"  for i in items_to_clean)
```

而新的 `ConfirmDialog(...)` 仍在引用它们 → 点击按钮立即 `NameError`。

**为什么"无效果"而不是报错**：程序以 `pythonw` / 打包 exe 启动，没有控制台，
tkinter 回调异常默认只写 stderr，被彻底吞掉。用户侧表现为点击后界面毫无变化。

### 复现路径
1. 扫描完成
2. 选中任意条目
3. 点击 `Clean Selected`
4. 无任何弹窗、无日志、无进度变化

---

## 二、修复清单

| # | 文件 | 改动 |
|---|---|---|
| F1 | `gui.py::_start_clean` | 补回 `total_size` / `has_caution` / `has_medium` 计算 |
| F2 | `gui.py::__init__` | 安装 `root.report_callback_exception = self._on_tk_error`，tkinter 回调异常不再静默：写日志面板 + 弹错误框 + 恢复按钮状态 |
| F3 | `gui.py::_clean_worker` | 整个清理循环包 try/except；异常回到 `_on_clean_complete(freed_total, err)`，标记 `Clean Failed` 并弹错，不再让界面卡在 `Cleaning...` |
| F4 | `gui.py::_clean_selected` | 右键单项清理同样加异常兜底 |
| F5 | `gui.py::_finish_clean` | 工作线程 `root.after` 抛 `RuntimeError('main thread is not in main loop')` 时兜底为同步收尾 |
| F6 | `main.py` | 安装 `sys.excepthook`：未捕获异常写入 `logs/crash-*.log` 并弹错误框（exe 无控制台时可见） |

### F5 说明（真实存在的次生隐患）
工作线程中调用 `root.after()`，若主线程当时不在 `mainloop`（例如窗口正在重建、
或程序处于非标准事件循环状态），tkinter 会抛 `RuntimeError`。该调用原先位于
try 之外 → 线程直接死亡 → `Cleaning...` 永久卡住，同样是"点了没反应"。
现已封装为 `_finish_clean()`，after 失败时降级为同步收尾。

---

## 三、新增防回归工具

| 文件 | 作用 |
|---|---|
| `tools/check_undefined_names.py` | 轻量未定义名扫描（mini-pyflakes）。基于 AST，处理 lambda 参数、推导式变量、注解赋值、`global/nonlocal`、with-as、except-as，避免误报 |
| `tools/selftest_checker.py` | 扫描器自检：必须能检出 `total_size/has_caution/has_medium` 形态，且对正常代码零误报 |
| `tools/run_all_tests.py` | 全量回归入口：4 套测试 + 静态扫描 + 6 个源文件编译，结果落盘 `logs/regression-latest.log` |
| `tests/test_clean_flow.py` | 15 项：点击链路不抛异常、确认框明细/合计/危险标记、线程收尾、异常恢复 |
| `tests/test_gui_smoke.py` | 7 项：**真实 Tk 窗口**下构造 `SysCleanApp` → 填树 → 选中 → 点击 → 收尾（真实 mainloop 泵事件） |

> 设计原则：这类"静默失效"必须有两道防线 ——
> **静态扫描**（提交前发现未定义名）+ **运行时兜底**（异常必弹窗/写日志，绝不静默）。

---

## 四、验证结果

```
--- B1–B6 修复           exit=0  总计 25 项，失败 0 项
--- 规则数据库            exit=0  总计 24 项，失败 0 项
--- Clean 点击链路        exit=0  总计 15 项，通过 15，失败 0
--- GUI 真实窗口冒烟      exit=0  总计 7 项，通过 7，失败 0
--- 静态扫描自检          exit=0
--- 未定义名扫描          exit=0  扫描 6 个文件，可疑未定义名 0 处
--- 语法编译              main/gui/scanner/cli/settings/winapp2_parser 全部 OK
====== 全部通过
```

关键断言：
- 点击 `Clean Selected` 不再抛 `NameError`，确认框收到 2 项明细、合计 `3.00 KB`、caution 触发危险标记
- 清理线程收尾后 `progress_label = Clean Complete`、`stat_freed = 5.00 MB`、按钮恢复 `normal`
- 清理过程注入 `RuntimeError` 后：不向上抛、按钮恢复、标记 `Clean Failed`、日志含错误原文
- 确认框 3 项与 300 项高度恒为 474px（不超屏）

## 五、五道门状态

- **Test-Driven** ✅ 测试先写，71 项断言全绿后才报完成
- **Security-First** ✅ 全程只读取证 + 桩拦截删除，未动任何用户文件；未放宽权限
- **Immutability** ⚠️ `gui.py` / `main.py` 为就地修改（修 Bug 常规做法），新增文件均为新增
- **Plan Before Execute** ✅ 先定位根因再动手
- **Agent-First** — 未派子代理（改动为定位修改，派发收益低于开销）

## 六、未验证项（不粉饰）

- 未做真实桌面会话的鼠标点击截图确认（无头环境只验到真实 Tk 窗口 + 真实 mainloop 级别）
- 未验证打包成 exe 后 `logs/crash-*.log` 的写入路径行为（相对 exe 目录，需打包后实测）
