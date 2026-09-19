# Bug 修复记录 — B1~B6（2026-09-19）

> 触发：老陶要求通读 `AboutDEPT_SYsClean` 源码后修 Bug，并指定「全部 B1–B6」。
> 回归测试：`tests/test_bugfix_b1_b6.py`（23 项，全绿）。

## 修复清单

| # | 严重度 | 位置 | 症状 | 修复 |
|---|---|---|---|---|
| B1 | 致命 | `winapp2_parser.py` `entries_to_scan_items`；`scanner.py:1202` | winapp2 条目 `path` 保持 `%LocalAppData%\...` 字面量，`_scan_path` 判为不存在 → size 恒 0 → GUI 隐藏 / CLI 过滤。598 条中 **265 条（44%）永久失效** | 构造 ScanItem 前统一 `PathExpander.expand(raw_path)` |
| B2 | 高危（安全） | `scanner.py` `CleanEngine._is_excluded` | ExcludeKey **22/22 条含 `%VAR%`** 未展开 → 排除规则永不命中 → 保护形同虚设（修完 B1 后清理量暴涨，此 Bug 会直接变成误删风险） | 新增 `_normalize_exclusions()`，`__init__` / `set_exclusions` 时一次性展开 |
| B3 | 中 | `scanner.py:1390` + `gui.py:_populate_tree` | `scan_all` 按 size 全局降序，GUI 靠「相邻项分类不同就插标题」分组 → 同一分类标题重复出现 N 次 | 抽出 `_visible_items()` / `_group_by_category()`，先聚合再渲染 |
| B4 | 中 | `scanner.py` `clean_item` | 单文件项（如 `MEMORY.DMP`）走 `os.remove` **永久删除**，与弹窗「Files moved to Recycle Bin」不符 | 改走 `_delete_to_recycle_bin()`（内部失败兜底仍为直接删除，不比原先更差） |
| B5 | 低 | `cli.py:_in_scope` / `run_cli` | `--category ""` 空串 `in` 判断恒真 → 静默升级为**全量清理** | 空串返回 False；CLI 入口 `parser.error` 显式拒绝 |
| B6 | 低 | `winapp2_parser.py` detect | Detect 线索未展开 → 详情面板/复制路径显示 `%VAR%`，双击打开文件夹失败 | 与 B1 同处展开 |

附带增强：`PathExpander.expand` 增加大小写变体正则兜底（覆盖 `%localappdata%` 之类写法）。

## 取证（修复前，只读取证脚本）

```
winapp2 解析条目数: 598
path 仍含未展开环境变量: 595
  其中【不含通配符】(必死): 265
  其中【含通配符】(会被 resolve_matches 救回): 330
必死条目中，展开后真实存在的数量: 265   ← 修复后这 265 条立刻可扫
排除规则含未展开环境变量: 22/22
```

根因：展开只发生在「含通配符」的那条分支（`scanner.py:1191`），不含通配符的分支
（`scanner.py:1202`）直接 append 原始 `%VAR%` 路径。

## 验证

| 项 | 结果 |
|---|---|
| `tests/test_bugfix_b1_b6.py` | 23/23 PASS |
| 端到端 `main.py --scan --report` | 1m32s，exit 0；扫描目标 2331、可清理 505 项、66.29 GB，**「第三方应用」6.79 GB** |
| 6 个源文件语法编译 | 全部 PASS |

**未验证项**：GUI 无头环境无法启动（tkinter 窗口未实测），B3 只测了抽出的分组/过滤函数，
未做真实 Treeview 渲染验证。

## 环境注意

- WorkBuddy managed Python 3.13.12 **不含 tkinter**，本项目必须用系统
  `C:\Users\missi\AppData\Local\Programs\Python\Python310\python.exe` 运行。
