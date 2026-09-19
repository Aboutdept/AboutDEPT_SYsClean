# SysClean

**面向 CG / 虚拟制片 / AIGC 工作流的 Windows 垃圾清理器**
一个认识 Unreal、Unity、Houdini、Nuke、ComfyUI 缓存路径的开源清理工具 —— 通用清理器找不到的那几十 GB，它找得到。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6)
![License](https://img.shields.io/badge/License-MIT-green)
![Rules](https://img.shields.io/badge/Rules-3%2C911-orange)
![GUI](https://img.shields.io/badge/UI-tkinter%20Dark-4B8BBE)
![No registry](https://img.shields.io/badge/Registry-Never%20touched-brightgreen)

---

## 30 秒了解

| | |
|---|---|
| **它是什么** | 纯 Python + tkinter 的 Windows 垃圾扫描/清理工具，单文件 exe，无需安装 |
| **和 CCleaner 的区别** | 规则库按 CG 行业软件重写：Unreal / Unity / Houdini / Nuke / Resolve / ComfyUI / Stable Diffusion 的缓存路径它认识，通用工具不认识 |
| **能清多少** | 实测开发机 **79 GB**（内置 99 项 + CG/AIGC 规则库 91 条 + winapp2 社区库 3,721 条） |
| **安全吗** | 只删文件、**从不写注册表**；默认移入回收站；支持排除规则；有审计日志；CLI 默认干跑 |
| **怎么用** | 双击 `SysClean.exe` → Scan → 勾选 → Clean Selected |

一次真实扫描的输出（节选）：

```
[info] winapp2 数据库: 596 条已安装 App 条目
可回收空间   : 69.14 GB
    Read-Only Info  52.41 GB     Dev Tools       8.36 GB
    System Logs      3.56 GB     第三方应用       2.95 GB
    App Cache        1.38 GB     AIGC           61.91 MB
    Unreal Engine    1.39 MB     Windows Update  38.77 MB
```

---

## 一、它解决什么问题

做 CG 的人对 C 盘的体感是：**什么都没装，盘就红了**。原因是行业软件的缓存策略普遍「只写不扫」：

| 场景 | 典型占用 |
|---|---|
| Unreal Engine 派生数据缓存 / 崩溃转储 | 单个项目 5–40 GB |
| Unity ShaderCache / Library / Asset 导入缓存 | 每个工程 1–10 GB |
| Houdini 临时与崩溃日志 | 长期累积数 GB |
| Nuke / Foundry 缓存与日志 | 数 GB |
| ComfyUI / Stable Diffusion 临时与输出 | 数十 GB |
| Hugging Face 模型缓存（`~/.cache/huggingface`） | 单个模型 2–20 GB，**默认不自动清理** |
| GPU 着色器缓存（D3DSCache / NV_Cache / AMD / Intel） | 数 GB |
| Adobe 媒体缓存、PTX 索引、CEP 缓存 | 数 GB |

通用清理器（Windows 磁盘清理、CCleaner 默认规则）**不认识这些路径** —— 它们是为「浏览器 + Office + 系统临时文件」设计的。结果就是：真正占空间的东西一个没清，清掉的只有几十 MB。

SysClean 的做法是：**规则库按行业重写**。内置项覆盖系统与通用软件，`Databases/CG_AIGC.ini` 覆盖 CG / VP / AIGC 全链路，`Winapp2.ini` 兜底数千款通用 App。

---

## 二、对 CG / 虚拟制片 / AIGC 从业者的意义

| 角色 | 痛点 | SysClean 的作用 |
|---|---|---|
| **三维 / 渲染** | UE、Unity、Houdini、C4D、Blender 工程缓存堆积，多项目并行时 C 盘迅速见底 | 精确识别 ShaderCache / DerivedDataCache / 崩溃转储 / 临时目录，按项目清理而不动工程文件 |
| **后期 / 合成** | Nuke、Resolve、Fusion、Adobe 媒体缓存与 PTX 索引长期不清理 | 命中媒体缓存、预览缓存、日志目录，回收数 GB 而不影响素材 |
| **虚拟制片** | TouchDesigner、Notch、Aximmetry、Disguise 的现场日志与缓存累积 | 内置 VP & Broadcast 分类（8 项）+ 规则库 5 项，现场机器可定期清理 |
| **AIGC / 模型** | ComfyUI、SD-WebUI、Hugging Face、Ollama、Torch Hub 的模型与临时缓存动辄数十 GB | AIGC 分类 18 条规则，含 HF Hub / Xet、Gradio、Whisper、Ultralytics、Topaz |
| **IT / 机房维护** | 批量维护渲染农场的系统盘 | CLI + 任务计划程序静默清理，审计日志可追溯每次删除 |
| **自由创作者** | 不想装 CCleaner，不想被捆绑安装 | 单文件 exe，绿色便携，无联网、无广告、无遥测 |

**三条设计原则**（决定了它和"优化大师"类软件的区别）：

1. **不做注册表优化。** 只解析并执行文件/目录清理规则；winapp2 库中的 `RegKey` 一律忽略。注册表"优化"是收益极低、风险极高的一类操作。
2. **只移回收站，不直接删除。** 误删可从回收站还原。
3. **未安装或路径不存在的条目自动隐藏。** 不产生噪音，也绝不会被清理。

---

## 三、快速开始

### 方式一：直接用 exe（推荐）

从 Releases 下载 `SysClean.exe`，双击运行：

1. 点 **Scan** 扫描（约 1–2 分钟）
2. 勾选要清理的项（可按风险等级筛选）
3. 点 **Clean Selected** → 确认对话框 → 清理

> 清理系统目录项可能需要管理员权限，建议右键「以管理员身份运行」。

### 方式二：源码运行

```bat
git clone <your-repo-url>
cd SysClean
python main.py
```

要求：**Python 3.8+ 且带 tkinter**（python.org 官方安装包默认带；部分精简发行版没有）。
仅依赖标准库，无需 pip install。

---

## 四、清理范围

规则来源三路，合计 **3,911 条**：

| 来源 | 条数 | 说明 |
|---|---|---|
| 内置（`scanner.py`） | 99 | 系统 + 通用软件 + CG 基础项，随代码维护 |
| `Databases/CG_AIGC.ini` | 64 | **本项目自研**：CG / 后期 / VP / AIGC / GPU 着色器 |
| `Databases/Dism_System.ini` | 27 | 提取自 Dism++ 的纯文件型清理项（详见 `NOTICE.md`） |
| `Winapp2.ini` | 3,721 | winapp2 社区数据库（CC-BY-SA-4.0，详见 `NOTICE.md`） |

### 4.1 CG 与后期（`Databases/CG_AIGC.ini`，34 条）

| 软件 | 清理内容 |
|---|---|
| **Unreal Engine** | 崩溃转储、Saved 日志与缓存（另含内置 7 项） |
| **Unity** | ShaderCache、Hub 下载缓存、Asset 导入缓存、编辑器日志 |
| **Godot** | 项目缓存 |
| **Omniverse** | 缓存、日志 |
| **Maya** | 本地缓存、崩溃日志 |
| **3ds Max** | 自动备份（autoback） |
| **MotionBuilder** | 缓存 |
| **Cinema 4D (Maxon)** | 缓存 |
| **Blender** | 临时文件 |
| **Houdini** | 临时目录、崩溃与日志 |
| **Nuke / Foundry** | 临时与日志、应用缓存 |
| **Redshift** | 日志与缓存 |
| **V-Ray / Corona / Arnold** | 渲染缓存（含 Chaos 新版路径） |
| **Substance 3D** | 缓存（含旧版 Allegorithmic） |
| **DaVinci Resolve / Fusion** | 缓存、日志 |
| **Adobe 全家桶** | 媒体缓存、PTX 索引、CEP 缓存、CRLogs、Media Encoder 日志、Lightroom 预览缓存 |

### 4.2 AIGC（18 条）

ComfyUI（临时 / C 盘根目录临时 / 日志）、Stable Diffusion WebUI、Fooocus、Gradio、
**Hugging Face 模型缓存 + Xet 缓存**、Torch Hub、Whisper、Ultralytics、
Ollama、LM Studio、AnythingLLM、Topaz（缓存与日志）、
Agisoft Metashape、RealityCapture。

> Hugging Face 缓存标为 `caution`（需谨慎）：模型文件体积大，删除后需重新下载。

### 4.3 虚拟制片（5 条）+ 媒体（2 条）

TouchDesigner（缓存 / 日志）、Notch、Aximmetry、Disguise；OBS Studio 日志、VLC 缓存。

### 4.4 GPU 着色器缓存（5 条）

DirectX `D3DSCache`、NVIDIA `NV_Cache`、AMD 着色器缓存 / OpenGL 缓存、Intel 着色器缓存。

### 4.5 系统与开发（内置 + Dism++ 派生）

| 分类 | 内容 |
|---|---|
| Temp Files | Windows 临时、用户临时 |
| Windows Update | 更新下载缓存、CBS 临时、WinSxS 清单缓存 |
| System Logs | CBS / DISM / Panther、Defender 扫描历史、LiveKernelReports、WinSAT |
| System Cache | 缩略图缓存、Prefetch、INetCache/Cookies、字体缓存、UWP AC Temp |
| Crash Reports | 应用崩溃转储、Windows 错误报告 |
| Browser Cache | Chrome / Edge 缓存与 Code Cache |
| Dev Tools | npm、pip、NuGet、VS Package Cache、.NET Native Images、JetBrains 日志 |
| Other | 驱动安装临时、零售演示离线内容、NVIDIA 驱动下载缓存 |

---

## 五、安全设计

| 机制 | 说明 |
|---|---|
| **不碰注册表** | 从不读写注册表；winapp2 的 `RegKey` 全部忽略 |
| **只进回收站** | 文件与目录统一走 Shell 回收站 API，可还原 |
| **排除规则** | winapp2 自带 `ExcludeKey` + 用户「全局排除」列表，命中即跳过并记日志 |
| **风险分级** | `safe` / `medium` / `caution` 三档，危险项在确认框红色警示 |
| **只读标记** | 无权限或受保护项标 🔒，不可勾选清理 |
| **安装检测** | 未安装软件的条目自动隐藏，杜绝误伤 |
| **删后校验** | 删除失败不虚报释放空间、不写审计日志 |
| **CLI 干跑** | 命令行默认只打印计划，必须显式 `--yes` 才真删 |
| **审计日志** | 每次实际删除追加 `SysClean_cleanup.log`（TSV：时间/类型/名称/路径/大小） |
| **崩溃可见** | 打包 exe 无控制台，异常写入 `logs/crash-*.log` 并弹窗，绝不静默失败 |

---

## 六、架构与文件结构

```
SysClean/
├── main.py              # 入口：无参数 → GUI；带参数 → CLI
├── gui.py               # tkinter 暗色 GUI（扫描树 / 详情 / 日志 / 设置 / 确认对话框）
├── scanner.py           # 扫描引擎 + 清理引擎 + 报告生成 + 规则加载
├── cli.py               # 命令行（--scan / --clean / --auto / --report）
├── settings.py          # 设置持久化（settings.json）
├── app_paths.py         # 打包感知路径层（只读数据 vs 可写数据分离）
├── winapp2_parser.py    # Winapp2.ini 解析器
├── Winapp2.ini          # 社区数据库（3,721 条）
├── Databases/
│   ├── CG_AIGC.ini      # 自研：CG / VP / AIGC / GPU（64 条）
│   └── Dism_System.ini  # 源自 Dism++（27 条）
├── Custom/              # 用户自定义规则（放 .ini 即生效，无需改代码）
├── tests/               # 回归测试（5 套，84 项断言）
├── tools/               # 未定义名静态扫描 + 全量回归入口
├── docs/                # 设计、调研、迭代、Bug 修复记录
├── icon.ico / run.bat / build_exe.bat / *.spec
├── LICENSE              # MIT 全文（项目代码）
├── NOTICE.md            # 第三方数据来源与许可
├── CONTRIBUTING.md      # 贡献指南（含规则语法与安全红线）
├── .gitignore           # 忽略 __pycache__ / build / dist / logs / 运行时数据
└── .gitattributes       # 行尾规范化（.bat=CRLF，其余=LF）
```

**数据流**：

```
规则三源（内置 / Databases / Winapp2.ini / Custom）
        ↓  PathExpander 展开 %LocalAppData% 等环境变量
        ↓  DetectionService 安装检测（路径存在 or 注册表键）
ScanEngine.scan_all()  →  ScanItem 列表（大小 / 风险 / 文件数 / 子项）
        ↓
GUI 按分类聚合展示（或 CLI 过滤）
        ↓  CleanEngine（排除规则 → 回收站 → 删后校验 → 审计日志）
        ↓
ReportGenerator（TXT / JSON / CSV）
```

**关键模块**：

- `PathExpander` —— 统一展开 `%LocalAppData% %AppData% %ProgramData% %ProgramFiles% %ProgramFiles(x86)% %UserProfile% %SystemRoot% %SystemDrive% %System% %Public% %OneDrive% %Temp% %Documents% %Videos% %Pictures% %Desktop%`，并兼容大小写变体（如 `%localappdata%`）。
- `app_paths.py` —— **打包后正确运行的关键**。PyInstaller onefile 下 `__main__.__file__` 指向每次随机的 `_MEIxxxxxx` 临时目录，若沿用会导致设置/日志每次启动丢失。这里把「只读数据」(`data_dir`) 与「可写数据」(`writable_dir`) 分离。

---

## 七、编译与打包

### 7.1 环境

```bat
python --version          :: 3.8+ ，必须是带 tkinter 的 CPython
python -c "import tkinter"   :: 不报错即可
pip install pyinstaller
```

> WorkBuddy / 部分精简 Python **没有 tkinter**，用它打包会得到「能构建但启动即崩」的 exe。
> `build_exe.bat` 会先校验 tkinter 与 PyInstaller，缺一即停止。

### 7.2 构建

```bat
build_exe.bat          :: 只出 dist\SysClean.exe       （GUI，无控制台）
build_exe.bat /all     :: 另出 dist\SysClean_CLI.exe   （带控制台，供命令行/计划任务）
```

两个都是 **onefile**（单文件，约 8.5 MB），图标为 `icon.ico`。
可用 `set SYSCLEAN_PYTHON=<python.exe>` 指定解释器。

等价的直接调用：

```bat
python -m PyInstaller SysClean.spec      --noconfirm --clean
python -m PyInstaller SysClean_CLI.spec  --noconfirm --clean
```

### 7.3 spec 要点

`datas` 必须内嵌，缺了规则库就全废：

```python
datas = [('Winapp2.ini', '.'), ('icon.ico', '.'),
         ('Databases', 'Databases'), ('Custom', 'Custom')]
console   = False          # GUI 版；CLI 版为 True
icon      = 'icon.ico'
excludes  = ['numpy', 'scipy', 'PIL', 'PyQt5', 'PySide6', 'matplotlib', 'pandas']
```

> 为什么出两个 exe：Windows 下无控制台进程拿不到 stdout，纯 GUI 版无法使用
> `--scan --report`。两者同为单文件、互不依赖。

### 7.4 覆盖内置规则库（免重新打包）

把 `Databases/` 或新版 `Winapp2.ini` **放在 exe 旁边**即可覆盖内置版本 —— `data_dir()` 优先取 exe 目录。

---

## 八、部署与自动化

### 8.1 命令行用法

```bat
:: 只扫描并导出报告（不删任何文件）
SysClean_CLI.exe --scan --report report.json
SysClean_CLI.exe --scan --report report.csv

:: 干跑：打印计划，不实际删除
SysClean_CLI.exe --auto

:: 真正执行（用 GUI 中保存的选择）
SysClean_CLI.exe --auto --yes --log cleanup.log

:: 按分类清理
SysClean_CLI.exe --clean --category "Temp Files" --yes
SysClean_CLI.exe --clean --all --yes --report summary.txt
```

| 参数 | 作用 |
|---|---|
| `--scan` | 仅扫描出报告 |
| `--clean` | 清理（配合 `--all` / `--category` / `--selected` / `--auto`） |
| `--auto` | 用设置里保存的选择（等同 `--clean --selected`） |
| `--yes` | **确认删除**；缺省一律干跑 |
| `--report <path>` | `.json` / `.csv` / `.txt` |
| `--log <path>` | 审计日志路径 |
| `--db` / `--no-db` | 是否启用 CG/AIGC 规则库 |
| `--winapp2` / `--no-winapp2` | 是否启用社区库 |

### 8.2 定时清理（渲染农场 / 工作站的常规做法）

1. 任务计划程序 → 创建基本任务（如每日 03:00）
2. 操作：启动程序 → `SysClean_CLI.exe`
3. 参数：`--auto --yes --log "%APPDATA%\SysClean\cleanup.log"`
4. 起始位置：exe 所在目录
5. **先不加 `--yes` 跑一次**确认计划合理，再启用自动删除

### 8.3 便携部署

设置、审计日志、崩溃日志默认写 **exe 同目录**（便携模式）；目录不可写时自动退回 `%APPDATA%\SysClean`。
把 exe 与 `Databases/`、`Custom/` 一起放进 U 盘即可带走全部配置。

---

## 九、开发工作流

### 9.1 跑测试

```bat
python tools\run_all_tests.py
```

依次执行 5 套测试 + 未定义名静态扫描 + 6 个源文件语法编译，结果落盘 `logs/regression-latest.log`：

| 套件 | 项数 | 覆盖 |
|---|---|---|
| `tests/test_bugfix_b1_b6.py` | 26 | 路径展开、排除保护、分类分组、回收站、CLI 边界 |
| `tests/test_db_rules.py` | 24 | 规则库解析、确认框几何（3 项与 300 项等高等宽） |
| `tests/test_clean_flow.py` | 15 | Clean Selected 点击链路、异常恢复 |
| `tests/test_app_paths.py` | 12 | frozen/源码下的路径解析 |
| `tests/test_gui_smoke.py` | 7 | 真实 Tk 窗口 + 真实 mainloop 冒烟 |

### 9.2 两条防「静默失效」的防线

GUI 程序在 `pythonw` / 打包 exe 下没有控制台，异常会被吞掉，表现为「点了没反应」：

1. **静态扫描** — `python tools/check_undefined_names.py`（AST 迷你 pyflakes，处理 lambda / 推导式 / 注解赋值 / global），提交前发现未定义名
2. **运行时兜底** — `report_callback_exception` + `sys.excepthook`，任何异常必弹窗并写 `logs/`

### 9.3 新增一条规则（无需改代码）

在 `Custom/` 放 `.ini`（winapp2 子集 + 本项目扩展）：

```ini
[My Renderer Cache]
DetectFile=%LocalAppData%\MyRenderer
Category=CG & Post-Production
Risk=safe
FileKey1=%LocalAppData%\MyRenderer\Cache|*.tmp;*.cache|RECURSE
```

- `DetectFile` —— 安装检测，不存在则该项自动隐藏
- `FileKey1=路径|通配模式|RECURSE` —— 只删匹配模式的文件
- `REMOVESELF` —— 清空整个目录
- 文件名以 `.disabled` 结尾则忽略

---

## 十、文档索引

| 文档 | 内容 |
|---|---|
| `docs/01_参考分析_FluentCleaner.md` | 参考项目分析 |
| `docs/02_外部清理修复工具调研.md` | 主流清理工具调研 |
| `docs/03_SysClean现状与差距分析.md` | 立项时的差距分析 |
| `docs/04_迭代开发计划.md` | 迭代规划 |
| `docs/05~07_迭代N执行记录.md` | 各迭代实现记录 |
| `docs/08_Bug修复记录_B1-B6.md` | 路径展开 / 排除保护 / 分类重复 / 回收站 / CLI 边界 |
| `docs/09_规则数据库与UI修复.md` | CG/AIGC 规则库 + 确认框固定高度 |
| `docs/10_CleanSelected无响应修复.md` | 点击无反应的根因与两道防线 |
| `docs/11_打包为单个exe.md` | 打包路径层 Bug 与验证证据 |

---

## 十一、已知限制

- 单文件 exe 每次启动需解压到临时目录，首次启动比源码模式慢 1–3 秒
- PyInstaller onefile 可能被杀软误报（已知现象；必要时改用 onedir 或 Nuitka）
- `Databases/Dism_System.ini` 只取 Dism++ 的**纯文件/目录**清理项；注册表、WinSxS 组件清理、系统还原点、Appx 卸载一律不采用
- 清理系统目录项可能需要管理员权限
- Hugging Face / 模型类缓存删除后需重新下载，已标 `caution`

## 十二、路线图

- 空间分析 Tab（WizTree 式，找大文件夹）
- 重复文件查找
- 卸载残留扫描
- 英文界面

---

## 十三、许可与第三方数据

**代码：MIT**（见 `LICENSE`）。

第三方数据来源与许可详见 **`NOTICE.md`**，摘要：

| 文件 | 来源 | 许可 |
|---|---|---|
| `Winapp2.ini` | [MoscaDotTo/Winapp2](https://github.com/MoscaDotTo/Winapp2) | **CC-BY-SA-4.0**（署名 + 相同许可再分发） |
| `Databases/Dism_System.ini` | 提取自 [Chuyu-Team/Dism-Multi-language](https://github.com/Chuyu-Team/Dism-Multi-language) 的 `Data.xml` | **MIT**（Chuyu-Team, 2016） |
| `Databases/CG_AIGC.ini` | 本项目自研 | MIT |

---

## 免责声明

清理操作有风险。本工具默认移入回收站、提供干跑模式与排除规则，但**不保证任何删除操作的安全性**。建议首次使用时先只扫描、人工核对路径，再小批量清理；重要数据请先备份。
