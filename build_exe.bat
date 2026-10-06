@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo  SBoxLab 4x4 Experimental Platform - Windows EXE builder
echo ============================================================

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher "py" was not found.
  echo Install 64-bit Python 3.12 from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

if not exist .venv-build\Scripts\python.exe (
  echo [1/5] Creating isolated build environment...
  py -3.12 -m venv .venv-build
)

echo [2/5] Updating packaging tools...
.venv-build\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail

echo [3/5] Installing SBoxLab dependencies and PyInstaller...
.venv-build\Scripts\python.exe -m pip install -r requirements-desktop.txt
if errorlevel 1 goto :fail

echo [4/5] Running numerical verification tests...
.venv-build\Scripts\python.exe -m pip install "pytest>=8,<10"
.venv-build\Scripts\python.exe -m pytest -q tests\test_core.py tests\test_cipher.py tests\test_desktop.py
if errorlevel 1 goto :fail

echo [5/5] Building SBoxLab.exe...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
.venv-build\Scripts\python.exe -m PyInstaller --noconfirm SBoxLab.spec
if errorlevel 1 goto :fail

echo.
echo SUCCESS: dist\SBoxLab.exe
echo Copy that single EXE to another Windows 10/11 x64 machine and run it.
echo No localhost, browser, Python installation, or internet connection is needed at runtime.
pause
exit /b 0

:fail
echo.
echo BUILD FAILED. Review the error messages above.
pause
exit /b 1
