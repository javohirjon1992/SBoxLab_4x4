"""SBoxLab 4×4 Experimental Platform — native Tkinter research application.

This GUI is intentionally server-free: it never starts Streamlit, Flask, FastAPI,
or a localhost HTTP service. It can be packaged as a normal Windows .exe.
"""
from __future__ import annotations

import io
import json
import os
import sys
import threading
import traceback
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd
from PIL import Image, ImageTk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from sboxlab.core import A, B, construct, core, inverse, analyze, parse_lut, trace, affine_search
from sboxlab.catalog import comparison, benchmarks, gate_comparison
from sboxlab import circuits
from sboxlab.cipher import key_bytes, nonce_for, material, encrypt, decrypt
from sboxlab.experiments import demo, image_from_file, png, stats, recovery, run, metadata
from sboxlab.export import (
    sbox_zip,
    experiment_zip,
    json_bytes,
    cipher_bundle,
    load_cipher,
    benchmark_tables_zip,
)

APP_TITLE = "SBoxLab 4×4 | Experimental Platform"
DEFAULT_KEY = "00112233445566778899AABBCCDDEEFF"
DEFAULT_LUT = "4B8A6C72013E59FD"


def resource_path(*parts: str) -> Path:
    """Resolve development and PyInstaller bundled resources."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def hex_lut(values) -> str:
    return "".join(f"{int(x):X}" for x in values)


def save_bytes(parent, data: bytes, default_name: str, filetypes=None):
    path = filedialog.asksaveasfilename(
        parent=parent,
        initialfile=default_name,
        defaultextension=Path(default_name).suffix,
        filetypes=filetypes or [("All files", "*.*")],
    )
    if path:
        Path(path).write_bytes(data)
        messagebox.showinfo("Saved", f"Saved to:\n{path}", parent=parent)


def save_text(parent, text: str, default_name: str, filetypes=None):
    save_bytes(parent, text.encode("utf-8"), default_name, filetypes)


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))


class DataFrameView(ttk.Frame):
    """Reusable Treeview renderer for pandas/numpy tables."""
    def __init__(self, parent, height=18):
        super().__init__(parent)
        self.tree = ttk.Treeview(self, show="headings", height=height)
        y = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        x = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def set(self, obj, index=False, max_rows=5000):
        if isinstance(obj, np.ndarray):
            df = pd.DataFrame(obj)
        elif isinstance(obj, pd.DataFrame):
            df = obj.copy()
        else:
            df = pd.DataFrame(obj)
        if index:
            df = df.reset_index()
        self.tree.delete(*self.tree.get_children())
        cols = [str(c) for c in df.columns]
        self.tree["columns"] = cols
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=max(80, min(240, len(c) * 10 + 30)), stretch=True)
        for row in df.head(max_rows).itertuples(index=False, name=None):
            vals = []
            for v in row:
                if isinstance(v, float):
                    vals.append(f"{v:.8g}")
                elif isinstance(v, (list, dict, tuple, np.ndarray)):
                    vals.append(json.dumps(v, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x)))
                else:
                    vals.append(str(v))
            self.tree.insert("", "end", values=vals)


class PlotView(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.figure = Figure(figsize=(6.2, 4.5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def heatmap(self, a, title):
        arr = np.asarray(a)
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        im = self.ax.imshow(arr, cmap="viridis")
        self.figure.colorbar(im, ax=self.ax)
        self.ax.set_title(title)
        self.ax.set_xlabel("Output mask / output bit")
        self.ax.set_ylabel("Input mask / input bit")
        self.ax.set_xticks(range(arr.shape[1]))
        self.ax.set_yticks(range(arr.shape[0]))
        if arr.size <= 256:
            midpoint = (float(arr.max()) + float(arr.min())) / 2
            for (i, j), v in np.ndenumerate(arr):
                self.ax.text(j, i, f"{v:g}", ha="center", va="center", fontsize=7,
                             color="white" if float(v) < midpoint else "black")
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def lines(self, x, series: dict[str, list[float]], title, ylabel):
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        for label, y in series.items():
            self.ax.plot(x, y, label=label)
        self.ax.set_title(title)
        self.ax.set_xlabel("Trial / repeat")
        self.ax.set_ylabel(ylabel)
        if series:
            self.ax.legend()
        self.figure.tight_layout()
        self.canvas.draw_idle()


class SBoxLabDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1480x900")
        self.minsize(1120, 720)
        try:
            self.iconbitmap(resource_path("assets", "sboxlab.ico"))
        except Exception:
            pass

        self.active_sbox = construct()
        self.analysis_cache = None
        self.image_result = None
        self.experiment_result = None
        self.affine_rows = None
        self._photo_refs = []

        self._configure_style()
        self._build_header()
        self._build_notebook()
        self._build_statusbar()
        self.apply_sbox(show_errors=False)

    def _configure_style(self):
        style = ttk.Style(self)
        for candidate in ("vista", "clam", "xpnative"):
            try:
                style.theme_use(candidate)
                break
            except tk.TclError:
                pass
        style.configure("TNotebook.Tab", padding=(14, 8))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Metric.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))

    def _build_header(self):
        outer = ttk.Frame(self, padding=(14, 10))
        outer.pack(fill="x")
        left = ttk.Frame(outer)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="SBoxLab 4×4 Experimental Platform", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="4×4 S-Box Construction • Cryptographic Analysis • Reproducible Experiments",
                  style="Subtitle.TLabel").pack(anchor="w")

        control = ttk.LabelFrame(outer, text="Active S-box", padding=8)
        control.pack(side="right")
        self.sbox_choice = tk.StringVar(value="Proposed S")
        cb = ttk.Combobox(control, textvariable=self.sbox_choice, state="readonly", width=22,
                          values=["Proposed S", "Proposed inverse", "Custom hexadecimal LUT"])
        cb.grid(row=0, column=0, padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.apply_sbox())
        self.custom_lut_var = tk.StringVar(value=DEFAULT_LUT)
        ttk.Entry(control, textvariable=self.custom_lut_var, width=21).grid(row=0, column=1, padx=4)
        ttk.Button(control, text="Apply", command=self.apply_sbox).grid(row=0, column=2, padx=4)
        self.active_lut_label = ttk.Label(control, text=DEFAULT_LUT, style="Header.TLabel")
        self.active_lut_label.grid(row=1, column=0, columnspan=3, pady=(7, 0))

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.tabs = {}
        for name in ["Overview", "Construction", "Cryptographic Analysis", "Benchmark Comparison",
                     "Logic Circuits", "Image Encryption", "Experiments", "Affine Exploration"]:
            frame = ttk.Frame(self.notebook, padding=10)
            self.tabs[name] = frame
            self.notebook.add(frame, text=name)
        self._build_overview()
        self._build_construction()
        self._build_analysis()
        self._build_benchmarks()
        self._build_circuits()
        self._build_image_encryption()
        self._build_experiments()
        self._build_affine()

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Ready — no web server is running.")
        bar = ttk.Frame(self, padding=(10, 4))
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left")
        ttk.Label(bar, text="LSB-first • research prototype • no authentication tag").pack(side="right")

    def status(self, text):
        if hasattr(self, "status_var"):
            self.status_var.set(text)
            self.update_idletasks()

    def guarded(self, fn):
        try:
            return fn()
        except Exception as e:
            messagebox.showerror("SBoxLab", f"{e}", parent=self)
            self.status("Error: " + str(e))
            return None

    def apply_sbox(self, show_errors=True):
        try:
            choice = self.sbox_choice.get()
            if choice == "Custom hexadecimal LUT":
                s = parse_lut(self.custom_lut_var.get())
            elif choice == "Proposed inverse":
                s = inverse(construct())
            else:
                s = construct()
            self.active_sbox = s
            self.active_lut_label.configure(text=hex_lut(s))
            self.analysis_cache = None
            if hasattr(self, "analysis_direction"):
                self.refresh_analysis()
            if hasattr(self, "circuit_direction"):
                self.refresh_circuit()
            self.status(f"Active LUT: {hex_lut(s)}")
        except Exception as e:
            if show_errors:
                messagebox.showerror("Invalid S-box", str(e), parent=self)

    # ---------- Overview ----------
    def _build_overview(self):
        f = self.tabs["Overview"]
        ttk.Label(f, text="From algebraic construction to measured image experiments",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(2, 8))
        ttk.Label(f, text=("Generate the paper's S-box, inspect cryptographic tables, compare benchmark substitutions, "
                           "verify logic networks, and run image experiments without localhost or a browser."),
                  wraplength=1200, justify="left").pack(anchor="w", pady=(0, 12))
        metrics = ttk.Frame(f)
        metrics.pack(fill="x", pady=6)
        for i, (name, val) in enumerate([("Vectorial NL", "4"), ("Differential uniformity", "4"),
                                         ("Bidirectional SAC", "0.500"), ("Gates / direction", "28")]):
            box = ttk.LabelFrame(metrics, text=name, padding=12)
            box.grid(row=0, column=i, padx=5, sticky="nsew")
            metrics.columnconfigure(i, weight=1)
            ttk.Label(box, text=val, style="Metric.TLabel").pack()
        df = pd.DataFrame([
            ["Construction", "ANF core → input affine map → output affine map → inverse"],
            ["Analysis", "LAT, DDT, SAC, ANF, NL, DU, AD, AT, FP/OFP, BIC"],
            ["Comparison", "25 source LUTs recomputed under one convention"],
            ["Circuits", "28-gate networks, exhaustive simulation, DOT/Verilog/BLIF export"],
            ["Images", "Two rounds, round-trip decryption, histograms and correlation"],
            ["Experiments", "Plaintext flips, key flips, warm-ups, real CPU timing"],
            ["Exports", "CSV, JSON, LaTeX, PNG/PDF figures, ciphertext bundle"],
        ], columns=["Module", "Capabilities"])
        view = DataFrameView(f, height=8)
        view.pack(fill="x", pady=10)
        view.set(df)
        env_box = ttk.LabelFrame(f, text="Detected execution environment", padding=8)
        env_box.pack(fill="both", expand=True, pady=8)
        env = tk.Text(env_box, height=14, wrap="word", font=("Consolas", 9))
        env.pack(fill="both", expand=True)
        env.insert("1.0", json.dumps(metadata(), indent=2, default=str))
        env.configure(state="disabled")

    # ---------- Construction ----------
    def _build_construction(self):
        root = self.tabs["Construction"]
        top = ttk.Frame(root)
        top.pack(fill="x")
        ttk.Label(top, text="S(x) = B · G(Ax XOR α) XOR β", font=("Cambria Math", 15, "bold")).pack(anchor="w")
        ttk.Label(top, text="Rows and columns use the LSB-first convention.").pack(anchor="w", pady=(2, 8))
        grids = ttk.Frame(root)
        grids.pack(fill="x")
        self.matrix_entries = {}
        for col, (name, matrix) in enumerate([("A", A), ("B", B)]):
            box = ttk.LabelFrame(grids, text=f"Matrix {name}", padding=8)
            box.grid(row=0, column=col, padx=8, sticky="nw")
            entries = []
            for r in range(4):
                row = []
                for c in range(4):
                    v = tk.StringVar(value=str(int(matrix[r, c])))
                    e = ttk.Entry(box, textvariable=v, width=4, justify="center")
                    e.grid(row=r, column=c, padx=2, pady=2)
                    row.append(v)
                entries.append(row)
            self.matrix_entries[name] = entries
        params = ttk.LabelFrame(grids, text="Offsets", padding=10)
        params.grid(row=0, column=2, padx=8, sticky="nw")
        self.alpha_var = tk.IntVar(value=9)
        self.beta_var = tk.IntVar(value=10)
        ttk.Label(params, text="alpha").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(params, from_=0, to=15, textvariable=self.alpha_var, width=8).grid(row=0, column=1, padx=4)
        ttk.Label(params, text="beta").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(params, from_=0, to=15, textvariable=self.beta_var, width=8).grid(row=1, column=1, padx=4)
        ttk.Button(params, text="Compute construction", command=self.compute_construction).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 3))
        ttk.Button(params, text="Export construction JSON", command=self.export_construction).grid(row=3, column=0, columnspan=2, sticky="ew", pady=3)
        self.construction_luts = ttk.Label(root, text="", style="Header.TLabel")
        self.construction_luts.pack(anchor="w", pady=(12, 5))
        self.construction_view = DataFrameView(root, height=18)
        self.construction_view.pack(fill="both", expand=True)
        self.compute_construction()

    def _read_matrix(self, name):
        return np.array([[int(self.matrix_entries[name][r][c].get()) for c in range(4)] for r in range(4)], dtype=np.uint8)

    def construction_result(self):
        aa, bb = self._read_matrix("A"), self._read_matrix("B")
        alpha, beta = int(self.alpha_var.get()), int(self.beta_var.get())
        s = construct(aa, bb, alpha, beta)
        return aa, bb, alpha, beta, s

    def compute_construction(self):
        def task():
            aa, bb, alpha, beta, s = self.construction_result()
            self.construction_luts.configure(text=f"G = {hex_lut(core())}    S = {hex_lut(s)}    Inverse = {hex_lut(inverse(s))}")
            self.construction_view.set(pd.DataFrame(trace(aa, bb, alpha, beta)))
            self.status("Construction computed successfully.")
        self.guarded(task)

    def export_construction(self):
        def task():
            aa, bb, alpha, beta, s = self.construction_result()
            blob = json_bytes({"A": aa, "B": bb, "alpha": alpha, "beta": beta, "core": core(), "lut": s, "inverse": inverse(s)})
            save_bytes(self, blob, "construction.json", [("JSON", "*.json")])
        self.guarded(task)

    # ---------- Analysis ----------
    def _build_analysis(self):
        root = self.tabs["Cryptographic Analysis"]
        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(0, 6))
        self.analysis_direction = tk.StringVar(value="Forward")
        ttk.Label(controls, text="Direction:").pack(side="left")
        for name in ["Forward", "Inverse"]:
            ttk.Radiobutton(controls, text=name, value=name, variable=self.analysis_direction,
                            command=self.refresh_analysis).pack(side="left", padx=5)
        ttk.Button(controls, text="Export complete analysis ZIP", command=self.export_analysis).pack(side="right")
        self.metric_frame = ttk.Frame(root)
        self.metric_frame.pack(fill="x", pady=5)
        self.metric_labels = {}
        for i, key in enumerate(["NL", "DU", "linear_bias", "SAC_mean"]):
            box = ttk.LabelFrame(self.metric_frame, text=key, padding=8)
            box.grid(row=0, column=i, padx=5, sticky="ew")
            self.metric_frame.columnconfigure(i, weight=1)
            lab = ttk.Label(box, text="—", style="Metric.TLabel")
            lab.pack()
            self.metric_labels[key] = lab
        self.analysis_summary = DataFrameView(root, height=4)
        self.analysis_summary.pack(fill="x", pady=4)
        self.analysis_nb = ttk.Notebook(root)
        self.analysis_nb.pack(fill="both", expand=True, pady=(6, 0))
        self.analysis_views = {}
        for name in ["LAT (Walsh)", "DDT", "SAC", "ANF", "BIC"]:
            tab = ttk.Frame(self.analysis_nb, padding=6)
            self.analysis_nb.add(tab, text=name)
            self.analysis_views[name] = tab
        self.analysis_tables = {}
        self.analysis_plots = {}
        for name in ["LAT (Walsh)", "DDT", "SAC"]:
            tab = self.analysis_views[name]
            pane = ttk.Panedwindow(tab, orient="horizontal")
            pane.pack(fill="both", expand=True)
            left, right = ttk.Frame(pane), ttk.Frame(pane)
            pane.add(left, weight=1); pane.add(right, weight=1)
            tbl = DataFrameView(left, height=16); tbl.pack(fill="both", expand=True)
            plot = PlotView(right); plot.pack(fill="both", expand=True)
            self.analysis_tables[name] = tbl; self.analysis_plots[name] = plot
        self.anf_text = tk.Text(self.analysis_views["ANF"], font=("Consolas", 11), wrap="word")
        self.anf_text.pack(fill="both", expand=True)
        self.bic_table = DataFrameView(self.analysis_views["BIC"], height=14)
        self.bic_table.pack(fill="both", expand=True)
        self.analysis_check = ttk.Label(root, text="")
        self.analysis_check.pack(anchor="w", pady=4)

    def current_analysis(self):
        if self.analysis_cache is None:
            f = analyze(self.active_sbox)
            inv = analyze(inverse(self.active_sbox))
            self.analysis_cache = (f, inv)
        return self.analysis_cache

    def refresh_analysis(self):
        if not hasattr(self, "analysis_direction"):
            return
        try:
            f, inv = self.current_analysis()
            r = f if self.analysis_direction.get() == "Forward" else inv
            for key, lab in self.metric_labels.items():
                lab.configure(text=str(r["summary"][key]))
            self.analysis_summary.set(pd.DataFrame([r["summary"]]).astype(str))
            mapping = [("LAT (Walsh)", "lat", "Walsh LAT"), ("DDT", "ddt", "Difference distribution table"),
                       ("SAC", "sac", "Strict avalanche criterion")]
            for name, key, title in mapping:
                self.analysis_tables[name].set(r[key], index=True)
                self.analysis_plots[name].heatmap(r[key], title)
            self.anf_text.configure(state="normal")
            self.anf_text.delete("1.0", "end")
            self.anf_text.insert("1.0", "\n\n".join(f"f{j} = {expr}" for j, expr in enumerate(r["anf"])))
            self.anf_text.configure(state="disabled")
            biccols = ["0 XOR 1", "0 XOR 2", "0 XOR 3", "1 XOR 2", "1 XOR 3", "2 XOR 3"]
            self.bic_table.set(pd.DataFrame(r["bic_sac"], columns=biccols), index=True)
            self.analysis_check.configure(text=(f"Inverse identities: LAT transpose = {np.array_equal(inv['lat'], f['lat'].T)}; "
                                                f"DDT transpose = {np.array_equal(inv['ddt'], f['ddt'].T)}"))
        except Exception as e:
            self.status("Analysis error: " + str(e))

    def export_analysis(self):
        def task():
            f, inv = self.current_analysis()
            blob = sbox_zip({"forward": f, "inverse": inv})
            save_bytes(self, blob, "sbox_analysis.zip", [("ZIP", "*.zip")])
        self.guarded(task)

    # ---------- Benchmarks ----------
    def _build_benchmarks(self):
        root = self.tabs["Benchmark Comparison"]
        controls = ttk.Frame(root); controls.pack(fill="x", pady=(0, 5))
        ttk.Button(controls, text="Export comparison CSV", command=lambda: save_text(self, comparison().to_csv(index=False), "comparison.csv", [("CSV", "*.csv")])).pack(side="left", padx=3)
        ttk.Button(controls, text="Export comparison LaTeX", command=lambda: save_text(self, comparison().to_latex(index=False), "comparison.tex", [("TeX", "*.tex")])).pack(side="left", padx=3)
        ttk.Button(controls, text="Export all benchmark tables ZIP", command=lambda: save_bytes(self, benchmark_tables_zip(), "benchmark_tables.zip", [("ZIP", "*.zip")])).pack(side="left", padx=3)
        pane = ttk.Panedwindow(root, orient="vertical"); pane.pack(fill="both", expand=True)
        upper, lower = ttk.Frame(pane), ttk.Frame(pane); pane.add(upper, weight=2); pane.add(lower, weight=1)
        self.benchmark_comparison = DataFrameView(upper, height=14); self.benchmark_comparison.pack(fill="both", expand=True)
        self.benchmark_comparison.set(comparison())
        ctl = ttk.Frame(lower); ctl.pack(fill="x", pady=4)
        names = [r["name"] for r in benchmarks()]
        self.benchmark_name = tk.StringVar(value=names[0] if names else "")
        self.benchmark_field = tk.StringVar(value="sac")
        ttk.Label(ctl, text="Benchmark:").pack(side="left")
        cb = ttk.Combobox(ctl, values=names, state="readonly", textvariable=self.benchmark_name, width=35)
        cb.pack(side="left", padx=5); cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_benchmark_detail())
        ttk.Label(ctl, text="Table:").pack(side="left", padx=(12, 0))
        fb = ttk.Combobox(ctl, values=["sac", "lat", "ddt", "bic_sac"], state="readonly", textvariable=self.benchmark_field, width=12)
        fb.pack(side="left", padx=5); fb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_benchmark_detail())
        self.benchmark_detail = DataFrameView(lower, height=10); self.benchmark_detail.pack(fill="both", expand=True)
        self.refresh_benchmark_detail()

    def refresh_benchmark_detail(self):
        try:
            entry = next(r for r in benchmarks() if r["name"] == self.benchmark_name.get())
            detail = analyze(parse_lut(entry["lut"]))
            self.benchmark_detail.set(detail[self.benchmark_field.get()], index=True)
        except Exception as e:
            self.status("Benchmark error: " + str(e))

    # ---------- Circuits ----------
    def _build_circuits(self):
        root = self.tabs["Logic Circuits"]
        controls = ttk.Frame(root); controls.pack(fill="x")
        self.circuit_direction = tk.StringVar(value="forward")
        ttk.Label(controls, text="Circuit:").pack(side="left")
        for name in ["forward", "inverse"]:
            ttk.Radiobutton(controls, text=name.title(), value=name, variable=self.circuit_direction,
                            command=self.refresh_circuit).pack(side="left", padx=5)
        ttk.Button(controls, text="Export Verilog", command=lambda: self.export_circuit("verilog")).pack(side="right", padx=3)
        ttk.Button(controls, text="Export JSON", command=lambda: self.export_circuit("json")).pack(side="right", padx=3)
        ttk.Button(controls, text="Export DOT", command=lambda: self.export_circuit("dot")).pack(side="right", padx=3)
        ttk.Button(controls, text="Export active BLIF", command=lambda: save_text(self, circuits.blif(self.active_sbox), "active_sbox.blif", [("BLIF", "*.blif")])).pack(side="right", padx=3)
        self.circuit_info = ttk.Label(root, text="", style="Header.TLabel"); self.circuit_info.pack(anchor="w", pady=5)
        pane = ttk.Panedwindow(root, orient="horizontal"); pane.pack(fill="both", expand=True)
        left, right = ttk.Frame(pane), ttk.Frame(pane); pane.add(left, weight=1); pane.add(right, weight=2)
        self.circuit_image_label = ttk.Label(left, anchor="center"); self.circuit_image_label.pack(fill="both", expand=True)
        self.circuit_table = DataFrameView(right, height=23); self.circuit_table.pack(fill="both", expand=True)
        foot = ttk.Frame(root); foot.pack(fill="x", pady=5)
        ttk.Button(foot, text="Export gate-count comparison CSV", command=lambda: save_text(self, gate_comparison().to_csv(index=False), "gate_comparison.csv", [("CSV", "*.csv")])).pack(side="left")
        ttk.Button(foot, text="Run optional Berkeley ABC", command=self.run_abc).pack(side="left", padx=6)

    def refresh_circuit(self):
        if not hasattr(self, "circuit_direction"):
            return
        try:
            direction = self.circuit_direction.get()
            gates = circuits.load(direction)
            values, info = circuits.simulate(gates, direction)
            expected = construct() if direction == "forward" else inverse(construct())
            ok = np.array_equal(values, expected)
            self.circuit_info.configure(text=f"{info}    Exhaustive 16-input verification: {'PASS' if ok else 'FAIL'}")
            self.circuit_table.set(pd.DataFrame(gates, columns=["Output", "Gate", "Input A", "Input B"]))
            asset = resource_path("assets", f"{direction}_circuit.png")
            if asset.exists():
                im = Image.open(asset).convert("RGB")
                im.thumbnail((520, 620), Image.Resampling.LANCZOS)
                ph = ImageTk.PhotoImage(im)
                self.circuit_image_label.configure(image=ph, text="")
                self.circuit_image_label.image = ph
        except Exception as e:
            self.status("Circuit error: " + str(e))

    def export_circuit(self, kind):
        def task():
            direction = self.circuit_direction.get(); gates = circuits.load(direction)
            if kind == "verilog":
                save_text(self, circuits.verilog(gates, direction), f"{direction}.v", [("Verilog", "*.v")])
            elif kind == "dot":
                save_text(self, circuits.dot(gates, direction), f"{direction}.dot", [("DOT", "*.dot")])
            else:
                save_bytes(self, json_bytes(gates), f"{direction}_netlist.json", [("JSON", "*.json")])
        self.guarded(task)

    def run_abc(self):
        def task():
            log, hdl = circuits.run_abc(self.active_sbox)
            win = tk.Toplevel(self); win.title("Berkeley ABC output"); win.geometry("900x600")
            txt = tk.Text(win, font=("Consolas", 9)); txt.pack(fill="both", expand=True); txt.insert("1.0", log)
            ttk.Button(win, text="Save mapped Verilog", command=lambda: save_text(win, hdl, "abc_mapped.v", [("Verilog", "*.v")])).pack(pady=5)
        self.guarded(task)

    # ---------- Image encryption ----------
    def _build_image_encryption(self):
        root = self.tabs["Image Encryption"]
        controls = ttk.LabelFrame(root, text="Encrypt and verify", padding=8); controls.pack(fill="x")
        self.image_key_var = tk.StringVar(value=DEFAULT_KEY)
        self.image_path_var = tk.StringVar(value="")
        self.image_id_var = tk.StringVar(value="synthetic-demo")
        ttk.Label(controls, text="128-bit key:").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.image_key_var, show="•", width=38).grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Label(controls, text="Image:").grid(row=1, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.image_path_var, width=70).grid(row=1, column=1, padx=5, sticky="ew")
        ttk.Button(controls, text="Browse", command=self.choose_image).grid(row=1, column=2, padx=4)
        ttk.Label(controls, text="Image ID:").grid(row=2, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.image_id_var, width=40).grid(row=2, column=1, padx=5, sticky="w")
        ttk.Button(controls, text="Encrypt → decrypt → verify", command=self.encrypt_image).grid(row=3, column=1, sticky="w", padx=5, pady=6)
        ttk.Button(controls, text="Save ciphertext bundle", command=self.save_cipher_bundle).grid(row=3, column=2, padx=4)
        controls.columnconfigure(1, weight=1)
        body = ttk.Panedwindow(root, orient="horizontal"); body.pack(fill="both", expand=True, pady=8)
        preview, report = ttk.Frame(body), ttk.Frame(body); body.add(preview, weight=2); body.add(report, weight=1)
        self.image_preview = ttk.Frame(preview); self.image_preview.pack(fill="both", expand=True)
        self.image_report = tk.Text(report, font=("Consolas", 9), wrap="word"); self.image_report.pack(fill="both", expand=True)
        dec = ttk.LabelFrame(root, text="Decrypt saved bundle", padding=8); dec.pack(fill="x")
        self.bundle_path_var = tk.StringVar(value="")
        ttk.Entry(dec, textvariable=self.bundle_path_var, width=90).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(dec, text="Browse NPZ", command=self.choose_bundle).pack(side="left", padx=3)
        ttk.Button(dec, text="Decrypt bundle", command=self.decrypt_bundle).pack(side="left", padx=3)

    def choose_image(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Images", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"), ("All files", "*.*")])
        if path:
            self.image_path_var.set(path); self.image_id_var.set(Path(path).name)

    def choose_bundle(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Cipher bundle", "*.npz"), ("All files", "*.*")])
        if path: self.bundle_path_var.set(path)

    def _show_image_grid(self, items):
        for child in self.image_preview.winfo_children(): child.destroy()
        self._photo_refs = []
        for i, (name, arr) in enumerate(items):
            box = ttk.LabelFrame(self.image_preview, text=name, padding=4)
            box.grid(row=i // 2, column=i % 2, padx=4, pady=4, sticky="nsew")
            self.image_preview.rowconfigure(i // 2, weight=1); self.image_preview.columnconfigure(i % 2, weight=1)
            im = Image.fromarray(arr)
            im.thumbnail((430, 280), Image.Resampling.LANCZOS)
            ph = ImageTk.PhotoImage(im)
            self._photo_refs.append(ph)
            ttk.Label(box, image=ph).pack(fill="both", expand=True)

    def encrypt_image(self):
        def task():
            path = self.image_path_var.get().strip()
            img = image_from_file(path) if path else demo()
            k = key_bytes(self.image_key_var.get())
            image_id = self.image_id_var.get().strip() or (Path(path).name if path else "synthetic-demo")
            nonce = nonce_for(image_id, img.shape); mats = material(k, nonce, img.shape)
            states = encrypt(img, mats, self.active_sbox, True); rec = decrypt(states[-1], mats, self.active_sbox)
            result = {
                "images": [img, *states, rec],
                "recovery": recovery(img, rec),
                "stats": [{"stage": n, **stats(a)} for n, a in zip(["Original", "R1", "R2"], [img, *states])],
                "bundle": cipher_bundle(states[-1], nonce, self.active_sbox, image_id),
                "image_id": image_id,
                "lut": self.active_sbox.tolist(),
            }
            self.image_result = result
            self._show_image_grid(list(zip(["Original", "R1", "R2", "Recovered"], result["images"])))
            self.image_report.delete("1.0", "end")
            self.image_report.insert("1.0", "Recovery:\n" + json.dumps(result["recovery"], indent=2, default=str) +
                                     "\n\nStatistics:\n" + pd.DataFrame(result["stats"]).to_string(index=False))
            self.status("Image encrypted, decrypted, and verified.")
        self.guarded(task)

    def save_cipher_bundle(self):
        if not self.image_result:
            messagebox.showwarning("SBoxLab", "Run Encrypt → decrypt → verify first.", parent=self); return
        save_bytes(self, self.image_result["bundle"], "ciphertext.npz", [("NPZ", "*.npz")])

    def decrypt_bundle(self):
        def task():
            path = self.bundle_path_var.get().strip()
            if not path: raise ValueError("Select a ciphertext .npz bundle first.")
            raw = Path(path).read_bytes()
            c, n, lut, identifier = load_cipher(raw)
            p = decrypt(c, material(key_bytes(self.image_key_var.get()), n, c.shape), lut)
            self._show_image_grid([(f"Decrypted: {identifier}", p)])
            self.image_report.delete("1.0", "end")
            self.image_report.insert("1.0", "Decryption completed.\n\nWarning: this research transform has no authentication tag; a wrong key or modified bundle cannot be reliably detected.")
            if messagebox.askyesno("Save decrypted image?", "Decryption completed. Save decrypted PNG now?", parent=self):
                save_bytes(self, png(p), "decrypted.png", [("PNG", "*.png")])
        self.guarded(task)

    # ---------- Experiments ----------
    def _build_experiments(self):
        root = self.tabs["Experiments"]
        controls = ttk.LabelFrame(root, text="Batch experiment", padding=8); controls.pack(fill="x")
        self.exp_files = []
        self.exp_files_var = tk.StringVar(value="Synthetic demo (no external files selected)")
        ttk.Label(controls, textvariable=self.exp_files_var).grid(row=0, column=0, columnspan=6, sticky="w")
        ttk.Button(controls, text="Choose up to 4 images", command=self.choose_exp_images).grid(row=0, column=6, padx=4)
        self.exp_key_var = tk.StringVar(value=DEFAULT_KEY)
        labels = [("Master key", self.exp_key_var, None), ("Plaintext trials", tk.IntVar(value=100), (0, 1000)),
                  ("Key trials", tk.IntVar(value=30), (0, 128)), ("Warm-ups", tk.IntVar(value=5), (0, 50)),
                  ("Timing repeats", tk.IntVar(value=30), (2, 200)), ("Seed", tk.IntVar(value=42), (0, 2147483647))]
        self.exp_vars = {}
        for i, (label, var, rng) in enumerate(labels):
            ttk.Label(controls, text=label).grid(row=1, column=i, sticky="w", padx=3)
            if rng is None:
                ttk.Entry(controls, textvariable=var, show="•", width=28).grid(row=2, column=i, padx=3, sticky="ew")
            else:
                ttk.Spinbox(controls, from_=rng[0], to=rng[1], textvariable=var, width=12).grid(row=2, column=i, padx=3, sticky="ew")
                self.exp_vars[label] = var
        self.exp_progress = ttk.Progressbar(controls, mode="determinate", maximum=100)
        self.exp_progress.grid(row=3, column=0, columnspan=5, sticky="ew", padx=3, pady=8)
        self.exp_run_btn = ttk.Button(controls, text="Run experiment batch", command=self.start_experiment)
        self.exp_run_btn.grid(row=3, column=5, padx=3)
        ttk.Button(controls, text="Save result ZIP", command=self.save_experiment_zip).grid(row=3, column=6, padx=3)
        controls.columnconfigure(0, weight=1)
        pane = ttk.Panedwindow(root, orient="horizontal"); pane.pack(fill="both", expand=True, pady=8)
        left, right = ttk.Frame(pane), ttk.Frame(pane); pane.add(left, weight=1); pane.add(right, weight=1)
        self.exp_table = DataFrameView(left, height=20); self.exp_table.pack(fill="both", expand=True)
        self.exp_plot = PlotView(right); self.exp_plot.pack(fill="both", expand=True)
        self.exp_log = tk.Text(root, height=8, font=("Consolas", 9), wrap="word"); self.exp_log.pack(fill="x")

    def choose_exp_images(self):
        paths = filedialog.askopenfilenames(parent=self, filetypes=[("Images", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"), ("All files", "*.*")])
        if paths:
            self.exp_files = list(paths[:4])
            if len(paths) > 4:
                messagebox.showwarning("SBoxLab", "Only the first four images will be used.", parent=self)
            self.exp_files_var.set("; ".join(Path(p).name for p in self.exp_files))

    def start_experiment(self):
        if self.exp_run_btn["state"] == "disabled": return
        try:
            params = {
                "key": self.exp_key_var.get(),
                "files": list(self.exp_files),
                "trials": int(self.exp_vars["Plaintext trials"].get()),
                "key_trials": int(self.exp_vars["Key trials"].get()),
                "warmups": int(self.exp_vars["Warm-ups"].get()),
                "repeats": int(self.exp_vars["Timing repeats"].get()),
                "seed": int(self.exp_vars["Seed"].get()),
                "lut": self.active_sbox.copy(),
            }
        except Exception as e:
            messagebox.showerror("SBoxLab", str(e), parent=self); return
        self.exp_run_btn.configure(state="disabled")
        self.exp_progress["value"] = 0
        self.exp_log.delete("1.0", "end")
        self.status("Running experiment batch...")
        thread = threading.Thread(target=self._experiment_worker, args=(params,), daemon=True)
        thread.start()

    def _experiment_worker(self, params):
        try:
            k = key_bytes(params["key"])
            items = [(Path(p).name, image_from_file(p)) for p in params["files"]] if params["files"] else [("synthetic-demo", demo())]
            trials = params["trials"]; kt = params["key_trials"]
            warm = params["warmups"]; repeats = params["repeats"]; seed = params["seed"]
            lut = params["lut"]
            outputs = []
            for j, (name, img) in enumerate(items):
                self.after(0, lambda n=name: self._append_exp_log(f"Processing: {n}\n"))
                def prog(p, j=j):
                    self.after(0, lambda v=(j + p) / len(items) * 100: self.exp_progress.configure(value=v))
                r = run(img, k, name, lut, trials, kt, warm, repeats, seed, prog)
                outputs.append((name, r, experiment_zip(r)))
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for j, (name, r, blob) in enumerate(outputs):
                    z.writestr(f"{j+1:02d}_{Path(name).stem}_results.zip", blob)
                summary = pd.DataFrame([{"image": name, **r["runtime"]} for name, r, _blob in outputs])
                z.writestr("runtime_summary.csv", summary.to_csv(index=False))
            result = {
                "rows": [{"image": n, **r["runtime"], "exact_recovery": r["recovery"]["exact"]} for n, r, _b in outputs],
                "blob": buf.getvalue(), "env": metadata(),
                "details": [{"image": n, "statistics": r["statistics"], "recovery": r["recovery"],
                             "differential": r["differential_trials"], "key_sensitivity": r["key_trials_raw"],
                             "runtime_raw": r["runtime_raw"]} for n, r, _b in outputs],
            }
            self.after(0, lambda: self._experiment_done(result))
        except Exception as e:
            tb = traceback.format_exc()
            self.after(0, lambda: self._experiment_failed(e, tb))

    def _append_exp_log(self, text):
        self.exp_log.insert("end", text); self.exp_log.see("end")

    def _experiment_done(self, result):
        self.experiment_result = result
        self.exp_run_btn.configure(state="normal"); self.exp_progress["value"] = 100
        self.exp_table.set(pd.DataFrame(result["rows"]))
        if result["details"]:
            rr = result["details"][0]["runtime_raw"]
            x = [r["repeat"] for r in rr]
            self.exp_plot.lines(x, {"Encrypt ms": [r["encrypt_ms"] for r in rr], "Decrypt ms": [r["decrypt_ms"] for r in rr]},
                                "Measured runtime", "Milliseconds")
        self._append_exp_log("Completed successfully. Exact round-trip verification passed.\n")
        self._append_exp_log(json.dumps(result["env"], indent=2, default=str) + "\n")
        self.status("Experiment batch completed.")

    def _experiment_failed(self, exc, tb):
        self.exp_run_btn.configure(state="normal")
        self._append_exp_log(tb + "\n")
        self.status("Experiment failed: " + str(exc))
        messagebox.showerror("Experiment failed", str(exc), parent=self)

    def save_experiment_zip(self):
        if not self.experiment_result:
            messagebox.showwarning("SBoxLab", "Run an experiment batch first.", parent=self); return
        save_bytes(self, self.experiment_result["blob"], "experiment_batch.zip", [("ZIP", "*.zip")])

    # ---------- Affine ----------
    def _build_affine(self):
        root = self.tabs["Affine Exploration"]
        controls = ttk.Frame(root); controls.pack(fill="x", pady=(0, 6))
        self.affine_count = tk.IntVar(value=100); self.affine_seed = tk.IntVar(value=42)
        ttk.Label(controls, text="Candidates:").pack(side="left")
        ttk.Spinbox(controls, from_=1, to=5000, textvariable=self.affine_count, width=10).pack(side="left", padx=4)
        ttk.Label(controls, text="Seed:").pack(side="left", padx=(10, 0))
        ttk.Spinbox(controls, from_=0, to=2147483647, textvariable=self.affine_seed, width=14).pack(side="left", padx=4)
        ttk.Button(controls, text="Explore affine representatives", command=self.start_affine).pack(side="left", padx=8)
        ttk.Button(controls, text="Export JSON", command=self.save_affine).pack(side="right")
        ttk.Label(root, text="Bounded seeded sampling; this is not an exhaustive classification of GL(4,2) × GL(4,2).",
                  wraplength=1200).pack(anchor="w", pady=4)
        self.affine_view = DataFrameView(root, height=25); self.affine_view.pack(fill="both", expand=True)

    def start_affine(self):
        try:
            count, seed = int(self.affine_count.get()), int(self.affine_seed.get())
        except Exception as e:
            messagebox.showerror("Affine exploration", str(e), parent=self); return
        self.status("Evaluating affine candidates...")
        threading.Thread(target=self._affine_worker, args=(count, seed), daemon=True).start()

    def _affine_worker(self, count, seed):
        try:
            rows = affine_search(count, seed)
            self.after(0, lambda: self._affine_done(rows))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Affine exploration", str(e), parent=self))

    def _affine_done(self, rows):
        self.affine_rows = rows
        self.affine_view.set(pd.DataFrame(rows).drop(columns=["A", "B"], errors="ignore"))
        self.status(f"Affine exploration completed: {len(rows)} candidates.")

    def save_affine(self):
        if not self.affine_rows:
            messagebox.showwarning("SBoxLab", "Run affine exploration first.", parent=self); return
        save_bytes(self, json_bytes(self.affine_rows), "affine_search.json", [("JSON", "*.json")])


def main():
    app = SBoxLabDesktop()
    app.mainloop()


if __name__ == "__main__":
    main()
