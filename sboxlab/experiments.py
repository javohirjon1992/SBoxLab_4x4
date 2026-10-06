"""Statistical validation and actual-machine timing; no reference results substituted."""
import io,time,platform,sys,hashlib,importlib.metadata,os
import numpy as np
from PIL import Image
from scipy.stats import chi2
from skimage.metrics import structural_similarity
from .cipher import material,encrypt,decrypt,nonce_for,PROTOCOL

def image_from_file(file):
    with Image.open(file) as im:
        if im.width*im.height>4_000_000:raise ValueError('Limit: 4 million pixels per image.')
        return np.asarray(im.convert('L' if im.mode in ['L','1','I','I;16','F'] else 'RGB'),dtype=np.uint8).copy()

def png(a):
    b=io.BytesIO();Image.fromarray(a).save(b,format='PNG');return b.getvalue()

def demo(size=64):
    y,x=np.indices((size,size));return np.stack([(x*255//max(size-1,1)),(y*255//max(size-1,1)),((x//8+y//8)%2)*255],axis=2).astype(np.uint8)

def stats(a):
    h=np.bincount(a.ravel(),minlength=256);p=h[h>0]/a.size
    pairs=[(a[:,:-1],a[:,1:]),(a[:-1],a[1:]),(a[:-1,:-1],a[1:,1:])]
    rs=[]
    for x,y in pairs:
        x=x.ravel().astype(float);y=y.ravel().astype(float)
        rs.append(float(np.corrcoef(x,y)[0,1]) if len(x)>1 and x.std()>0 and y.std()>0 else None)
    v=float(np.sum((h-a.size/256)**2/(a.size/256)))
    return {'entropy':float(-sum(p*np.log2(p))),'r_H':rs[0],'r_V':rs[1],'r_D':rs[2],'chi2':v,'chi2_p':float(chi2.sf(v,255))}

def difference(a,b):
    d=np.abs(a.astype(float)-b.astype(float))
    return {'NPCR':float(np.mean(a!=b)*100),'UACI':float(d.mean()/255*100),'Hamming':float(np.unpackbits(a^b).mean()*100)}

def recovery(a,b):
    d=a.astype(float)-b.astype(float);mse=float(np.mean(d*d));win=min(7,*a.shape[:2]);win-=1-win%2
    ss=float(structural_similarity(a,b,data_range=255,channel_axis=-1 if a.ndim==3 else None,win_size=win)) if win>=3 else None
    return {'MSE':mse,'MaxErr':float(np.max(abs(d))),'PSNR': 'Infinity' if mse==0 else float(10*np.log10(255**2/mse)),
      'SSIM':ss,'Recovery_percent':float(np.mean(a==b)*100),'exact':bool(np.array_equal(a,b))}

def metadata():
    names=['numpy','pandas','Pillow','matplotlib','scipy','scikit-image']
    versions={}
    for n in names:
        try:versions[n]=importlib.metadata.version(n)
        except importlib.metadata.PackageNotFoundError:versions[n]='not installed'
    cpu=platform.processor() or 'not reported by OS';ram=None
    try:
        if sys.platform=='win32':
            import winreg,ctypes
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as reg:
                cpu=winreg.QueryValueEx(reg,'ProcessorNameString')[0].strip()
            kb=ctypes.c_ulonglong()
            if ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(kb)):ram=kb.value*1024
        elif sys.platform.startswith('linux'):
            from pathlib import Path
            for line in Path('/proc/cpuinfo').read_text().splitlines():
                if line.startswith('model name'):cpu=line.split(':',1)[1].strip();break
            ram=os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')
    except (OSError,ValueError,AttributeError):pass
    return {'platform':platform.platform(),'processor':cpu,'machine':platform.machine(),'logical_cpus':os.cpu_count(),'physical_memory_bytes':ram,
      'python':sys.version,'libraries':versions,'protocol':PROTOCOL,'timing_clock':'perf_counter_ns','backend':'NumPy rotation-normalized XOR scan'}

def run(image,key,image_id,lut,trials=100,key_trials=30,warmups=5,repeats=30,seed=42,progress=None):
    if not 0<=trials<=1000 or not 0<=key_trials<=128 or repeats<2 or warmups<0:raise ValueError('Invalid experiment counts.')
    nonce=nonce_for(image_id,image.shape);mats=material(key,nonce,image.shape);states=encrypt(image,mats,lut,True)
    recovered=decrypt(states[-1],mats,lut)
    if not np.array_equal(recovered,image):raise AssertionError('Round-trip failed; timing cancelled.')
    rng=np.random.default_rng(seed);diff=[];ks=[];total=max(trials+key_trials+repeats,1);done=0
    def tick():
        nonlocal done
        done+=1
        if progress:progress(min(done/total,1))
    for t in range(trials):
        changed=image.copy();bit=int(rng.integers(image.size*8));changed.ravel()[bit//8]^=1<<(bit%8)
        alt=encrypt(changed,mats,lut,True)
        for r in range(2):diff.append({'trial':t,'round':r+1,'plaintext_bit':bit,**difference(states[r],alt[r])})
        tick()
    for t,bit in enumerate(rng.choice(128,size=key_trials,replace=False)):
        k=bytearray(key);k[int(bit)//8]^=1<<(int(bit)%8)
        altered=encrypt(image,material(bytes(k),nonce,image.shape),lut)
        ks.append({'trial':t,'key_bit':int(bit),**difference(states[-1],altered)});tick()
    for _ in range(warmups):encrypt(image,mats,lut);decrypt(states[-1],mats,lut)
    times=[]
    for i in range(repeats):
        t=time.perf_counter_ns();c=encrypt(image,mats,lut);enc=(time.perf_counter_ns()-t)/1e6
        t=time.perf_counter_ns();p=decrypt(c,mats,lut);dec=(time.perf_counter_ns()-t)/1e6
        if not np.array_equal(p,image):raise AssertionError('Timed round-trip failed.')
        times.append({'repeat':i,'encrypt_ms':enc,'decrypt_ms':dec});tick()
    e=np.array([r['encrypt_ms'] for r in times]);d=np.array([r['decrypt_ms'] for r in times])
    runtime={'encrypt_median_ms':float(np.median(e)),'encrypt_std_ms':float(e.std(ddof=1)),'decrypt_median_ms':float(np.median(d)),
      'decrypt_std_ms':float(d.std(ddof=1)),'MB_per_s':float(image.size/(1000*np.median(e))),
      'warmups':warmups,'repeats':repeats,'round_material_included':False}
    return {'metadata':metadata(),'image_id':image_id,'shape':list(image.shape),'image_sha256':hashlib.sha256(image.tobytes()).hexdigest(),
      'nonce_hex':nonce.hex(),'lut':[int(x) for x in lut],'seed':seed,'trials':trials,'key_trials':key_trials,
      'statistics':[{'stage':n,**stats(a)} for n,a in zip(['Original','R1','R2'],[image,*states])],
      'recovery':recovery(image,recovered),'cipher_difference':recovery(image,states[-1]),'differential_trials':diff,'key_trials_raw':ks,
      'runtime_raw':times,'runtime':runtime,'images':{'Original':image,'R1':states[0],'R2':states[1],'Recovered':recovered}}
