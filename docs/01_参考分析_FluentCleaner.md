# 参考分析：FluentCleaner（Ref/FluentCleaner-main）

> 分析目的：理解 FluentCleaner 的扫描目录、扫描类型与清理机制，提取可提升 SysClean 的设计。
> 分析对象：`D:\Builds\AboutDEPT_SYsClean\Ref\FluentCleaner-main`
> 分析日期：2026-07-12

---

## 1. 核心结论：它是"数据驱动"的，而不是"硬编码目录"的

SysClean 当前把 ~80 个扫描目标**写死在源码**（`scanner.py` 的 `get_scan_targets()`）。
FluentCleaner 恰恰相反：**源码里几乎没有具体扫描目录**，真正的扫描目录/类型来自一个外部数据库 `Winapp2.ini`（社区维护 15 年、本次随包附带 **3721 条规则**、CC-BY-SA-4.0 许可）。

这意味着：

- **扫描"什么"由数据决定**，不是由代码决定；
- 新增一个 App 的清理规则 = 往 `Winapp2.ini` 加一段文本，**不用改 C# 代码、不用重新编译**；
- 用户还能放自己的 `Custom/*.ini`，走同一套解析+检测逻辑。

> 对 SysClean 的启示：**把"扫描目标"从源码里解耦出来**，是 FluentCleaner 最值得借鉴的架构思想。

---

## 2. FluentCleaner 实际"扫描"了哪些目录与类型

因为目录来自数据库，下面按 `Winapp2.ini` 的真实覆盖分类（只列与 SysClean 相关的）：

### 2.1 它**已经覆盖**的影视 / CG / VP 相关应用（实测 grep 命中）

| 应用 | 在 Winapp2.ini 中的条目示例 | 说明 |
|------|------------------------------|------|
| Adobe 全家桶 | `Adobe After Effects *`、`Adobe Premiere Pro *`、`Adobe Media Encoder *`、`Adobe Photoshop *`、`Adobe Audition *`、`Adobe Illustrator *`、`Adobe Lightroom *`、`Adobe Bridge *` 等 | 覆盖非常全，且按功能拆成多条精细规则 |
| Blackmagic Design | `Blackmagic Design DaVinci Resolve *` | 有，但 SysClean 的覆盖更细（CacheClip/代理/调色/静帧） |
| Blender | `Blender *` | 有 |
| NVIDIA | `NVIDIA Shader Cache *`、`NVIDIA App *`、`NVIDIA Broadcast *`、`NVIDIA Omniverse *`、`NVIDIA GeForce Experience *` 等 10+ 条 | 比 SysClean 更全 |
| OBS Studio | `OBS Studio *` | SysClean 未覆盖 |
| V-Ray | `V-Ray *` | 有 |
| Autodesk | `Autodesk AutoCAD *`、`Autodesk Revit *`、`Autodesk Inventor *`、`Autodesk Installer *` | 注意：**未搜到 Maya / 3ds Max**，SysClean 反而有 Maya |

### 2.2 它**没有覆盖**、但 SysClean 已经定制好的垂直条目

这是 SysClean 的差异化优势，FluentCleaner（通用工具）和 winapp2 都薄弱：

- Unreal Engine 系列（winapp2 只有 `Unreal Tournament` **游戏**，不是引擎）→ SysClean 有 DDC / ShaderCache / Intermediate / AutoSaved / CrashReports
- Houdini、Nuke、Cinema 4D、Redshift、Octane
- Aximmetry、Disguise、Pixotope、Hecoos（纯 VP 虚拟制作）
- 腾讯/微信、各类直播/会议缓存（SysClean 的 App Cache 是国内场景特色）

> 结论：**两者互补**。SysClean 的"VP 垂直深度"该保留并继续加强；winapp2 的"通用广度"可作为可插拔数据库补充。

---

## 3. 数据格式：Winapp2.ini 一条规则长什么样

```ini
[App Name *]
LangSecRef=3021          ; 分类码（映射到 UI 分组）
Detect=HKLM\Software\MyApp
DetectFile=%LocalAppData%\MyApp
SpecialDetect=DET_CHROME ; 知名 App 的简写检测
Warning=This removes saved passwords
Default=False            ; 是否默认勾选
FileKey1=%AppData%\MyApp|*.log;*.tmp        ; 路径|分号分隔的模式
FileKey2=%AppData%\MyApp\Cache|*|REMOVESELF ; RECURSE 递归 / REMOVESELF 删空目录
RegKey1=HKCU\Software\MyApp\MRU
ExcludeKey1=FILE|%AppData%\MyApp\|important.db ; 即使匹配也跳过
```

关键字段含义（详见同目录 `Winapp2-Format_EN.md`）：

