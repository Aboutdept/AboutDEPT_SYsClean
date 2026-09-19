<p align="center">
  <img src="icon.ico" alt="SysClean" width="96" height="96">
</p>

<h1 align="center">SysClean</h1>

<p align="center">
  <b>A Windows junk cleaner built for CG / Virtual Production / AIGC pipelines</b><br>
  An open-source cleaner that knows the cache paths of Unreal, Unity, Houdini, Nuke and ComfyUI — the tens of GB that generic cleaners miss.
</p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/语言-中文-red" alt="中文"></a>
  <a href="README_EN.md"><img src="https://img.shields.io/badge/Language-English-blue" alt="English"></a>
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Rules-3%2C911-orange" alt="Rules">
  <img src="https://img.shields.io/badge/UI-tkinter%20Dark-4B8BBE" alt="UI">
  <img src="https://img.shields.io/badge/Registry-Never%20touched-brightgreen" alt="No registry">
</p>

<p align="center">
  <b>🌐 Language：</b>
  <a href="README.md">中文</a> ·
  <a href="README_EN.md"><b>English</b></a>
</p>

---

## 30-Second Overview

| | |
|---|---|
| **What it is** | A pure-Python + tkinter Windows scan/clean tool, single-file exe, no install needed |
| **How it differs from CCleaner** | The rule database is rewritten for CG-industry software: it knows the cache paths of Unreal / Unity / Houdini / Nuke / Resolve / ComfyUI / Stable Diffusion that generic tools don't |
| **How much it frees** | Measured **79 GB** on the dev machine (99 built-in + 91 CG/AIGC DB rules + 3,721 winapp2 community rules) |
| **Is it safe** | Files only, **never touches the registry**; sends to Recycle Bin by default; supports exclusion rules; has an audit log; CLI dry-runs by default |
| **How to use** | Double-click `SysClean.exe` → Scan → check → Clean Selected |

A real scan output (excerpt):

```
[info] winapp2 database: 596 installed-app entries
Reclaimable space : 69.14 GB
    Read-Only Info  52.41 GB     Dev Tools       8.36 GB
    System Logs      3.56 GB     3rd-party apps   2.95 GB
    App Cache        1.38 GB     AIGC           61.91 MB
    Unreal Engine    1.39 MB     Windows Update  38.77 MB
```

---

## 1. The Problem It Solves

For CG artists, the C: drive feels like: **nothing installed, yet the disk is red.** The reason is that industry software caches with a "write-only, never-scan" strategy:

| Scenario | Typical footprint |
|---|---|
| Unreal Engine derived-data cache / crash dumps | 5–40 GB per project |
| Unity ShaderCache / Library / Asset import cache | 1–10 GB per project |
| Houdini temp & crash logs | several GB over time |
| Nuke / Foundry cache & logs | several GB |
| ComfyUI / Stable Diffusion temp & output | tens of GB |
| Hugging Face model cache (`~/.cache/huggingface`) | 2–20 GB per model, **not auto-cleaned by default** |
| GPU shader cache (D3DSCache / NV_Cache / AMD / Intel) | several GB |
| Adobe media cache, PTX index, CEP cache | several GB |

Generic cleaners (Windows Disk Cleanup, CCleaner default rules) **don't know these paths** — they are designed for "browser + Office + system temp files." The result: the stuff that actually eats space is never cleaned; only a few dozen MB get removed.

SysClean's approach: **the rule database is rewritten by industry.** Built-in entries cover system & common software, `Databases/CG_AIGC.ini` covers the whole CG / VP / AIGC chain, and `Winapp2.ini` backstops thousands of general apps.

---

## 2. Why It Matters to CG / Virtual Production / AIGC Professionals

| Role | Pain point | What SysClean does |
|---|---|---|
| **3D / Rendering** | UE, Unity, Houdini, C4D, Blender project caches pile up; C: fills fast when running multiple projects in parallel | Precisely targets ShaderCache / DerivedDataCache / crash dumps / temp dirs, cleans per project without touching project files |
| **Post / Comp** | Nuke, Resolve, Fusion, Adobe media cache & PTX index accumulate unmaintained | Hits media cache, preview cache, log dirs; reclaims several GB without touching assets |
| **Virtual Production** | TouchDesigner, Notch, Aximmetry, Disguise on-site logs & caches accumulate | Built-in VP & Broadcast category (8) + 5 DB rules; on-site machines can be cleaned regularly |
| **AIGC / Models** | ComfyUI, SD-WebUI, Hugging Face, Ollama, Torch Hub model & temp caches easily hit tens of GB | AIGC category with 18 rules, incl. HF Hub / Xet, Gradio, Whisper, Ultralytics, Topaz |
| **IT / Farm maintenance** | Batch-maintaining render-farm system disks | CLI + Task Scheduler silent cleanup; audit log traces every deletion |
| **Freelancers** | Don't want CCleaner, don't want bundled installs | Single-file exe, portable, no network, no ads, no telemetry |

