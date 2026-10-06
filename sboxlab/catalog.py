from pathlib import Path
import json
import pandas as pd
from .core import analyze,parse_lut,construct,inverse

def benchmarks():return json.loads((Path(__file__).resolve().parent/'data/benchmarks.json').read_text())

def comparison():
    items=[('Proposed S',construct()),('Proposed inverse',inverse(construct()))]+[(r['name'],parse_lut(r['lut'])) for r in benchmarks()]
    rows=[]
    for name,s in items:
        v=analyze(s)['summary'];rows.append({'S-box':name,**{k:(','.join(map(str,x)) if isinstance(x,list) else x) for k,x in v.items() if k!='NL_components'}})
    return pd.DataFrame(rows)

def gate_comparison():
    return pd.DataFrame(json.loads((Path(__file__).resolve().parent/'data/published_gate_counts.json').read_text()))
