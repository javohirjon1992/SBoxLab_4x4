# Build a Windows EXE

SBoxLab 4×4 Experimental Platform is a native **Tkinter** application. It does not run a local web server and does not open a browser.

## Recommended: one-file EXE

1. Install **64-bit Python 3.12** from python.org and enable the Python launcher.
2. Extract this project to a normal writable folder (for example `C:\SBoxLab`).
3. Double-click `build_exe.bat`.
4. The finished program is `dist\SBoxLab.exe`.

The build script creates an isolated `.venv-build`, installs the pinned-range scientific dependencies, runs numerical tests, and invokes PyInstaller with `SBoxLab.spec`.

The generated `SBoxLab.exe` is self-contained for Windows 10/11 x64: the destination computer does not need Python, Streamlit, a browser, localhost, or an internet connection.

## Alternative: portable folder

Double-click `build_onedir.bat`. The result is `dist\SBoxLab\SBoxLab.exe` plus its dependency files. This form starts faster and is easier to troubleshoot, but the whole folder must be copied together.

## Development run without building

Double-click `run_windows.bat`. This creates `.venv` and launches the same native desktop UI using Python.

## Important platform note

A genuine Windows `.exe` should be built on Windows. The source ZIP can be prepared and verified on other operating systems, but PyInstaller does not cross-compile a Windows executable from Linux/macOS in the normal supported workflow.
