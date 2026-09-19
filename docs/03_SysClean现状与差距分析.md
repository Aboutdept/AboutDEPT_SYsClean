# SysClean 现状与差距分析

> 目的：基于前两份分析（FluentCleaner 参考 + 外部工具调研），定位 SysClean 自身的能力现状与差距。
> 分析对象：`D:\Builds\AboutDEPT_SYsClean`（main.py / scanner.py / gui.py）

---

## 1. SysClean 现状（已实现）

| 维度 | 现状 |
|------|------|
| 扫描目标 | `scanner.py` 中**硬编码**约 80 个 `ScanItem`，分 **14 大类**（Temp / Windows Update / System Logs / System Cache / Browser / Dev Tools / Crash / App Cache / Other / Read-Only / Unreal / VP & Broadcast / CG & Post-Production / Win11） |
| 扫描实现 | `os.walk` 统计文件数/文件夹数/总大小；`glob` 支持有限通配（仅 Win11 Packages 用 `*`） |
| 清理实现 | `CleanEngine`：文件直接删、目录移**回收站**（SHFileOperationW），失败回退直删 |
| 风险模型 | `safe / medium / caution` 三级 + 5 个 `readonly` 项（WinSxS / Installer / pagefile / hiberfil / swapfile） |
| 界面 | tkinter 暗色主题，树形分类列表 + 详情面板 + 活动日志 + 统计卡片 |
| 报告 | TXT 文本报告 + JSON 数据报告导出 |
| 交互 | 右键菜单（打开/复制路径/清理）、双击打开、全选安全项、确认弹窗 |

### SysClean 的**差异化优势**（必须保留并加强）

1. **VP / 影视垂直深度** —— 已经定制：
   - Unreal Engine：DDC / ShaderCache / Intermediate / AutoSaved / CrashReports
   - 纯 VP：Aximmetry、Disguise、Pixotope、Hecoos
   - CG/后期：Houdini、Nuke、Maya、Cinema 4D、Redshift、Octane、V-Ray、DaVinci、AE/PR 媒体缓存与磁盘缓存
   - 这些是 FluentCleaner（通用）和 winapp2 都**覆盖薄弱甚至缺失**的部分。
2. **中文界面 + 详尽中文说明** —— 贴合目标用户。
3. **风险分级 + 只读保护 + 回收站防误删** —— 与 FluentCleaner 哲学一致，体验甚至更好（有回收站兜底）。

---

## 2. 差距清单（对照参考与外部工具）

| # | 差距 | 现状表现 | 后果 | 参考来源 |
|---|------|----------|------|----------|
| G1 | **无安装检测** | 80 项全部无条件扫描；没装 UE/Houdini 也一直显示 | 大量"未找到/0 B"噪音；扫描慢；用户难聚焦 | FluentCleaner `DetectionService` |
| G2 | **硬编码、覆盖有限** | 新增 App 要改 `scanner.py` 源码、重新打包 | 通用软件（数千款）缺失；扩展成本高 | winapp2 数据库 |
| G3 | **无自定义规则** | 用户无法加"我自己的工具缓存路径" | VP 用户的小众工具缓存扫不到 | `CustomEntryService` |
| G4 | **无 CLI / 自动模式** | 只能手动点 GUI | 无法做计划任务夜间自动清理 | FluentCleaner `/AUTO`、BleachBit CLI |
| G5 | **无设置持久化** | 每次启动重新全选 | 重复操作、体验差 | `AppSettings` 便携 |
| G6 | **无全局排除** | 重要文件保护靠人工"注意" | 误删风险（如把微信聊天缓存当普通缓存清） | `ExcludeKey` / 全局排除 |
| G7 | **只扫预定义路径** | 无法发现"项目文件夹膨胀"这种 VP 大头 | 真正占空间的东西可能根本没被扫到 | WizTree / WinDirStat |
| G8 | **WinSxS / Installer 只能整目录只读** | 标只读 + 文字说明，无操作 | 用户要么不动、要么自己手敲 DISM；Installer 缓存白白占空间 | Dism++ / PatchCleaner |
| G9 | **无系统修复动作** | 只有说明文字，没有按钮 | 用户还要另开工具做 SFC/DISM | Dism++ |
| G10 | **无清理日志文件 / 历史** | 只有应用内滚动日志，关掉即丢 | 不可审计、无法看垃圾增长趋势 | FluentCleaner `auto.log` / `CleanHistory` |
| G11 | **路径表达不统一** | 手写 `os.environ` + 零散拼接 | 规则复用差、易出错 | `PathExpander` |

---

## 3. 优势 vs 短板 矩阵

```
                    高价值
                      ↑
   磁盘空间分析 Tab   │   安装检测
   (WizTree 启发)     │   (DetectionService)
   CLI/自动模式        │   自定义规则文件夹
   (BleachBit/FC)     │   (CustomEntryService)
                      │
   系统修复动作 ───────┼─────── 已强：VP 垂直条目
   (Dism++)           │          风险分级/回收站/中文
                      │
   清理日志/历史       │   全局排除
   (PrivaZer/FC)      │   设置持久化
                      │
                    低价值（暂时）──→ 实现难度/风险
```

---

## 4. 差距 → 改进映射（为开发计划铺路）

| 差距 | 对应改进（落在哪个迭代见 `04_迭代开发计划.md`） |
|------|-----------------------------------------------|
| G1 安装检测 | 迭代1：ScanItem 增加 `detect` 字段，未安装项折叠/隐藏 |
| G3 自定义规则 | 迭代1：新增 `Custom/` 加载器（简易 ini，复用 winapp2 子集语法） |
| G5 设置持久化 | 迭代1：新增 `settings.json` 读写（便携模式） |
| G2 覆盖广度 | 迭代2：新增 `winapp2_parser.py` + 加载器，合并内置/winapp2/自定义 |
| G6 全局排除 | 迭代2：ExcludeKey 解析 + 全局排除列表 |
| G4 CLI / G10 日志 | 迭代3：CLI 模式 + 每轮日志文件 |
| G7 空间分析 | 迭代4：磁盘空间分析 Tab |
| G8/G9 WinSxS/修复 | 迭代5：系统修复按钮 + Installer 孤立项清理 |
| G11 路径表达 | 迭代1/2：统一路径展开器（%变量% + 通配符） |

---

## 5. 设计原则（贯穿所有迭代）

1. **只删明确是垃圾的东西**（缓存/临时/残留日志），不碰用户数据。
2. **不做注册表"优化"清理**（无效且危险）。
3. **不默认做 SSD 安全覆写擦除**（标注无效）。
4. **精确删除 + 排除保护**，绝不整盘通配。
5. **关键操作必须用户确认**（延续现有确认弹窗 + 回收站兜底）。
6. **保持中文界面与 VP 垂直深度**这一差异化优势。

下一份文档：`04_迭代开发计划.md`（每次迭代的具体调整内容 + 验证）。
