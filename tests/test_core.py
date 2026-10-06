import numpy as np
import pytest
from sboxlab.core import construct,core,inverse,analyze,parse_lut,anf,gf2_rank,affine_search
from sboxlab.circuits import load,simulate
from sboxlab.catalog import benchmarks

def test_reference_construction():
    assert core().tolist()==list(bytes.fromhex('000102030406080B050C0D070A0F090E'))
    assert ''.join(f'{v:X}' for v in construct())=='4B8A6C72013E59FD'
    assert ''.join(f'{v:X}' for v in inverse(construct()))=='897A0C462D315FBE'

def test_metrics_and_inverse():
    s=construct();f=analyze(s);r=analyze(inverse(s))
    for v in [f,r]:
        m=v['summary'];assert m['NL']==4 and m['DU']==4 and m['linear_bias']==.25
        assert m['AD']==[3]*4 and m['FP']==0 and m['OFP']==0
        assert np.all(v['sac']==.5);assert np.all(v['ddt'].sum(axis=1)==16)
        for j in range(4):
            c=anf((v['lut']>>j)&1)
            for x in range(16):
                out=0
                for mask in range(16):
                    if x&mask==mask:out^=int(c[mask])
                assert out==int(v['lut'][x]>>j&1)
    assert f['summary']['AT']==[7,6,11,7]
    assert r['summary']['AT']==[6,7,7,11]
    assert np.array_equal(f['lat'].T,r['lat']) and np.array_equal(f['ddt'].T,r['ddt'])
    assert np.array_equal(f['ddt'],f['ddt'].T)

def test_independent_walsh_ddt_reference():
    s=construct();r=analyze(s)
    for a in range(16):
        for b in range(16):
            w=sum((-1)**(((a&x).bit_count()+(b&int(s[x])).bit_count())%2) for x in range(16))
            assert w==r['lat'][a,b]
            assert sum(int(s[x])^int(s[x^a])==b for x in range(16))==r['ddt'][a,b]

def test_circuits_exhaustive():
    for d,target,comp in [('forward',construct(),{'AND':11,'OR':10,'NAND':1,'NOR':6}),('inverse',inverse(construct()),{'AND':11,'OR':10,'NAND':2,'NOR':5})]:
        s,info=simulate(load(d),d);assert np.array_equal(s,target)
        assert info=={'gates':28,'depth':7,'composition':comp}

def test_benchmark_catalog():
    assert len(benchmarks())==25
    for row in benchmarks():assert analyze(parse_lut(row['lut']))['summary']['NL']==4

def test_validation_and_search():
    for text in ['0'*16,'0123','0123456789ABCDEG']:
        with pytest.raises(ValueError):parse_lut(text)
    with pytest.raises(ValueError):construct(a=np.zeros((4,4),dtype=int))
    rows=affine_search(5,123);assert rows==affine_search(5,123)
    assert all(r['NL']==4 and r['DU']==4 for r in rows)
