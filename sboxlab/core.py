"""Exact LSB-first Boolean algebra and cryptographic metrics."""
import numpy as np
from itertools import combinations

A = np.array([[0,1,1,1],[0,0,1,0],[1,1,1,1],[0,1,1,0]], dtype=np.uint8)
B = np.array([[1,0,0,0],[0,1,1,0],[0,1,0,1],[1,0,0,1]], dtype=np.uint8)
CORE_TERMS = [[1,8,5,12,7,11,13,14],[2,5,6,10,11,12,13],[4,8,6,13,14],[6,9,10,12,13]]

def validate(lut):
    a = np.asarray(lut)
    if a.shape != (16,) or not np.issubdtype(a.dtype, np.integer) or sorted(a.tolist()) != list(range(16)):
        raise ValueError('Enter a permutation of the integers 0 through 15.')
    return a.astype(np.uint8)

def parse_lut(text):
    text = text.strip().replace(',', ' ')
    if len(text) == 16 and ' ' not in text:
        return validate([int(c,16) for c in text])
    return validate([int(v,16) for v in text.split()])

def gf2_rank(m):
    m = np.asarray(m,dtype=np.uint8).copy() % 2
    row = 0
    for col in range(m.shape[1]):
        piv = np.flatnonzero(m[row:,col])
        if not len(piv): continue
        j = row + piv[0]; m[[row,j]] = m[[j,row]]
        for k in range(m.shape[0]):
            if k != row and m[k,col]: m[k] ^= m[row]
        row += 1
        if row == m.shape[0]: break
    return row

def linear(m, x):
    m=np.asarray(m)
    if m.shape != (4,4) or not np.isin(m,[0,1]).all(): raise ValueError('Matrix must be binary 4 x 4.')
    bits=(np.asarray(x,dtype=np.uint8)[...,None] >> np.arange(4)) & 1
    return (((bits @ m.T) % 2) @ (1 << np.arange(4))).astype(np.uint8)

def core():
    x=np.arange(16,dtype=np.uint8); out=np.zeros(16,dtype=np.uint8)
    for j,terms in enumerate(CORE_TERMS):
        bit=np.zeros(16,dtype=np.uint8)
        for mask in terms: bit ^= ((x & mask)==mask).astype(np.uint8)
        out |= bit << j
    return out

def construct(a=A,b=B,alpha=9,beta=10):
    if not 0<=int(alpha)<16 or not 0<=int(beta)<16: raise ValueError('Offsets must be 0..15.')
    linear(a,0); linear(b,0)
    if gf2_rank(a)!=4 or gf2_rank(b)!=4: raise ValueError('Both matrices must be invertible over GF(2).')
    return validate(linear(b,core()[linear(a,np.arange(16)) ^ alpha]) ^ beta)

def inverse(s): return np.argsort(validate(s)).astype(np.uint8)

def anf(f):
    c=np.asarray(f,dtype=np.uint8).copy()
    for i in range(4):
        for mask in range(16):
            if mask & (1<<i): c[mask] ^= c[mask^(1<<i)]
    return c

def anf_string(f, variable='x'):
    return ' XOR '.join('1' if m==0 else '*'.join(f'{variable}{j}' for j in range(4) if m>>j&1) for m in np.flatnonzero(anf(f))) or '0'

def analyze(s):
    s=validate(s); x=np.arange(16); parity=np.array([v.bit_count()%2 for v in range(16)],dtype=np.int16)
    w=np.array([[sum(1-2*parity[(a&x) ^ (b&s)]) for b in range(16)] for a in range(16)],dtype=int)
    d=np.array([np.bincount(s ^ s[x^a],minlength=16) for a in range(16)])
    sac=np.array([[np.mean(((s ^ s[x^(1<<i)])>>j)&1) for j in range(4)] for i in range(4)])
    cs=[anf((s>>j)&1) for j in range(4)]
    nl=(8-np.max(abs(w[:,1:]),axis=0)/2).astype(int)
    bic=np.array([[np.mean((((s^s[x^(1<<i)])>>j)^((s^s[x^(1<<i)])>>k))&1) for j,k in combinations(range(4),2)] for i in range(4)])
    degrees=[max((int(m).bit_count() for m in np.flatnonzero(c)),default=0) for c in cs]
    return {'lut':s,'inverse':inverse(s),'lat':w,'ddt':d,'sac':sac,'bic_sac':bic,
        'anf':[anf_string((s>>j)&1) for j in range(4)],
        'summary':{'NL':int(nl.min()),'NL_components':nl.tolist(),'NL_coordinates':[int(nl[(1<<j)-1]) for j in range(4)],
        'DU':int(d[1:].max()),'DP_max':float(d[1:].max()/16),'LAT_max':int(abs(w[1:,1:]).max()),
        'linear_bias':float(abs(w[1:,1:]).max()/32),'SAC_min':float(sac.min()),'SAC_mean':float(sac.mean()),'SAC_max':float(sac.max()),
        'AD':degrees,'AT':[int(c.sum()) for c in cs],'FP':int(sum(s==x)),'OFP':int(sum(s==(x^15))),
        'BIC_NL_min':min(int(nl[(1<<j | 1<<k)-1]) for j,k in combinations(range(4),2)),
        'BIC_SAC_min':float(bic.min()),'BIC_SAC_mean':float(bic.mean()),'BIC_SAC_max':float(bic.max())}}

def trace(a=A,b=B,alpha=9,beta=10):
    s=construct(a,b,alpha,beta); x=np.arange(16); ax=linear(a,x); u=ax^alpha; g=core()[u]; bg=linear(b,g)
    return [{'x':f'{i:X}','Ax':f'{ax[i]:X}','Ax XOR alpha':f'{u[i]:X}','G(u)':f'{g[i]:X}','B G(u)':f'{bg[i]:X}','S(x)':f'{s[i]:X}'} for i in range(16)]

def affine_search(count=100,seed=42):
    """Seeded sampling, NOT exhaustive classification of GL(4,2)^2."""
    rng=np.random.default_rng(seed); rows=[]
    def matrix():
        while True:
            m=rng.integers(0,2,(4,4),dtype=np.uint8)
            if gf2_rank(m)==4:return m
    for k in range(count):
        a,b=matrix(),matrix(); alpha,beta=map(int,rng.integers(0,16,2))
        s=construct(a,b,alpha,beta); f=analyze(s); r=analyze(inverse(s))
        rows.append({'trial':k,'lut':''.join(f'{v:X}' for v in s),'A':a.tolist(),'B':b.tolist(),'alpha':alpha,'beta':beta,
          'SAC_forward_min':f['summary']['SAC_min'],'SAC_forward_max':f['summary']['SAC_max'],
          'SAC_inverse_min':r['summary']['SAC_min'],'SAC_inverse_max':r['summary']['SAC_max'],
          'ideal_bidirectional':bool(np.all(f['sac']==.5) and np.all(r['sac']==.5)),
          'NL':f['summary']['NL'],'DU':f['summary']['DU']})
    return rows
