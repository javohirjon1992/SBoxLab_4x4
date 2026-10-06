"""Portable reports, raw trials, figures, and replayable ciphertext bundles."""
import io,json,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .experiments import png

def serial(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    raise TypeError(type(v).__name__)

def json_bytes(v):return json.dumps(v,default=serial,indent=2,allow_nan=False).encode()

def figure_bytes(fig,fmt='png'):
    b=io.BytesIO();fig.savefig(b,format=fmt,dpi=180,bbox_inches='tight');return b.getvalue()

def heatmap(a,title):
    fig,ax=plt.subplots(figsize=(7,5));im=ax.imshow(a,cmap='viridis');fig.colorbar(im,ax=ax)
    ax.set_title(title);ax.set_xlabel('Output mask / output bit');ax.set_ylabel('Input mask / input bit')
    ax.set_xticks(range(a.shape[1]));ax.set_yticks(range(a.shape[0]))
    if a.size<=256:
        for (i,j),v in np.ndenumerate(a):ax.text(j,i,f'{v:g}',ha='center',va='center',fontsize=7,color='white' if v<(a.max()+a.min())/2 else 'black')
    return fig

def sbox_zip(results,comparison=None):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
        for name,r in results.items():
            z.writestr(f'{name}/metrics.json',json_bytes(r))
            for field in ['lat','ddt','sac','bic_sac']:
                df=pd.DataFrame(r[field]);z.writestr(f'{name}/{field}.csv',df.to_csv(index=True));z.writestr(f'{name}/{field}.tex',df.to_latex())
                fig=heatmap(r[field],f'{name}: {field.upper()}')
                for fmt in ['png','pdf']:z.writestr(f'{name}/{field}.{fmt}',figure_bytes(fig,fmt))
                plt.close(fig)
        if comparison is not None:z.writestr('comparison.csv',comparison.to_csv(index=False));z.writestr('comparison.tex',comparison.to_latex(index=False))
    return b.getvalue()

def cipher_bundle(cipher,nonce,lut,image_id):
    b=io.BytesIO();np.savez_compressed(b,cipher=cipher,nonce=np.frombuffer(nonce,dtype=np.uint8),lut=np.asarray(lut,dtype=np.uint8),image_id=np.array(image_id),protocol=np.array('SBoxLab-image-v1'))
    return b.getvalue()

def load_cipher(file):
    # Refuse oversized decompressed NPZ entries before NumPy allocates arrays.
    raw=file.read() if hasattr(file,'read') else file
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(i.file_size for i in z.infolist())>64_000_000:raise ValueError('Cipher bundle exceeds 64 MB decompressed limit.')
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        if str(z['protocol'])!='SBoxLab-image-v1':raise ValueError('Unsupported protocol.')
        from .cipher import check_image
        from .core import validate
        c=check_image(z['cipher'].copy());n=z['nonce'].tobytes();s=validate(z['lut'])
        if len(n)!=16:raise ValueError('Invalid nonce.')
        return c,n,s,str(z['image_id'])

def experiment_zip(r):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('results.json',json_bytes({k:v for k,v in r.items() if k!='images'}))
        for k in ['statistics','differential_trials','key_trials_raw','runtime_raw']:
            df=pd.DataFrame(r[k]);z.writestr(k+'.csv',df.to_csv(index=False))
        z.writestr('runtime.tex',pd.DataFrame([r['runtime']]).to_latex(index=False))
        z.writestr('recovery.tex',pd.DataFrame([r['recovery']]).to_latex(index=False))
        for key in ['differential_trials','key_trials_raw']:
            df=pd.DataFrame(r[key])
            if not df.empty:
                summary=df.groupby('round')[['NPCR','UACI','Hamming']].agg(['mean','std','min','max']) if key=='differential_trials' else df[['NPCR','UACI','Hamming']].agg(['mean','std','min','max'])
                z.writestr(key+'_summary.csv',summary.to_csv());z.writestr(key+'_summary.tex',summary.to_latex())
        for name,a in r['images'].items():z.writestr(f'images/{name}.png',png(a))
        z.writestr('ciphertext.npz',cipher_bundle(r['images']['R2'],bytes.fromhex(r['nonce_hex']),r['lut'],r['image_id']))
        def save(fig,name):
            for fmt in ['png','pdf']:z.writestr(f'figures/{name}.{fmt}',figure_bytes(fig,fmt))
            plt.close(fig)
        fig,ax=plt.subplots(figsize=(7,4))
        for name in ['Original','R1','R2']:ax.plot(np.bincount(r['images'][name].ravel(),minlength=256),label=name,lw=1)
        ax.set(xlabel='Byte intensity',ylabel='Frequency',title='Histogram');ax.legend();save(fig,'histograms')
        fig,axes=plt.subplots(2,3,figsize=(11,6))
        for row,name in enumerate(['Original','R2']):
            a=r['images'][name];pairs=[(a[:,:-1],a[:,1:]),(a[:-1],a[1:]),(a[:-1,:-1],a[1:,1:])]
            for col,(x,y) in enumerate(pairs):
                x=x.ravel();y=y.ravel();stride=max(1,len(x)//5000)
                axes[row,col].scatter(x[::stride],y[::stride],s=1,alpha=.25);axes[row,col].set(title=f'{name} / {"HVD"[col]}',xlabel='Pixel component',ylabel='Neighbor component')
        fig.tight_layout();save(fig,'correlations')
        fig,ax=plt.subplots(figsize=(6,4));ax.bar(['Original','R1','R2'],[v['entropy'] for v in r['statistics']]);ax.set(ylabel='Shannon entropy (bits)',ylim=(0,8));save(fig,'entropy')
        for key,name in [('differential_trials','differential'),('key_trials_raw','key_sensitivity')]:
            df=pd.DataFrame(r[key])
            if df.empty:continue
            fig,axes=plt.subplots(1,2,figsize=(9,4))
            for ax,metric,ref in zip(axes,['NPCR','UACI'],[99.609375,100*257/(3*256)]):
                if 'round' in df:
                    for rnd,g in df.groupby('round'):ax.plot(g['trial'],g[metric],label=f'R{rnd}')
                else:ax.plot(df['trial'],df[metric],label='R2')
                ax.axhline(ref,ls='--',color='black',label='Random reference');ax.set(xlabel='Trial',ylabel=metric+' (%)');ax.legend(fontsize=7)
            fig.tight_layout();save(fig,name)
        fig,ax=plt.subplots(figsize=(6,4));ax.bar(['Encrypt','Decrypt'],[r['runtime']['encrypt_median_ms'],r['runtime']['decrypt_median_ms']]);ax.set(ylabel='Median time (ms)',title='Measured on the executing machine');save(fig,'runtime')
        z.writestr('REPORT.md','# SBoxLab measured experiment\n\nProtocol: '+r['metadata']['protocol']+'\n\nMachine: '+r['metadata']['platform']+'\n\nExact decryption: '+str(r['recovery']['exact'])+'\n\nKDF material generation is excluded from runtime measurements. Raw trials and environment versions are included. No secret key is exported.\n')
    return b.getvalue()

def benchmark_tables_zip():
    from .catalog import benchmarks,comparison,gate_comparison
    from .core import parse_lut,analyze
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('comparison.csv',comparison().to_csv(index=False))
        z.writestr('published_gate_counts.csv',gate_comparison().to_csv(index=False))
        for i,item in enumerate(benchmarks()):
            r=analyze(parse_lut(item['lut']));prefix=f'{i+1:02d}'
            z.writestr(prefix+'/source.json',json_bytes(item))
            z.writestr(prefix+'/metrics.json',json_bytes(r))
            for field in ['lat','ddt','sac','bic_sac']:z.writestr(prefix+'/'+field+'.csv',pd.DataFrame(r[field]).to_csv())
    return b.getvalue()
