# SysClean 打包为单个 exe

日期：2026-09-19
目标：`icon.ico` 作为图标，输出**单文件（onefile）** exe。

---

## 一、结论

| 产物 | 模式 | 用途 |
|---|---|---|
| `dist/SysClean.exe` | onefile + **无控制台** | 双击使用（GUI），图标 = icon.ico |
| `dist/SysClean_CLI.exe` | onefile + **有控制台** | 命令行 / Windows 任务计划程序静默清理 |

> 为什么要两个：无控制台版双击时不会闪黑窗，但 Windows 下**无控制台进程拿不到 stdout**，
> `--scan --report` 这类 CLI 功能无法使用。因此保留一个带控制台的孪生版本供自动化使用。
> 两个都是单文件，互不依赖。

## 二、构建命令

```bat
:: 只出 GUI 版
build_exe.bat

:: 同时出 CLI 版
build_exe.bat /all
```

`build_exe.bat` 会：
1. 定位带 **tkinter** 的 Python（可用 `set SYSCLEAN_PYTHON=...` 覆盖）
2. 校验 tkinter 与 PyInstaller 存在（缺一即报错停止，不会产出半成品 exe）
3. 执行 `pyinstaller SysClean.spec --noconfirm --clean`

直接调用亦可：

```bat
python -m PyInstaller SysClean.spec --noconfirm --clean
python -m PyInstaller SysClean_CLI.spec --noconfirm --clean
```

## 三、spec 要点

`SysClean.spec` / `SysClean_CLI.spec`：

- `console=False`（GUI 版） / `True`（CLI 版）
- `icon='icon.ico'` —— 嵌入为 exe 图标
- `datas` 内嵌（**缺了规则库就全废**）：
  - `Winapp2.ini`
  - `Databases/`（CG_AIGC.ini + Dism_System.ini）
  - `Custom/`
  - `icon.ico`
- `excludes`：numpy / scipy / PIL / PyQt5 / PySide6 / matplotlib / pandas（本项目不用）
- `optimize=2`，`upx=True`（无 UPX 时自动跳过，只影响体积）

---

## 四、打包前必须修的路径 Bug（重要）

PyInstaller onefile 运行时，`sys.modules["__main__"].__file__` 指向
**每次启动都会变的临时解压目录**（`_MEIxxxxxx`）。原代码三处都以它为基准：

| 位置 | 原行为（打包后） | 后果 |
|---|---|---|
| `settings._resolve_path()` | settings.json 写进临时目录 | **每次启动设置全丢**（选择、窗口尺寸、开关） |
| `scanner.default_cleanup_log_path()` | 审计日志写进临时目录 | 清理记录全丢 |
| `scanner._base_dir()` | 规则基准指向临时目录 | 用户在 exe 旁放的 `Databases/`、`Custom/`、`Winapp2.ini` 永远读不到 |

### 修复：新增 `app_paths.py`（打包感知路径层）

| 函数 | 语义 |
|---|---|
| `is_frozen()` | 是否运行在打包 exe 中 |
| `project_dir()` | 源码模式项目根（多候选 + 特征目录校验，防 tests/ 误判） |
| `exe_dir()` | exe / 入口脚本所在目录 —— **唯一保证可写的基准** |
| `bundle_dir()` | 打包内嵌数据目录（frozen 时为 `_MEIPASS`，只读） |
| `data_dir()` | 规则数据基准：**exe 旁的覆盖优先**，否则内嵌数据 |
| `writable_dir()` | 设置/日志基准：exe 目录，不可写则退回 `%APPDATA%/SysClean` |

改造点：
- `scanner._base_dir()` → `app_paths.data_dir()`
- `scanner.default_cleanup_log_path()` → `app_paths.writable_dir()`
- `settings._project_base()` / `_resolve_path()` → `app_paths.writable_dir()`
- `settings.winapp2_path` 默认 → `app_paths.data_dir()/Winapp2.ini`；
  加载时若已保存路径不存在则自动回退默认（换机器/打包后路径变化不会失效）
- `gui._load_icon()` → 依次尝试 exe 旁 → `_MEIPASS` → `__main__` 目录 → gui.py 目录
- `main.py` → 崩溃日志写 `writable_dir()/logs/`；并把 `sys._MEIPASS` 加入 `sys.path`

**效果**：把 `Databases/` 或新版 `Winapp2.ini` 放在 exe 旁边即可覆盖内置规则库，
不需要重新打包。

---

## 五、附带修复：B1 测试的脆弱断言

打包前跑回归时发现 `B1 无通配符条目已能真实扫描到内容` FAIL。查证后确认
**不是回归，是断言脆弱**：

- `scanner._base_dir()` / `app_paths.data_dir()` 输出均正确（`D:\Builds\AboutDEPT_SYsClean`）
- 抽样前 30 条无通配符目录（`.dotnet` / `.Thumbnails` / `Adobe\CRLogs` …）**顶层恰好没有
  匹配文件** —— 内容都在子目录里，而这些 FileKey 未开 `RECURSE`，所以 size 恒为 0
  （实测 `.dotnet` 有 262 个子项但全在子目录；`Adobe\CRLogs` 本身为空）