| 字段 | 作用 |
|------|------|
| `Detect` / `DetectFile` / `SpecialDetect` | **安装检测**，OR 逻辑；一条都不命中则整条规则隐藏 |
| `FileKeyN=路径\|模式\|[RECURSE\|REMOVESELF]` | 删除哪些文件；支持递归、删后清理空目录、分号多模式 |
| `RegKeyN` | 删除注册表键/值（FluentCleaner 仍支持，但 SysClean 可选择性忽略） |
| `ExcludeKeyN` | 保护重要文件，即使被 FileKey 命中也跳过 |
| `LangSecRef` | 分类码（3021=应用、3025=Windows、3029=Chrome…） |
| `Warning` / `Default` | 风险提示 + 是否默认勾选 |

**路径变量**：`%AppData% %LocalAppData% %LocalLowAppData% %ProgramFiles% %ProgramFiles(x86)% %ProgramData% %UserProfile% %SystemRoot% %System% %Temp% %Documents% %Desktop% %Videos%` 等，且 `%ProgramFiles%` 会自动尝试 x86 变体。

---

## 4. FluentCleaner 的核心机制（对应源码）

| 模块 | 文件 | 干什么 | 对 SysClean 的借鉴 |
|------|------|--------|--------------------|
| **解析器** | `Winapp2Parser.cs` | 把 ini 文本解析成 `CleanerEntry`（支持 FileKey/RegKey/ExcludeKey/Detect 的编号多值键） | 用 Python 写一个等价的 `winapp2_parser.py` |
| **安装检测** | `DetectionService.cs` | 按 Detect/DetectFile/SpecialDetect 判断 App 是否安装；**未安装→隐藏该项** | SysClean 应只在"App 已安装"时才显示扫描项，消灭"一堆 Not found" |
| **路径展开** | `PathExpander.cs` | 展开 `%变量%` + 递归解析含 `*` 的路径段 | SysClean 目前用手写 `os.environ`，可统一为展开器 |
| **分类解析** | `CategoryResolver.cs` | LangSecRef 码 → 分类名 + 排序 | SysClean 已有中文分类，可保留 |
| **自定义规则** | `CustomEntryService.cs` | 加载 `Custom/*.ini`，同样走检测+解析；`.disabled` 关闭 | SysClean 加一个 `Custom/` 目录，让用户加自己的工具缓存 |
| **AI 解释** | `AiExplainer.cs` | 调 Groq，用真实路径解释每条规则（需 API key） | 可选；SysClean 已有详尽中文 description，优先级低 |
| **命令行** | `CliCleanerModule.cs` | `clean/analyze/scan/list/categories`，支持 `all`/`selected`/`category <名>` | SysClean 缺 CLI，无法做计划任务自动清理 |
| **设置持久化** | `AppSettings.cs` | 保存选择/数据库开关/全局排除/窗口大小/清理历史/语言；**支持便携模式**（exe 旁放 settings.json） | SysClean 当前无持久化，每次重选 |
| **清理方式** | `CleaningService.cs` | 直接删除（非回收站）；强调"精确删除特定文件"，而非通配整目录 | 与 SysClean 的"回收站防误删"理念不同，但"精确删除"思路可吸收（用 ExcludeKey 保护） |

---

## 5. FluentCleaner 的产品哲学（值得 SysClean 对齐）

README 明确反对的"行业噪音"，正好是可借鉴的**负面清单**：

1. **不做注册表"优化"清理** —— 认为 orphaned key 对性能零影响、误删风险高（安慰剂 vs 变砖）。SysClean 当前也没有注册表清理，应继续保持。
2. **不做多次覆写"安全删除"（DoD 7-pass / Gutmann 35-pass）** —— 作者指出 SSD 有 wear-leveling/TRIM，软件覆写无效，属"安全剧场"。SysClean 若要加"擦除"，必须标注 SSD 无效。
3. **不做功能膨胀 / 诱导广告 / VPN 推销** —— 保持工具聚焦。
4. **只删"明确是垃圾"的东西**（缓存、临时文件、残留日志），且每条规则**精确、可审计、不扫整盘**。

> SysClean 已有的"风险分级 + 回收站 + 只读保护 + 中文说明"完全契合这一哲学，应延续。

---

## 6. 对 SysClean 可落地的借鉴点（提炼）

| # | 借鉴点 | 价值 | 风险 |
|---|--------|------|------|
| 1 | 数据驱动 + 可插拔 winapp2 数据库 | 覆盖从 80 条 → 数千条，且可审计 | 中（需写解析器） |
| 2 | 安装检测（只显示已装 App） | 消灭"Not found"噪音、扫描更快 | 低 |
| 3 | 自定义规则文件夹 `Custom/` | 用户自行加 VP 工具缓存，无需改源码 | 低 |
| 4 | CLI / 自动模式 | 可做计划任务夜间自动清理 | 低 |
| 5 | 设置持久化 + 便携 | 记住选择/窗口，体验更好 | 低 |
| 6 | 全局排除（ExcludeKey） | 重要文件不被误删 | 低 |
| 7 | 路径变量展开 + 通配符 | 规则更简洁、更准 | 低 |
| 8 | 逐条精确删除 + 排除保护 | 比"整目录删除"更安全 | 低 |
| 9 | 清理历史 / 日志文件 | 可追溯、可审计 | 低 |

下一份文档：`02_外部清理修复工具调研.md`（互联网上的主流工具能再补什么）。
