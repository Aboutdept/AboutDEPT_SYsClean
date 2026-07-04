@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ================================================================
::  SysClean - Nuitka 单文件打包脚本
::  输出: dist\SysClean.exe
:: ================================================================

set "APP_NAME=SysClean"
set "ENTRY=main.py"
set "ICON=icon.ico"
set "DIST_DIR=dist"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║     SysClean - Nuitka Build                      ║
echo  ╚══════════════════════════════════════════════════╝
echo.

:: 检查入口文件
if not exist "%ENTRY%" (
    echo  [ERROR] 找不到 %ENTRY%
    pause
    exit /b 1
)

:: 检查图标文件
if not exist "%ICON%" (
    echo  [WARN]  找不到 %ICON%，将不嵌入图标
    set "ICON_OPT="
    set "DATA_OPT="
) else (
    echo  [OK] 图标: %ICON%
    set "ICON_OPT=--windows-icon-from-ico=%ICON%"
    set "DATA_OPT=--include-data-files=%ICON%=%ICON%"
)

:: 检查 nuitka
where nuitka >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] 未找到 nuitka，请先安装: pip install nuitka
    pause
    exit /b 1
)

echo  [OK] 开始打包...
echo.

:: 清理旧构建
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "main.build" rmdir /s /q "main.build"
if exist "main.onefile-build" rmdir /s /q "main.onefile-build"

:: Nuitka 打包
python -m nuitka ^
    --standalone ^
    --onefile ^
    %ICON_OPT% ^
    --windows-console-mode=disable ^
    --windows-uac-admin ^
    --output-dir=%DIST_DIR% ^
    --output-filename=%APP_NAME%.exe ^
    --company-name="AboutDEPT" ^
    --product-name="SysClean" ^
    --file-description="SysClean - 系统垃圾文件扫描与清理工具" ^
    --file-version=1.0.0.0 ^
    --product-version=1.0.0.0 ^
    --enable-plugin=tk-inter ^
    %DATA_OPT% ^
    --remove-output ^
    %ENTRY%

if errorlevel 1 (
    echo.
    echo  [ERROR] 打包失败！
    pause
    exit /b 1
)

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║  打包完成                                        ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  输出: %DIST_DIR%\%APP_NAME%.exe

for %%F in ("%DIST_DIR%\%APP_NAME%.exe") do echo  大小: %%~zF bytes
echo.

pause