- 实测命中率：样本 50 → 非空 7；样本 100 → 非空 27；样本 150 → 非空 50

改为统计断言（只扫一遍 100 条，同时产出两组统计）：
- 路径存在率 ≥ 55/60（实测 60/60 —— **这才是 B1 修复的直接证据**：展开前 265 条路径含 `%VAR%` 必不存在）
- 非空命中 ≥ 10/100（实测 27）

---

## 六、验证结果

### 6.1 回归（打包前）

| 项 | 结果 |
|---|---|
| 全量回归 | ✅ 26 + 24 + 15 + 12 + 7 = **84 项全绿** |
| 未定义名静态扫描 | ✅ 7 个文件 0 处 |
| 语法编译 | ✅ 6/6 |

新增 `tests/test_app_paths.py`（12 项）：用 `FrozenEnv` 伪装 `sys.frozen / _MEIPASS /
executable`，覆盖 frozen 下 `exe_dir / bundle_dir / data_dir / writable_dir`
以及 exe 旁覆盖优先级，并断言 `settings.json` 落在 exe 目录。

### 6.2 产物

```
dist\SysClean.exe      8.49 MB   (onefile, 无控制台, 图标 icon.ico)
dist\SysClean_CLI.exe  8.50 MB   (onefile, 有控制台, 图标 icon.ico)
```

### 6.3 CLI 版端到端（证明内嵌规则库生效）

```
SysClean_CLI.exe --scan --report scan.json     exit=0
  [info] winapp2 数据库: 596 条已安装 App 条目
  可回收空间   : 69.14 GB
    Read-Only Info  52.41 GB     Dev Tools     8.36 GB
    System Logs      3.56 GB     第三方应用      2.95 GB
    App Cache        1.38 GB     AIGC          61.91 MB
    Unreal Engine    1.39 MB     Windows Update 38.77 MB
```

`winapp2 596 条` + `AIGC` / `Unreal Engine` 分类命中 ⇒
`Winapp2.ini` 与 `Databases/` 均已正确内嵌并被读到。

### 6.4 GUI 版启动（证明路径层修复生效）

启动 `SysClean.exe` 后读 `dist\logs\startup.log`：

```
2026-09-20 00:04:18  mode=gui frozen=True
    exe        = D:\Builds\AboutDEPT_SYsClean\dist\SysClean.exe
    data_dir   = C:\Users\missi\AppData\Local\Temp\_MEI556442
    bundle_dir = C:\Users\missi\AppData\Local\Temp\_MEI556442
    writable   = D:\Builds\AboutDEPT_SYsClean\dist
2026-09-20 00:05:03  mode=gui frozen=True
    data_dir   = ...\_MEI608082        <-- 每次启动都变
    writable   = D:\...\dist           <-- 恒定
2026-09-20 00:07:45  mode=cli frozen=True
    data_dir   = ...\_MEI529882
    writable   = D:\...\dist
```

- GUI 进程存活 14 秒无崩溃、无 `crash-*.log`
- **三次运行临时目录各不相同**（556442 / 608082 / 529882）—— 这正是旧逻辑下
  设置与日志必然丢失的直接证据
- `writable` 始终为 exe 所在目录 —— 路径层修复生效

### 6.5 覆盖机制

把 `Databases/` 或新版 `Winapp2.ini` 复制到 exe 旁边即可覆盖内置规则库，
无需重新打包（`data_dir()` 优先取 exe 目录）。

## 七、未验证项（不粉饰）

- **GUI 关闭时保存 settings.json**：沙箱里窗口不可见，`CloseMainWindow()` 无效，
  无法触发 `WM_DELETE_WINDOW` → `_on_close()`。间接证据：`startup.log` 证明
  `writable_dir() = exe 目录`，而 `settings.path` 由同一函数派生；且
  `test_app_paths.py` 已断言 frozen 下 `settings.json` 落在 exe 目录。
  **建议老陶双击运行一次、点 Scan、关闭窗口，确认 dist 下出现 settings.json。**
- **图标在任务栏/标题栏的视觉效果**：spec 已写 `icon='icon.ico'` 且构建无警告，
  但未截图确认（无头环境无法截 GUI）。
- **UPX 是否生效**：构建日志未确认 UPX 存在与否，只影响体积。

## 八、已知限制

- **体积**：onefile 每次运行需解压到临时目录，首次启动比源码模式慢 1–3 秒。
- **UPX**：若本机无 UPX 则体积更大（不影响功能）。
- **杀软误报**：PyInstaller onefile 常被误报，属已知现象；必要时改用 onedir 或 Nuitka。
- **UAC**：清理系统目录项可能需要管理员权限，建议右键「以管理员身份运行」。
- 无控制台版崩溃不会弹控制台，依赖 `logs/crash-*.log`（已内置兜底）。
- `build.bat`（旧 Nuitka 脚本）未同步维护：它**没有**内嵌 `Databases/` 与 `Winapp2.ini`，
  直接用会产出规则库缺失的 exe。请用 `build_exe.bat`。
