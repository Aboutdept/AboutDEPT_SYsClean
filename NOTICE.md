# 第三方数据来源与许可 / Third-Party Notices

本项目的**源代码**采用 MIT 许可（见 `LICENSE`）。
但仓库内包含**非本项目原创的规则数据文件**，它们各自适用不同的许可条款。
分发、二次发布或Fork 本仓库时，请一并保留本文件。

---

## 1. `Winapp2.ini` —— CC BY-SA 4.0

| 项目 | 内容 |
|---|---|
| 文件 | `Winapp2.ini`（仓库根目录） |
| 来源 | <https://github.com/MoscaDotTo/Winapp2> |
| 上游维护者 | MoscaDotTo / Winapp2 社区贡献者 |
| 许可 | **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)** |
| 文件头原文声明 | `; // This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License.` |
| 本仓库快照 | Version `260515`，共 3,721 条 `[Application]` 条目 |

**义务（CC BY-SA 4.0 核心条款摘要）**

- **署名（BY）**：保留原作者与来源链接，注明是否做了修改。
- **相同方式共享（SA）**：若你基于该文件创作演绎作品并分发，必须以 **CC BY-SA 4.0** 许可发布。
- 本仓库对该文件**仅做只读引用**，未在程序运行时改写其内容；SysClean 只是解析它生成扫描项。

完整法律文本：<https://creativecommons.org/licenses/by-sa/4.0/legalcode>

> 若你希望移除该文件：删除 `Winapp2.ini` 即可，程序会自动降级为「仅使用内置规则 + `Databases/` 规则库」，功能不受影响（仅覆盖的软件数量减少）。

---

## 2. `Databases/Dism_System.ini` —— 源自 Dism++（MIT）

| 项目 | 内容 |
|---|---|
| 文件 | `Databases/Dism_System.ini` |
| 来源项目 | Dism-Multi-language（Dism++）<https://github.com/Chuyu-Team/Dism-Multi-language> |
| 原始许可 | **MIT License，Copyright (c) 2016 Chuyu-Team** |
| 本仓库的处理 | 从上游 `Data.xml`（268 项）中**筛选并转写**为 SysClean 的 ini 规则语法，共 **27 条** |

**转写说明（非逐字复制）**

上游 `Data.xml` 的条目是 XML 结构（`<CleanCollection4><Item>` + `<General RootPath= Flags=>`）。
本仓库只保留了**纯文件/目录删除型**条目，并做了以下处理：

- 剔除**注册表操作**类条目（SysClean 不写注册表）
- 剔除 **WinSxS 组件存储清理**、**系统还原点删除**、**Appx 包清理**等高风险项
- 路径占位符从上游格式改写为 SysClean 的 `%VAR%` 展开语法
- 每条追加 `Category=` 与 `Risk=` 分级（这两项为本仓库新增的元数据）

因此 `Dism_System.ini` 属于**演绎作品**，按 MIT 要求已在下方保留原始版权与许可声明。

```
The MIT License (MIT)

Copyright (c) 2016 Chuyu-Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 3. `Databases/CG_AIGC.ini` —— 本项目原创（MIT）

| 项目 | 内容 |
|---|---|
| 文件 | `Databases/CG_AIGC.ini` |
| 作者 | AboutDEPT（本项目） |
| 许可 | **MIT**（与仓库主体一致） |
| 条目数 | 64 条 |

覆盖 Unreal Engine / Unity / Houdini / Nuke / DaVinci Resolve / Blender / Substance / Cinema 4D / Maya / 3ds Max / ComfyUI / Stable Diffusion WebUI / Fooocus / InvokeAI / Ollama / NVIDIA / Adobe 等缓存路径。
欢迎提 PR 补充，补充者默认同意以 MIT 许可贡献。

---

## 4. 内置规则（源码内）

`scanner.py` 中 `DEFAULT_RULES` 定义的 99 项内置规则为本仓库原创，MIT 许可。

---

## 5. `icon.ico`

本项目自有图标，MIT 许可范围内使用。

---

## 汇总表

| 文件 | 来源 | 许可 | 条目数 |
|---|---|---:|---:|
| `Winapp2.ini` | MoscaDotTo/Winapp2 | CC BY-SA 4.0 | 3,721 |
| `Databases/Dism_System.ini` | Chuyu-Team/Dism-Multi-language（转写） | MIT (2016) | 27 |
| `Databases/CG_AIGC.ini` | 本项目原创 | MIT | 64 |
| `scanner.py` 内置规则 | 本项目原创 | MIT | 99 |
| **合计** | | | **3,911** |

---

*本文件不构成法律意见。若你对上述许可的合规性有疑问，请在分发前咨询专业法律意见。*
