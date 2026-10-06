from pathlib import Path
import ast
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_entry_is_server_free():
    src = (ROOT / 'desktop_app.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split('.')[0])
    assert 'streamlit' not in imported
    assert 'flask' not in imported
    assert 'fastapi' not in imported


def test_resources_for_exe_are_present():
    assert (ROOT / 'assets' / 'forward_circuit.png').exists()
    assert (ROOT / 'assets' / 'inverse_circuit.png').exists()
    assert (ROOT / 'sboxlab' / 'data' / 'forward_netlist.json').exists()
    assert (ROOT / 'sboxlab' / 'data' / 'inverse_netlist.json').exists()
    assert (ROOT / 'SBoxLab.spec').exists()


def test_desktop_imports_without_starting_gui():
    import desktop_app
    assert callable(desktop_app.main)
    assert desktop_app.hex_lut(np.array([0, 1, 10, 15], dtype=np.uint8)) == '01AF'
