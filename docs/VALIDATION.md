# Validation report — desktop conversion

Validation for this project revision was performed in the executing Linux environment. The scientific core is platform-independent; the final Windows `.exe` must still be built on a Windows host with the supplied build script.

## Automated suite

```text
19 passed
```

The suite covers:

- exact ANF-derived core and proposed forward/inverse LUTs;
- independent Walsh and DDT computations;
- SAC, degree, term counts and fixed-point results;
- exhaustive simulation of both 28-gate networks on all 16 inputs;
- scalar/vectorized diffusion consistency;
- RGB/grayscale image round trips and ciphertext bundle reload;
- desktop entry-point/resource smoke tests;
- verification that the primary desktop application does not import Streamlit, Flask, or FastAPI.

## Desktop GUI smoke test

The Tkinter application was instantiated under a virtual X display and all eight workspaces were created successfully:

```text
Overview
Construction
Cryptographic Analysis
Benchmark Comparison
Logic Circuits
Image Encryption
Experiments
Affine Exploration
```

The active reference LUT was `4B8A6C72013E59FD`, and its analysis returned `NL = 4` during the GUI smoke test.

## Current validation environment

```json
{
  "platform": "Linux-6.18.44-x86_64-with-glibc2.41",
  "processor": "INTEL(R) XEON(R) PLATINUM 8573C",
  "machine": "x86_64",
  "logical_cpus": 5,
  "physical_memory_bytes": 6236880896,
  "python": "3.13.5",
  "libraries": {
    "numpy": "2.3.5",
    "pandas": "2.2.3",
    "Pillow": "12.3.0",
    "matplotlib": "3.10.8",
    "scipy": "1.17.0",
    "scikit-image": "0.26.0"
  },
  "protocol": "SBoxLab-image-v1"
}
```

## Windows EXE boundary

A genuine Windows executable was **not** fabricated in this Linux environment. The ZIP therefore contains the complete Windows-native source, `SBoxLab.spec`, `SBoxLab_onedir.spec`, and `build_exe.bat`. Running `build_exe.bat` on 64-bit Windows with Python 3.12 builds `dist\SBoxLab.exe` after running the numerical tests.

This distinction is deliberate: normal PyInstaller builds are platform-specific and do not produce a supported Windows `.exe` by cross-compiling from Linux.