**Three design principles** (what sets it apart from "system optimizer" software):

1. **No registry optimization.** It only parses and executes file/directory cleanup rules; winapp2 `RegKey` entries are ignored. Registry "optimization" is low-benefit, high-risk.
2. **Recycle Bin only, never direct deletion.** Mistakes can be restored from the Recycle Bin.
3. **Undetected / non-existent entries are auto-hidden.** No noise, and they are never cleaned.

---

## 3. Quick Start

### Option A: Use the exe (recommended)

Download `SysClean.exe` from Releases and double-click:

1. Click **Scan** (about 1–2 minutes)
2. Check the items to clean (filter by risk level)
3. Click **Clean Selected** → confirm dialog → clean

> Cleaning system-directory items may need admin rights; right-click → "Run as administrator" is recommended.

### Option B: Run from source

```bat
git clone <your-repo-url>
cd SysClean
python main.py
```

Requirements: **Python 3.8+ with tkinter** (the official python.org installer includes it; some slim distros don't).
Standard library only — no `pip install` needed.

---

## 4. What It Cleans

Three rule sources, **3,911 entries** total:

| Source | Count | Note |
|---|---|---|
| Built-in (`scanner.py`) | 99 | System + common software + CG basics, maintained in code |
| `Databases/CG_AIGC.ini` | 64 | **Authored here**: CG / Post / VP / AIGC / GPU shaders |
| `Databases/Dism_System.ini` | 27 | File-only items extracted from Dism++ (see `NOTICE.md`) |
| `Winapp2.ini` | 3,721 | winapp2 community DB (CC-BY-SA-4.0, see `NOTICE.md`) |

### 4.1 CG & Post (`Databases/CG_AIGC.ini`, 34 entries)

| Software | What it cleans |
|---|---|
| **Unreal Engine** | Crash dumps, Saved logs & cache (plus 7 built-in) |
| **Unity** | ShaderCache, Hub download cache, Asset import cache, editor logs |
| **Godot** | Project cache |
| **Omniverse** | Cache, logs |
| **Maya** | Local cache, crash logs |
| **3ds Max** | Auto backup (autoback) |
| **MotionBuilder** | Cache |
| **Cinema 4D (Maxon)** | Cache |
| **Blender** | Temp files |
| **Houdini** | Temp dir, crash & logs |
| **Nuke / Foundry** | Temp & logs, app cache |
| **Redshift** | Logs & cache |
| **V-Ray / Corona / Arnold** | Render cache (incl. new Chaos paths) |
| **Substance 3D** | Cache (incl. legacy Allegorithmic) |
| **DaVinci Resolve / Fusion** | Cache, logs |
| **Adobe suite** | Media cache, PTX index, CEP cache, CRLogs, Media Encoder logs, Lightroom preview cache |

### 4.2 AIGC (18 entries)

ComfyUI (temp / C:-root temp / logs), Stable Diffusion WebUI, Fooocus, Gradio,
**Hugging Face model cache + Xet cache**, Torch Hub, Whisper, Ultralytics,
Ollama, LM Studio, AnythingLLM, Topaz (cache & logs),
Agisoft Metashape, RealityCapture.

> Hugging Face cache is marked `caution` (handle with care): model files are large; deleting them means re-downloading.

### 4.3 Virtual Production (5) + Media (2)

TouchDesigner (cache / logs), Notch, Aximmetry, Disguise; OBS Studio logs, VLC cache.

### 4.4 GPU shader cache (5)

DirectX `D3DSCache`, NVIDIA `NV_Cache`, AMD shader cache / OpenGL cache, Intel shader cache.

### 4.5 System & Dev (built-in + Dism++ derived)

| Category | Content |
|---|---|
| Temp Files | Windows temp, user temp |
| Windows Update | Update download cache, CBS temp, WinSxS manifest cache |
| System Logs | CBS / DISM / Panther, Defender scan history, LiveKernelReports, WinSAT |
| System Cache | Thumbnail cache, Prefetch, INetCache/Cookies, font cache, UWP AC Temp |
| Crash Reports | App crash dumps, Windows Error Reporting |
| Browser Cache | Chrome / Edge cache & Code Cache |
| Dev Tools | npm, pip, NuGet, VS Package Cache, .NET Native Images, JetBrains logs |
| Other | Driver-install temp, retail-demo offline content, NVIDIA driver download cache |

---

## 5. Safety Design

| Mechanism | Note |
|---|---|
| **No registry** | Never reads/writes the registry; winapp2 `RegKey` ignored |
| **Recycle Bin only** | Files & dirs go through the Shell Recycle Bin API, restorable |
| **Exclusion rules** | winapp2 `ExcludeKey` + user "global exclude" list; a hit is skipped and logged |
| **Risk levels** | `safe` / `medium` / `caution`; dangerous items show a red warning in the confirm dialog |
| **Read-only marker** | No-permission or protected items show 🔒 and cannot be checked |
| **Install detection** | Undetected software entries are auto-hidden, preventing misfires |
| **Post-delete verify** | Failed deletes don't fake freed space and don't write the audit log |
| **CLI dry-run** | CLI only prints the plan by default; explicit `--yes` is required to actually delete |
| **Audit log** | Every real deletion appends `SysClean_cleanup.log` (TSV: time/type/name/path/size) |
| **Crash visibility** | Packaged exe has no console; exceptions write `logs/crash-*.log` and pop a dialog — never fails silently |

---

## 6. Architecture & File Structure

```
SysClean/
├── main.py              # Entry: no args → GUI; args → CLI
├── gui.py               # tkinter dark GUI (scan tree / details / log / settings / confirm dialog)
├── scanner.py           # Scan engine + clean engine + report generator + rule loader
├── cli.py               # CLI (--scan / --clean / --auto / --report)
├── settings.py          # Settings persistence (settings.json)
├── app_paths.py         # Packaging-aware path layer (read-only vs writable data split)
├── winapp2_parser.py    # Winapp2.ini parser
├── Winapp2.ini          # Community DB (3,721 entries)
├── Databases/
│   ├── CG_AIGC.ini      # Authored: CG / VP / AIGC / GPU (64)
│   └── Dism_System.ini  # From Dism++ (27)
├── Custom/              # User custom rules (drop a .ini, works, no code change)
├── tests/               # Regression tests (5 suites, 84 assertions)
├── tools/               # Undefined-name static scan + full regression entry
├── docs/                # Design, research, iterations, bug-fix logs
├── icon.ico             # App icon (also used as the README header badge)
├── run.bat / build_exe.bat / *.spec
├── README.md            # Chinese version (switch via the Language badge at top)
├── README_EN.md         # This document (English)
├── LICENSE              # MIT full text (project code)
├── NOTICE.md            # Third-party data sources & licenses
├── CONTRIBUTING.md      # Contribution guide (rule syntax + safety red lines)
├── .gitignore           # Ignores __pycache__ / build / dist / logs / runtime data
└── .gitattributes       # Line-ending normalization (.bat=CRLF, rest=LF)
```

**Data flow**:

```
Three rule sources (built-in / Databases / Winapp2.ini / Custom)
        ↓  PathExpander expands %LocalAppData% etc. env vars
        ↓  DetectionService install detection (path exists or registry key)
ScanEngine.scan_all()  →  ScanItem list (size / risk / file count / children)
        ↓
GUI aggregates by category (or CLI filters)
        ↓  CleanEngine (exclusions → Recycle Bin → post-delete verify → audit log)
        ↓
ReportGenerator (TXT / JSON / CSV)
```

**Key modules**:

- `PathExpander` — uniformly expands `%LocalAppData% %AppData% %ProgramData% %ProgramFiles% %ProgramFiles(x86)% %UserProfile% %SystemRoot% %SystemDrive% %System% %Public% %OneDrive% %Temp% %Documents% %Videos% %Pictures% %Desktop%`, and tolerates case variants (e.g. `%localappdata%`).
- `app_paths.py` — **the key to running correctly after packaging.** Under PyInstaller onefile, `__main__.__file__` points to a new random `_MEIxxxxxx` temp dir each run; reusing it would lose settings/logs every launch. Here "read-only data" (`data_dir`) is separated from "writable data" (`writable_dir`).

---

## 7. Build & Package

### 7.1 Environment

```bat
python --version          :: 3.8+ , must be a tkinter-enabled CPython
python -c "import tkinter"   :: no error = OK
pip install pyinstaller
```

> WorkBuddy / some slim Python builds **lack tkinter**; packaging with them yields an exe that "builds but crashes on launch."
> `build_exe.bat` validates tkinter and PyInstaller first and stops if either is missing.

### 7.2 Build

```bat
build_exe.bat          :: only dist\SysClean.exe       (GUI, no console)
build_exe.bat /all     :: also dist\SysClean_CLI.exe   (with console, for CLI / Task Scheduler)
```

Both are **onefile** (single file, ~8.5 MB), icon = `icon.ico`.
Use `set SYSCLEAN_PYTHON=<python.exe>` to specify the interpreter.

Equivalent direct calls:

```bat
python -m PyInstaller SysClean.spec      --noconfirm --clean
python -m PyInstaller SysClean_CLI.spec  --noconfirm --clean
```

### 7.3 spec essentials

`datas` must be embedded, or the rule DB is useless:

```python
datas = [('Winapp2.ini', '.'), ('icon.ico', '.'),
         ('Databases', 'Databases'), ('Custom', 'Custom')]
console   = False          # GUI build; CLI build = True
icon      = 'icon.ico'
excludes  = ['numpy', 'scipy', 'PIL', 'PyQt5', 'PySide6', 'matplotlib', 'pandas']
```

> Why two exes: a console-less process on Windows can't get stdout, so the pure-GUI build can't use `--scan --report`. Both are single-file and independent.

### 7.4 Override the built-in rule DB (no rebuild needed)

Place `Databases/` or a newer `Winapp2.ini` **next to the exe** to override the built-in version — `data_dir()` prefers the exe directory.

---

## 8. Deploy & Automate

### 8.1 CLI usage

```bat
:: Scan only and export a report (deletes nothing)
SysClean_CLI.exe --scan --report report.json
SysClean_CLI.exe --scan --report report.csv

:: Dry-run: print the plan, don't actually delete
SysClean_CLI.exe --auto

:: Actually execute (uses selections saved in the GUI)
SysClean_CLI.exe --auto --yes --log cleanup.log

:: Clean by category
SysClean_CLI.exe --clean --category "Temp Files" --yes
SysClean_CLI.exe --clean --all --yes --report summary.txt
```

| Flag | Effect |
|---|---|
| `--scan` | Scan only, emit report |
| `--clean` | Clean (with `--all` / `--category` / `--selected` / `--auto`) |
| `--auto` | Use selections saved in settings (same as `--clean --selected`) |
| `--yes` | **Confirm deletion**; defaults to dry-run when omitted |
| `--report <path>` | `.json` / `.csv` / `.txt` |
| `--log <path>` | Audit log path |
| `--db` / `--no-db` | Enable / disable the CG/AIGC rule DB |
| `--winapp2` / `--no-winapp2` | Enable / disable the community DB |

### 8.2 Scheduled cleanup (render farm / workstation routine)

1. Task Scheduler → create a basic task (e.g. daily 03:00)
2. Action: start a program → `SysClean_CLI.exe`
3. Arguments: `--auto --yes --log "%APPDATA%\SysClean\cleanup.log"`
4. Start in: the exe's directory
5. **Run once without `--yes` first** to confirm the plan is sane, then enable auto-delete

### 8.3 Portable deployment

Settings, audit log and crash log default to **the exe's directory** (portable mode); if not writable they fall back to `%APPDATA%\SysClean`.
Put the exe together with `Databases/` and `Custom/` on a USB drive to carry all config.

---

## 9. Development Workflow

### 9.1 Run tests

```bat
python tools\run_all_tests.py
```

Runs 5 suites + undefined-name static scan + syntax compile of 6 source files, results to `logs/regression-latest.log`:

| Suite | Count | Covers |
|---|---|---|
| `tests/test_bugfix_b1_b6.py` | 26 | Path expansion, exclusion protection, category grouping, Recycle Bin, CLI bounds |
| `tests/test_db_rules.py` | 24 | Rule DB parsing, confirm-dialog geometry (equal height/width at 3 vs 300 items) |
| `tests/test_clean_flow.py` | 15 | Clean Selected click chain, exception recovery |
| `tests/test_app_paths.py` | 12 | Path resolution under frozen / source |
| `tests/test_gui_smoke.py` | 7 | Real Tk window + real mainloop smoke |

### 9.2 Two lines of defense against "silent failure"

Under `pythonw` / packaged exe there is no console, so exceptions are swallowed and it looks like "clicked but nothing happened":

1. **Static scan** — `python tools/check_undefined_names.py` (AST mini-pyflakes handling lambda / comprehensions / annotation assignment / global), catches undefined names before commit
2. **Runtime fallback** — `report_callback_exception` + `sys.excepthook`, any exception always pops a dialog and writes `logs/`

### 9.3 Add a rule (no code change)

Drop a `.ini` in `Custom/` (winapp2 subset + project extensions):

```ini
[My Renderer Cache]
DetectFile=%LocalAppData%\MyRenderer
Category=CG & Post-Production
Risk=safe
FileKey1=%LocalAppData%\MyRenderer\Cache|*.tmp;*.cache|RECURSE
```

- `DetectFile` — install detection; if absent the item is auto-hidden
- `FileKey1=path|wildcard pattern|RECURSE` — only deletes files matching the pattern
- `REMOVESELF` — empties the whole directory
- Files ending in `.disabled` are ignored

---

## 10. Documentation Index

| Doc | Content |
|---|---|
| `docs/01_参考分析_FluentCleaner.md` | Reference project analysis |
| `docs/02_外部清理修复工具调研.md` | Mainstream cleaner research |
| `docs/03_SysClean现状与差距分析.md` | Gap analysis at project start |
| `docs/04_迭代开发计划.md` | Iteration plan |
| `docs/05~07_迭代N执行记录.md` | Per-iteration implementation logs |
| `docs/08_Bug修复记录_B1-B6.md` | Path expansion / exclusion / category dup / Recycle Bin / CLI bounds |
| `docs/09_规则数据库与UI修复.md` | CG/AIGC rule DB + fixed-height confirm dialog |
| `docs/10_CleanSelected无响应修复.md` | Root cause of "click no response" + two defense lines |
| `docs/11_打包为单个exe.md` | Packaging path-layer bug & verification evidence |

---

## 11. Known Limitations

- The single-file exe extracts to a temp dir on each launch; first launch is 1–3s slower than source mode
- PyInstaller onefile may be falsely flagged by antivirus (known; use onedir or Nuitka if needed)
- `Databases/Dism_System.ini` only takes Dism++'s **file/directory** cleanup items; registry, WinSxS component cleanup, system restore points and Appx uninstall are never adopted
- Cleaning system-directory items may require admin rights
- Hugging Face / model caches must be re-downloaded after deletion; marked `caution`

## 12. Roadmap

- Space analysis tab (WizTree-style, find big folders)
- Duplicate file finder
- Uninstall-residue scanner
- In-app English UI

---

## 13. License & Third-Party Data

**Code: MIT** (see `LICENSE`).

Third-party data sources & licenses: see **`NOTICE.md`**. Summary:

| File | Source | License |
|---|---|---|
| `Winapp2.ini` | [MoscaDotTo/Winapp2](https://github.com/MoscaDotTo/Winapp2) | **CC-BY-SA-4.0** (attribution + share-alike redistribution) |
| `Databases/Dism_System.ini` | Extracted from [Chuyu-Team/Dism-Multi-language](https://github.com/Chuyu-Team/Dism-Multi-language) `Data.xml` | **MIT** (Chuyu-Team, 2016) |
| `Databases/CG_AIGC.ini` | Authored here | MIT |

---

## Disclaimer

Cleaning is risky. This tool sends to Recycle Bin by default and provides a dry-run mode and exclusion rules, but **does not guarantee the safety of any deletion**. On first use, scan only, manually verify paths, then clean in small batches; back up important data first.

---

## 🌐 Bilingual

This document is available in Chinese and English; click the **Language** badge at the top to switch:

- **English (this file)**: [`README_EN.md`](README_EN.md)
- **中文**: [`README.md`](README.md)

The two versions correspond exactly and share the same data. If any translation diverges, the Chinese version prevails.
