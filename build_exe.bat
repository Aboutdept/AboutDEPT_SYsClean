@echo off
REM ================================================================
REM  SysClean - PyInstaller onefile build script (ASCII only)
REM
REM  Usage:
REM     build_exe.bat          -> dist\SysClean.exe        (GUI, no console)
REM     build_exe.bat /all     -> also dist\SysClean_CLI.exe (console)
REM
REM  Requires a Python with tkinter. Override with:
REM     set SYSCLEAN_PYTHON=C:\path\to\python.exe
REM ================================================================
setlocal enabledelayedexpansion

set "PY="
if defined SYSCLEAN_PYTHON set "PY=%SYSCLEAN_PYTHON%"

if not defined PY if exist "C:\Users\missi\AppData\Local\Programs\Python\Python310\python.exe" set "PY=C:\Users\missi\AppData\Local\Programs\Python\Python310\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PY if exist "C:\Python310\python.exe" set "PY=C:\Python310\python.exe"
if not defined PY set "PY=python"

echo.
echo  ============================================
echo    SysClean - PyInstaller onefile build
echo  ============================================
echo.

if not exist "%PY%" (
    echo  [ERROR] Python not found: %PY%
    echo          Set SYSCLEAN_PYTHON to a valid python.exe
    pause
    exit /b 1
)

"%PY%" -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] This Python has no tkinter: %PY%
    echo          PyInstaller would build an exe that cannot start.
    echo          Install CPython from python.org and set SYSCLEAN_PYTHON.
    pause
    exit /b 1
)

"%PY%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] PyInstaller missing for: %PY%
    echo          Run: "%PY%" -m pip install pyinstaller
    pause
    exit /b 1
)

echo  [OK] Python    : %PY%
echo  [OK] tkinter   : yes
echo.

set "BUILD_CLI=0"
if /i "%1"=="/cli" set "BUILD_CLI=1"
if /i "%1"=="/all" set "BUILD_CLI=1"

echo  [1/2] Building SysClean.exe ...
"%PY%" -m PyInstaller SysClean.spec --noconfirm --clean
if errorlevel 1 goto failed

if "%BUILD_CLI%"=="0" goto skip_cli
echo  [2/2] Building SysClean_CLI.exe ...
"%PY%" -m PyInstaller SysClean_CLI.spec --noconfirm --clean
if errorlevel 1 goto failed
:skip_cli

echo.
echo  ============================================
echo    Build finished
echo  ============================================
echo.
for %%F in ("dist\SysClean.exe") do echo   SysClean.exe      %%~zF bytes
if "%BUILD_CLI%"=="1" for %%F in ("dist\SysClean_CLI.exe") do echo   SysClean_CLI.exe  %%~zF bytes
echo.
echo  Output folder: dist\
echo.
pause
exit /b 0

:failed
echo.
echo  [ERROR] Build failed. See messages above.
echo.
pause
exit /b 1
