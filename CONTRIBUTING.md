# CONTRIBUTING / 贡献指南

感谢你考虑为 SysClean 贡献力量。本项目面向 **CG / 虚拟制片 / AIGC** 工作流，
规则数据库的准确性直接关系到用户磁盘数据安全，**请务必遵守下述规则**。

---

## 一、许可与署名

- 你的代码贡献默认以 **MIT** 许可授权给本项目（与 `LICENSE` 一致）。
- 新增规则文件（`.ini`）若来源于第三方，请：
  1. 在 `NOTICE.md` 中登记来源与许可；
  2. 保留原始版权声明；
  3. 若许可为 **Copyleft**（如 CC BY-SA），请提前在 Issue 中说明兼容性。

---

## 二、规则贡献（最重要）

我们希望覆盖更多 **CG / AIGC 软件的缓存路径**。新增规则请在 `Databases/` 下新建或扩展 `.ini`。

### 规则语法

```ini
[YourAppName]
Category=CG & Post-Production          ; 分类，决定 UI 分组
Risk=safe                              ; safe | medium | caution
DetectFile=%ProgramFiles%\Vendor\App\  ; 可选：软件未安装则跳过
FileKey1=%LocalAppData%\Vendor\App\Cache\*.*|RECURSE
ExcludeKey1=%LocalAppData%\Vendor\App\Cache\important.dat
```

### 安全红线（不可违反）

- ❌ **绝不**写入或删除注册表（SysClean 只删文件）。
- ❌ **绝不**使用 `REMOVESELF` 指向用户文档、工程目录、素材目录。
- ❌ **绝不**对 `Risk=caution` 之外的路径使用通配符递归到系统根。
- ✅ 每条规则必须标注 `Risk=`，高风险路径用 `caution` 并加 `ExcludeKey` 保护关键文件。
- ✅ 提交前用 `python tools/run_all_tests.py` 跑一遍，确保无回归。

---

## 三、开发环境

- Python 3.8+（推荐 3.10）
- 仅依赖标准库 **tkinter**（Windows 自带）
- 打包：`build_exe.bat`（需先 `pip install pyinstaller`）

```bash
# 本地运行（源码模式）
python main.py

# CLI 扫描（干跑，不删除）
python main.py --scan

# 跑测试
python tools/run_all_tests.py
```

---

## 四、提交流程

1. Fork → 新建分支 `feat/xxx` 或 `fix/xxx`
2. 遵循现有代码风格（4 空格缩进、ASCII 标识符、函数级注释）
3. 更新对应 `docs/` 开发日志（append-only）
4. 开 PR，在描述中说明：改了什么 / 为什么 / 如何验证
5. 维护者 review 后合并

---

## 五、Issue 规范

- **Bug 报告**请附：Windows 版本、Python 版本、复现步骤、相关日志（`logs/` 下）
- **规则请求**请附：软件名 + 版本、缓存路径截图、路径是否可安全删除的依据

---

*保持克制：SysClean 的价值在于「精准而非贪婪」。一条误删比十条漏清更致命。*
