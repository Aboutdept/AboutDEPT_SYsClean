# -*- coding: utf-8 -*-
"""
winapp2_parser.py - Winapp2.ini 解析器（SysClean 迭代 2）

解析社区维护的 Winapp2.ini 数据库（3721+ 条规则），把其中「仅文件清理」
的条目转换为 SysClean 的 ScanItem，并收集 ExcludeKey 排除规则。

设计原则（对齐 SysClean「不做注册表优化」哲学）：
  * 只处理 FileKey（文件/目录清理），**完全忽略 RegKey**（不读写注册表）。
  * 只处理 LangSecRef 分类中的「第三方应用」类，跳过 System / Registry / CCleaner。
  * ExcludeKey 的 FILE / PATH 生效（保护用户文件），REG 忽略。
  * 未通过安装检测（Detect / DetectFile）的条目直接丢弃，避免噪音。
"""

import os
import re
import configparser
import fnmatch

try:
    import winreg
except ImportError:
    winreg = None

from dataclasses import dataclass, field


# ------------------------------------------------------------
#  数据结构
# ------------------------------------------------------------

@dataclass
class CleanerEntry:
    """单条 winapp2 规则（已解析）"""
    name: str
    category: str = ""              # 来自 LangSecRef 第二个分段
    description: str = ""           # Default
    warning: bool = False           # 存在 Warning 键
    detect: list = field(default_factory=list)      # 展开后的文件/文件夹路径
    detect_reg: list = field(default_factory=list)  # 注册表键
    file_keys: list = field(default_factory=list)   # [{"path","patterns","recurse","removeself"}]
    exclude_keys: list = field(default_factory=list)  # [(type, value)]


# 需要跳过的分类（这些与 builtin 系统项重复，或涉及注册表，SysClean 不处理）
_SKIP_GROUPS = {"System", "Registry", "CCleaner"}

# LangSecRef 第二个分段 → SysClean 中文分类（未列出的保持英文原值）
_GROUP_MAP = {
    "Applications":   "第三方应用",
    "Games":          "游戏",
    "Multimedia":     "多媒体",
    "Utilities":      "实用工具",
    "Web Browsers":   "浏览器",
    "IM":             "即时通讯",
    "Media Players":  "媒体播放器",
    "Developers":     "开发工具",
    "AntiVirus":      "杀毒软件",
    "Documents":      "文档工具",
    "Edge":           "Edge",
    "Firefox":        "Firefox",
    "Chrome":         "Chrome",
    "Mozilla":        "Mozilla",
    "Opera":          "Opera",
    "Apple":          "Apple",
    "Microsoft":      "Microsoft",
    "Adobe":          "Adobe",
    "iTunes":         "iTunes",
}


def _slug(name: str) -> str:
    return re.sub(r"\W+", "_", name.strip()) or "entry"


# ------------------------------------------------------------
#  解析
# ------------------------------------------------------------

def parse_winapp2(path: str) -> list:
    """解析 Winapp2.ini，返回 CleanerEntry 列表（未做安装过滤）。"""
    if not path or not os.path.isfile(path):
        return []
    # strict=False：Winapp2.ini 中个别 section 存在重复键（如多个 Default 行），
    # 关闭严格模式，取最后一个值即可，避免解析整体失败。
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str  # 保留键名大小写（FileKey1 / ExcludeKey1...）
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return []

    entries = []
    for section in parser.sections():
        data = dict(parser.items(section))
        entry = _parse_section(section, data)
        if entry is not None:
            entries.append(entry)
    return entries


def _parse_section(name: str, data: dict) -> "CleanerEntry | None":
    lsr = data.get("LangSecRef", "")
    parts = [p.strip() for p in lsr.split("|")] if lsr else []
    group = parts[1] if len(parts) > 1 else ""
    # 跳过系统/注册表/CCleaner 分类（与 builtin 重复或涉及注册表）
    if group in _SKIP_GROUPS:
        return None

    category = _GROUP_MAP.get(group, group) if group else "第三方应用"

    # 检测线索
    detect = []
    detect_reg = []
    if data.get("DetectFile"):
        detect.append(data["DetectFile"].strip())
    if data.get("Detect"):
        detect_reg.append(data["Detect"].strip())
    if data.get("DetectOS"):
        # DetectOS 跨平台约束，本地忽略（视为满足）
        pass

    # 文件键
    fk_keys = sorted(
        [k for k in data if k.startswith("FileKey")],
        key=lambda k: int("".join(filter(str.isdigit, k)) or 0)
    )
    file_keys = []
    for key in fk_keys:
        seg = [s.strip() for s in data[key].split("|")]
        raw = seg[0] if seg else ""
        if not raw:
            continue
        patterns = []
        recurse = False
        removeself = False
        if len(seg) > 1 and seg[1]:
            patterns = [p.strip() for p in seg[1].split(";") if p.strip()]
        if len(seg) > 2:
            flags = " ".join(seg[2:]).upper()
            if "RECURSE" in flags:
                recurse = True
            if "REMOVESELF" in flags:
                removeself = True
        file_keys.append({
            "path": raw,
            "patterns": patterns,
            "recurse": recurse,
            "removeself": removeself,
        })

    # 排除键
    ek_keys = sorted(
        [k for k in data if k.startswith("ExcludeKey")],
        key=lambda k: int("".join(filter(str.isdigit, k)) or 0)
    )
    exclude_keys = []
    for key in ek_keys:
        val = data[key].strip()
        if not val:
            continue
        segs = val.split("|")
        typ = segs[0].upper() if segs else ""
        if typ not in ("FILE", "PATH", "REG"):
            continue
        if typ == "REG":
            continue  # SysClean 不处理注册表
        rest = "|".join(segs[1:]) if len(segs) > 1 else ""
        if rest:
            exclude_keys.append((typ, rest))

    entry = CleanerEntry(
        name=name,
        category=category,
        description=data.get("Default", "").strip() or name,
        warning="Warning" in data,
        detect=detect,
        detect_reg=detect_reg,
        file_keys=file_keys,
        exclude_keys=exclude_keys,
    )
    return entry


