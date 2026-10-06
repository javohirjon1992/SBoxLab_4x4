# SBoxLab 4×4 Experimental Platform

SBoxLab 4×4 Experimental Platform is an **English-language native desktop application** for the construction, evaluation, circuit verification, and two-round image experiments described in *Construction of S-Boxes with Bidirectionally Stable Strict Avalanche Properties Based on Affine Transformations*.

The primary interface is now **Tkinter desktop UI**. It does **not** use localhost, Streamlit, Flask, FastAPI, a browser, an API key, or a cloud service.

## Fastest use on Windows

### Run from source

Install 64-bit Python 3.12, extract the project, then double-click:

```text
run_windows.bat
```

The script creates `.venv`, installs the scientific dependencies, and opens the native SBoxLab window.

### Build a single EXE

Double-click:

```text
build_exe.bat
```

After the tests and PyInstaller build finish, the program is:

```text
dist\SBoxLab.exe
```

That EXE is intended to run on Windows 10/11 x64 without Python and without an internet connection. For a faster-starting portable folder build, use `build_onedir.bat` instead. See `BUILD_EXE.md`.

If the project is pushed to GitHub, **Actions → Build Windows EXE → Run workflow** builds `SBoxLab.exe` on an actual Windows runner and publishes it as the `SBoxLab-Windows-x64` artifact.

> A real Windows `.exe` should be built on Windows. PyInstaller does not normally cross-compile a Windows executable from Linux/macOS.

## Desktop workspaces

| Workspace | Available operations |
|---|---|
| Overview | Workflow and detected execution environment |
| Construction | Evaluate the Boolean ANF core; edit invertible GF(2) matrices and offsets; inspect all 16 intermediate mappings; export JSON |
| Cryptographic Analysis | Forward/inverse LUT, Walsh LAT, DDT, SAC, ANF, vectorial/coordinate NL, DU, DP, linear bias, degree, term counts, FP/OFP, BIC-related metrics |
| Benchmark Comparison | Recompute the manuscript benchmark LUTs and export CSV/LaTeX/ZIP |
| Logic Circuits | Simulate both fixed 28-gate circuits on all 16 inputs; inspect circuit images and netlists; export JSON, DOT, Verilog, BLIF; optionally invoke Berkeley ABC |
| Image Encryption | Load grayscale/RGB images, run two rounds, decrypt, verify exact recovery, save/reload ciphertext NPZ |
| Experiments | Batch up to four images; entropy, chi-square, correlation, plaintext/key sensitivity, exact recovery, warm-ups, real CPU timing, ZIP reports |
| Affine Exploration | Seeded bounded sampling of affine-equivalent representatives with forward/inverse SAC profiles |

The top-right selector changes the active S-box between the proposed S-box, its inverse, and a custom hexadecimal 4-bit permutation.

## Verified reference values

```text
Core G:     0123468B5CD7AF9E
Forward S:  4B8A6C72013E59FD
Inverse S:  897A0C462D315FBE
NL = 4
DU = 4
max differential probability = 0.25
max absolute Walsh LAT entry (nonzero masks) = 8
max absolute linear bias = 0.25
all 16 SAC entries = 0.5 in each direction
coordinate degrees = (3, 3, 3, 3)
FP = OFP = 0
28 gates and logic depth 7 in each direction
```

## Repository structure

```text
app.py                       Desktop launcher
desktop_app.py               Native Tkinter interface
SBoxLab.spec                 PyInstaller single-file EXE specification
SBoxLab_onedir.spec          PyInstaller portable-folder specification
build_exe.bat                Build + tests + single Windows EXE
build_onedir.bat             Build portable Windows folder
run_windows.bat              Run native desktop UI from source on Windows
run_unix.sh                  Run native desktop UI from source on Linux/macOS
requirements.txt             Runtime scientific packages
requirements-desktop.txt     Runtime packages + PyInstaller
sboxlab/core.py              ANF, affine maps, cryptographic metrics
sboxlab/cipher.py            Deterministic image protocol and invertible rounds
sboxlab/experiments.py       Statistics, sensitivity trials, actual-machine timing
sboxlab/circuits.py          Gate simulation and HDL/synthesis helpers
sboxlab/catalog.py           Comparison catalog
sboxlab/export.py            CSV/LaTeX/JSON/PNG/PDF/NPZ/ZIP exports
sboxlab/data/                Benchmark LUTs and exact gate netlists
assets/                      Circuit diagrams and application icon
tests/                       Numerical, cipher, resource, desktop smoke tests
legacy_web/app_streamlit.py  Preserved previous browser UI source
```

## Scientific/reproducibility notes

The algebraic S-box construction and gate equations are executable transcriptions and are exhaustively verified against all 16 inputs. Image experiments use the explicitly defined `SBoxLab-image-v1` protocol. Timing reports record the actual executing machine and exclude KDF/material derivation from timed encryption/decryption regions.

The image transform is a research construction, not production authenticated encryption. It has no authentication tag; a wrong key or modified ciphertext bundle cannot be reliably detected.

## Tests

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

