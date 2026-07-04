# SysClean 系统清理工具 - 项目记录

## 项目概述
Windows 系统垃圾文件扫描与清理工具，基于 tkinter/PyQt5 GUI。

## 扫描分类（共 17 大类，119 扫描项）

1. Temp Files（临时文件）
2. Windows Update（Windows 更新）
3. System Logs（系统日志）
4. System Cache（系统缓存）
5. Browser Cache（浏览器缓存）
6. Dev Tools（开发工具缓存）
7. Crash Reports（崩溃报告）
8. App Cache（应用缓存）
9. Other（其他）
10. Read-Only Info（只读信息）
11. Unreal Engine（虚幻引擎）
12. VP & Broadcast（虚拟制作）
13. CG & Post-Production（CG 与后期制作）
14. Win11 Exclusive（Windows 11 特有）
15. System Restore（系统还原与修复）
16. **VP & Broadcast Extended（VP 虚拟制作扩展）** - 新增
17. **Multimedia Tools（多媒体工具）** - 新增

## 已添加的扫描项

### 新增分类：System Restore（2026-03-31）
- `system_restore`: 系统还原点 (C:\System Volume Information)

### 新增 .NET 相关（2026-03-31）
- `dotnet_native_cache`: .NET Native 程序集缓存
- `dotnet_share_cache`: .NET Share 程序集缓存
- `dotnet_framework_cache`: .NET Framework 内部缓存

### 新增 百度网盘（2026-03-31）
- `baidu_netdisk_logs`: 百度网盘日志

### 新增 Visual Studio 相关（2026-03-31）
- `vs_component_model`: VS 组件模型缓存
- `vs_extensions`: VS 扩展缓存
- `vs_database`: VS 数据库缓存
- `vs_shader_cache`: VS 着色器缓存
- `vsdebugger`: VS 调试器临时文件
- `vs_pxg_cache`: VS Performance 性能缓存
- `package_cache`: VS Installer Package Cache

### 新增 VP 虚拟制作扩展（2026-03-31）
- `notch_cache`: Notch 渲染器缓存
- `notch_builder_cache`: Notch Builder 预览缓存
- `omniverse_cache`: NVIDIA Omniverse 缓存
- `mosys_tracker`: Mo-Sys StarTracker 缓存
- `sensapex_cache`: Sensapex 控制器缓存

### 新增多媒体工具（2026-03-31）
- `vlc_cache`: VLC 媒体播放器缓存
- `adobe_reader_cache`: Adobe Reader 缓存
- `libreoffice_cache`: LibreOffice 缓存

## 用户要求排除项（重要！）
- **Cookie 不扫描** - 所有浏览器扫描项均不包含 cookie 路径

## 技术备注
- 扫描项总数：119 个
- 使用通配符的路径会自动展开为多个具体路径
- 所有新增项均已设置风险等级和清理备注
