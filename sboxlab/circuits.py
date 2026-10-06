"""Exhaustive netlist simulation, HDL export, and optional ABC integration."""
from pathlib import Path
import json, subprocess, tempfile, shutil
from collections import Counter
import numpy as np
DATA=Path(__file__).resolve().parent/'data'

def load(direction='forward'):return json.loads((DATA/f'{direction}_netlist.json').read_text())

def simulate(gates,direction='forward'):
    inp,out=('x','s') if direction=='forward' else ('y','r')
    depths={f'{inp}{j}':0 for j in range(4)}; lut=[]
    for name,op,a,b in gates:
        if name in depths or a not in depths or b not in depths:raise ValueError('Netlist is not topologically valid.')
        if op not in ['AND','OR','NAND','NOR']:raise ValueError('Unsupported gate.')
        depths[name]=1+max(depths[a],depths[b])
    for x in range(16):
        v={f'{inp}{j}':x>>j&1 for j in range(4)}
        for name,op,a,b in gates:
            z=(v[a]&v[b]) if op in ['AND','NAND'] else (v[a]|v[b])
            v[name]=1-z if op.startswith('N') else z
        lut.append(sum(v[f'{out}{j}']<<j for j in range(4)))
    return np.array(lut,dtype=np.uint8),{'gates':len(gates),'depth':max(depths[f'{out}{j}'] for j in range(4)),'composition':dict(Counter(g[1] for g in gates))}

def dot(gates,direction='forward'):
    inp,out=('x','s') if direction=='forward' else ('y','r')
    lines=['digraph G { rankdir=LR; bgcolor="white"; node [fontname="Times",shape=box]; edge [arrowhead=none];']
    for j in range(4):lines.append(f'{inp}{j} [shape=plaintext];')
    for name,op,a,b in gates:
        lines.extend([f'{name} [label="{name}: {op}"];',f'{a} -> {name};',f'{b} -> {name};'])
    lines.append('}')
    return '\n'.join(lines)

def verilog(gates,direction='forward'):
    inp,out=('x','s') if direction=='forward' else ('y','r')
    wires=[g[0] for g in gates if not g[0].startswith(out)]
    lines=[f'module sbox_{direction}(input [3:0] {inp}, output [3:0] {out});','wire '+', '.join(wires)+';']
    def signal(n):return f'{n[0]}[{n[1:]}]' if n[0] in [inp,out] else n
    for k,(name,op,a,b) in enumerate(gates):lines.append(f'{op.lower()} g{k} ({signal(name)}, {signal(a)}, {signal(b)});')
    return '\n'.join(lines+['endmodule'])

def blif(lut):
    lines=['.model sbox','.inputs x0 x1 x2 x3','.outputs s0 s1 s2 s3']
    for j in range(4):
        lines.append(f'.names x0 x1 x2 x3 s{j}')
        for x,y in enumerate(lut):
            if int(y)>>j&1:lines.append(''.join(str(x>>i&1) for i in range(4))+' 1')
    return '\n'.join(lines+['.end'])+'\n'

def run_abc(lut,executable='abc'):
    """Optional new synthesis run. No claim to recreate the missing original search."""
    exe=shutil.which(executable)
    if not exe:raise RuntimeError('ABC is not installed or not on PATH. Export BLIF and install Berkeley ABC.')
    lib='''GATE AND2 1 Y=A*B; PIN * NONINV 1 999 1 0 1 0
GATE OR2 1 Y=A+B; PIN * NONINV 1 999 1 0 1 0
GATE NAND2 1 Y=!(A*B); PIN * INV 1 999 1 0 1 0
GATE NOR2 1 Y=!(A+B); PIN * INV 1 999 1 0 1 0
GATE INV 1 Y=!A; PIN * INV 1 999 1 0 1 0
'''
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/'input.blif').write_text(blif(lut));(p/'cells.genlib').write_text(lib)
        r=subprocess.run([exe,'-c','read_library cells.genlib; read_blif input.blif; strash; rewrite; balance; map; print_stats; write_verilog mapped.v'],cwd=tmp,capture_output=True,text=True,timeout=60)
        if r.returncode or not (p/'mapped.v').exists():raise RuntimeError(r.stdout+r.stderr)
        return r.stdout+r.stderr,(p/'mapped.v').read_text()
