"""Research-only image transform; explicit v1 encoding of underspecified KDF details."""
import hashlib, json
import numpy as np
from .core import validate,inverse,construct
PROTOCOL='SBoxLab-image-v1'

def key_bytes(text):
    try:k=bytes.fromhex(text)
    except ValueError as e:raise ValueError('Key must be hexadecimal.') from e
    if len(k)!=16:raise ValueError('Key must contain exactly 32 hex characters (128 bits).')
    return k

def nonce_for(image_id,shape):
    return hashlib.sha256(json.dumps([str(image_id),list(shape)],separators=(',',':')).encode()).digest()[:16]

def material(key,nonce,shape,rounds=2):
    if len(key)!=16 or len(nonce)!=16:raise ValueError('Key and nonce must each be 16 bytes.')
    if len(shape) not in (2,3) or (len(shape)==3 and shape[2]!=3):raise ValueError('Use grayscale or RGB images.')
    if rounds not in (1,2):raise ValueError('Rounds must be 1 or 2.')
    n=int(shape[0]*shape[1]); result=[]
    for r in range(1,rounds+1):
        prefix=PROTOCOL.encode()+b'\0'+key+nonce+r.to_bytes(4,'big')
        derive=lambda label:hashlib.sha256(prefix+label.encode()).digest()
        scores=np.frombuffer(hashlib.shake_256(prefix+b'PERM').digest(8*n),dtype='<u8')
        pi=np.argsort(scores,kind='stable');inv=np.argsort(pi)
        result.append({'rk':np.frombuffer(derive('RK')[:16],dtype=np.uint8).copy(),
          'df':np.frombuffer(derive('DF')[:16],dtype=np.uint8).copy(),'db':np.frombuffer(derive('DB')[:16],dtype=np.uint8).copy(),
          'ivf':derive('IVF')[0],'ivb':derive('IVB')[0],'pi':pi,'inv':inv})
    return result

def rot(v,n):
    v=np.asarray(v,dtype=np.uint16);n=np.asarray(n)%8
    return (((v<<n)|(v>>((8-n)%8)))&255).astype(np.uint8)

def _scan(q,iv,step):
    # Normalize rotations, cumulative XOR, then restore the rotation at each index.
    q=q.copy();q[0]^=iv;k=np.arange(q.size,dtype=np.int64)*step
    return rot(np.bitwise_xor.accumulate(rot(q,-k)),k)

def diffuse(p,m):
    n=p.size
    f=_scan(p ^ np.resize(m['df'],n),m['ivf'],1)
    return _scan((f ^ np.resize(m['db'],n))[::-1],m['ivb'],-1)[::-1].copy()

def undiffuse(x,m):
    n=x.size;f=x ^ np.resize(m['db'],n);f[-1]^=m['ivb'];f[:-1]^=rot(x[1:],-1)
    p=f ^ np.resize(m['df'],n);p[0]^=m['ivf'];p[1:]^=rot(f[:-1],1)
    return p

def check_image(a):
    a=np.asarray(a)
    if a.dtype!=np.uint8 or a.ndim not in (2,3) or min(a.shape[:2])<1 or (a.ndim==3 and a.shape[2]!=3):
        raise ValueError('Image must be a nonempty uint8 grayscale or RGB array.')
    return a

def encrypt(image,mats,lut=None,stages=False):
    image=check_image(image);s=validate(construct() if lut is None else lut);shape=image.shape;x=image.copy();states=[]
    for m in mats:
        a=x.ravel() ^ np.resize(m['rk'],x.size)
        b=(s[a>>4]<<4)|s[a&15]
        p=b.reshape(shape).reshape((len(m['pi']),-1))[m['pi']].ravel()
        x=diffuse(p,m).reshape(shape);states.append(x.copy())
    return states if stages else x

def decrypt(image,mats,lut=None):
    image=check_image(image);s=inverse(construct() if lut is None else lut);shape=image.shape;x=image.copy()
    for m in reversed(mats):
        p=undiffuse(x.ravel(),m).reshape((len(m['pi']),-1))
        b=p[m['inv']].ravel();a=(s[b>>4]<<4)|s[b&15]
        x=(a ^ np.resize(m['rk'],a.size)).reshape(shape)
    return x