# ------------------------------------------------------------
#  安装检测（仅用于决定条目是否纳入扫描）
# ------------------------------------------------------------

def _reg_key_exists(key_path: str) -> bool:
    if winreg is None:
        return False
    try:
        root_name, sub = key_path.split("\\", 1)
    except ValueError:
        return False
    hkey = {
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
        "HKLM64": winreg.HKEY_LOCAL_MACHINE,
    }.get(root_name)
    if hkey is None:
        return False
    try:
        key = winreg.OpenKey(hkey, sub, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        key.Close()
        return True
    except OSError:
        return False


def _entry_installed(entry: "CleanerEntry") -> bool:
    """判断该 winapp2 条目对应的软件是否已安装。"""
    from scanner import PathExpander  # 延迟导入，避免循环依赖

    # 有显式检测线索：文件 OR 注册表
    if entry.detect or entry.detect_reg:
        paths = PathExpander.expand_list(entry.detect)
        regs = entry.detect_reg
        for p in paths:
            for ep in PathExpander.resolve_matches(p):
                if os.path.exists(ep):
                    return True
        for r in regs:
            if _reg_key_exists(r):
                return True
        return False

    # 无检测线索：用首个 FileKey 的「应用已知目录」是否存在来推断
    if entry.file_keys:
        base = entry.file_keys[0]["path"].split("*")[0].rstrip("\\/")
        if not base:
            return False
        base = PathExpander.expand(base)
        # 去掉可能的通配符段后的目录
        test_dir = base
        if os.path.isdir(test_dir):
            return True
        parent = os.path.dirname(base)
        if parent and os.path.isdir(parent):
            return True
    return False


# ------------------------------------------------------------
#  转换为 ScanItem（仅文件清理条目）
# ------------------------------------------------------------

def _fk_exists(raw_path: str) -> bool:
    """判断某个 FileKey 目标路径是否存在（含通配符展开）。"""
    from scanner import PathExpander  # 延迟导入
    expanded = PathExpander.expand(raw_path)
    if "*" in expanded or "?" in expanded:
        return bool(PathExpander.resolve_matches(expanded))
    return os.path.exists(expanded)


def entries_to_scan_items(entries: list) -> "tuple[list, list]":
    """把通过安装检测且「实际存在缓存」的条目转为 ScanItem，并汇总排除规则。

    仅纳入真正有内容的条目（FileKey 目标路径在磁盘上确实存在），避免把数千条
    空规则灌入扫描列表。返回 (scan_items, exclude_rules)。
      exclude_rules: [(type, value), ...]，type ∈ {"FILE","PATH"}，
                     value 对 FILE 可能是 "dir|pattern"，对 PATH 是 "dir"。
    """
    from scanner import ScanItem, PathExpander  # 延迟导入

    items = []
    all_excludes = []
    for entry in entries:
        if not entry.file_keys:
            continue  # 仅注册表条目：忽略
        if not _entry_installed(entry):
            continue

        # 仅保留确实存在的 FileKey（不存在的缓存目录不产生扫描项）
        kept = []
        for fk in entry.file_keys:
            if _fk_exists(fk["path"]):
                kept.append(fk)
        if not kept:
            continue

        all_excludes.extend(entry.exclude_keys)

        for idx, fk in enumerate(kept):
            raw_path = fk["path"]
            patterns = fk["patterns"]
            recurse = fk["recurse"]
            removeself = fk["removeself"]

            label = entry.name if len(kept) == 1 else f"{entry.name} (#{idx + 1})"
            sid = f"wa_{_slug(entry.name)}_{idx}"
            # BUGFIX B1: 路径必须展开环境变量，否则 ScanEngine._scan_path 会把
            # "%LocalAppData%\Foo\Cache" 当作字面目录判为不存在（size 恒为 0）。
            # 含通配符的分支在 scanner.py 里会被 resolve_matches 救回，
            # 不含通配符的分支（约 44% 条目）会永久失效 —— 故在此统一展开。
            expanded_path = PathExpander.expand(raw_path)

            # REMOVESELF：清理整个目录（不含通配符的目录整体删除）
            if removeself:
                patterns = []
                recurse = True

            item = ScanItem(
                id=sid,
                label=label,
                path=expanded_path,
                category=entry.category,
                risk_level="caution" if entry.warning else "safe",
                description=entry.description,
                cleaning_note="来自 winapp2 社区数据库（仅清理文件缓存，不涉及注册表）。",
                source="winapp2",
                custom=False,
                # BUGFIX B6: Detect 线索同样展开，避免详情面板/复制路径显示 %VAR%
                detect=[PathExpander.expand(d) for d in entry.detect],
                detect_reg=entry.detect_reg,
                patterns=patterns,
                recurse=recurse,
            )
            items.append(item)
    return items, all_excludes


# ------------------------------------------------------------
#  顶层加载器（供 scanner 调用）
# ------------------------------------------------------------

def load_winapp2(winapp2_path: str, enabled: bool = True) -> "tuple[list, list]":
    """加载 winapp2 数据库。

    返回 (scan_items, exclude_rules)。disabled 或文件缺失时返回 ([], [])。
    """
    if not enabled or not winapp2_path or not os.path.isfile(winapp2_path):
        return [], []
    entries = parse_winapp2(winapp2_path)
    return entries_to_scan_items(entries)
