@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>nul || (echo Python 3.12 is required.& pause & exit /b 1)
if not exist .venv-build\Scripts\python.exe py -3.12 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.venv-build\Scripts\python.exe -m pip install -r requirements-desktop.txt
if exist build rmdir /s /q build
if exist dist\SBoxLab rmdir /s /q dist\SBoxLab
.venv-build\Scripts\python.exe -m PyInstaller --noconfirm SBoxLab_onedir.spec
if errorlevel 1 (pause & exit /b 1)
echo Portable folder created: dist\SBoxLab\
pause
