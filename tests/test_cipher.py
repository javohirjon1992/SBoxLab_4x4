import io,zipfile,json
import numpy as np
import pytest
from sboxlab.cipher import *
from sboxlab.experiments import demo,run,stats,recovery,difference
from sboxlab.export import experiment_zip,cipher_bundle,load_cipher

KEY=bytes(range(16))

def scalar_diffuse(p,m):
    def rol(x):return ((x<<1)|(x>>7))&255
    def ror(x):return ((x>>1)|(x<<7))&255
    f=[]
    for i,v in enumerate(p):f.append(int(v)^int(m['df'][i%16])^(m['ivf'] if i==0 else rol(f[-1])))
    x=[0]*len(f)
    for i in range(len(f)-1,-1,-1):x[i]=f[i]^int(m['db'][i%16])^(m['ivb'] if i==len(f)-1 else ror(x[i+1]))
    return np.array(x,dtype=np.uint8)

@pytest.mark.parametrize('shape',[(1,1),(1,7),(7,1),(7,9),(8,11,3),(17,16,3)])
def test_exact_inversion_and_scalar_reference(shape):
    rng=np.random.default_rng(19);a=rng.integers(0,256,shape,dtype=np.uint8)
    nonce=nonce_for('test',shape);m=material(KEY,nonce,shape)
    for t in m:
        assert np.array_equal(diffuse(a.ravel(),t),scalar_diffuse(a.ravel(),t))
        assert np.array_equal(undiffuse(diffuse(a.ravel(),t),t),a.ravel())
    for rounds in [1,2]:
        c=encrypt(a,m[:rounds]);assert np.array_equal(decrypt(c,m[:rounds]),a)
    c=encrypt(a,m);assert not np.array_equal(c,encrypt(a,material(KEY,nonce_for('other',shape),shape)))

def test_cipher_bundle():
    a=demo(16);n=nonce_for('demo',a.shape);c=encrypt(a,material(KEY,n,a.shape))
    blob=cipher_bundle(c,n,construct(),'demo');cc,nn,s,i=load_cipher(blob)
    assert np.array_equal(decrypt(cc,material(KEY,nn,cc.shape),s),a)
    assert i=='demo'
    with np.load(io.BytesIO(blob),allow_pickle=False) as z:assert 'key' not in z.files

def test_metrics_and_export():
    a=demo(16);assert recovery(a,a)['exact'] and recovery(a,a)['SSIM']==1
    assert difference(a,a)=={'NPCR':0.,'UACI':0.,'Hamming':0.}
    r=run(a,KEY,'demo',construct(),trials=3,key_trials=2,warmups=0,repeats=2)
    assert r['recovery']['exact'] and len(r['differential_trials'])==6
    assert r['runtime']['encrypt_median_ms']>0
    blob=experiment_zip(r)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        assert z.testzip() is None
        assert 'figures/correlations.pdf' in z.namelist()
        data=json.loads(z.read('results.json'));assert 'key' not in data

def test_small_constant_images():
    a=np.zeros((1,1),dtype=np.uint8)
    assert stats(a)['r_H'] is None and recovery(a,a)['SSIM'] is None
    with pytest.raises(ValueError):key_bytes('00')

def test_every_byte_nibble_and_large_image():
    s=construct();si=inverse(s);a=np.arange(256,dtype=np.uint8)
    b=(s[a>>4]<<4)|s[a&15];assert np.array_equal((si[b>>4]<<4)|si[b&15],a)
    im=np.tile(a,(256,1));m=material(KEY,nonce_for('large',im.shape),im.shape)
    assert np.array_equal(decrypt(encrypt(im,m),m),im)
